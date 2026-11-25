"""Provider-independent LLM interface returning schema-validated JSON.

The LLM is used only for synthesis (reading sources, classifying, extracting
evidence). All arithmetic, scoring, dedupe and validation are deterministic Python.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..config import env
from ..monitoring.budget_tracker import BudgetExceeded, BudgetTracker
from ..utils.cache import DiskCache
from ..utils.http import backoff_sleep

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class LLMConfigError(LLMError):
    """The key or account is misconfigured: every call will fail the same way, so the run must stop."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


def strict_json_schema(model: Type[BaseModel]) -> dict:
    """Pydantic schema -> self-contained strict JSON schema (inlined refs, no extras)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            node = {k: resolve(v) for k, v in node.items()
                    if k not in ("title", "default", "minimum", "maximum", "exclusiveMinimum",
                                 "exclusiveMaximum", "format", "description")}
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            return node
        if isinstance(node, list):
            return [resolve(n) for n in node]
        return node

    return resolve(schema)


def optional_instead_of_nullable(schema: dict) -> dict:
    """Turn `anyOf: [X, null]` properties into optional (non-required) X.

    Anthropic structured outputs allow at most 16 union-typed parameters; every nullable field in
    the models has a default, so leaving it out is equivalent to null."""
    node = copy.deepcopy(schema)

    def walk(n):
        if isinstance(n, dict):
            props = n.get("properties")
            if isinstance(props, dict):
                for name, p in list(props.items()):
                    opts = p.get("anyOf") if isinstance(p, dict) else None
                    if opts and len(opts) == 2 and {"type": "null"} in opts:
                        props[name] = next(o for o in opts if o != {"type": "null"})
                        if name in n.get("required", []):
                            n["required"] = [r for r in n["required"] if r != name]
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(node)
    return node


def schema_instruction(schema: dict | None) -> str:
    if not schema:
        return "\n\nRespond with a single JSON object."
    return ("\n\nRespond with a single JSON object that validates against this JSON schema "
            "(use exactly these field names):\n" + json.dumps(schema, separators=(",", ":")))


def extract_json(text: str) -> str:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start > 0:
        text = text[start:]
    end = max(text.rfind("}"), text.rfind("]"))
    if end != -1:
        text = text[: end + 1]
    return text


class LLMProvider:
    name = "base"

    def __init__(self, model: str, budget: BudgetTracker, cache_root, max_output_tokens: int = 8000,
                 fallback_models: list[str] | None = None, retry: dict | None = None):
        retry = retry or {}
        self.max_transient = int(retry.get("max_retries", 5))
        self.retry_base = float(retry.get("retry_base_seconds", 4))
        self.retry_cap = float(retry.get("retry_cap_seconds", 60))
        self.model = model
        self.primary_model = model
        # Tried in order when the current model keeps returning overload/rate-limit errors.
        self.models = [model] + [m for m in (fallback_models or []) if m and m != model]
        self.budget = budget
        self.max_output_tokens = max_output_tokens
        self.cache = DiskCache(cache_root, "llm")
        self.errors: list[str] = []

    @property
    def available(self) -> bool:
        return True

    def verify_key(self) -> None:
        """Free request (model listing) that raises LLMConfigError if the key or account is unusable."""

    # Subclasses implement one raw call.
    def _call(self, system: str, user: str, schema: dict | None) -> LLMResponse:
        raise NotImplementedError

    def complete_json(self, system: str, user: str, output_model: Type[T], *, cache: bool = True) -> T:
        schema = strict_json_schema(output_model)
        key = hashlib.sha256(f"{self.name}|{self.primary_model}|{system}|{user}|{json.dumps(schema, sort_keys=True)}".encode()).hexdigest()
        if cache:
            cached = self.cache.get(key, ttl_seconds=30 * 86400)
            if cached:
                try:
                    return output_model.model_validate(cached)
                except ValidationError:
                    pass
        user_msg = user
        last_error = ""
        repairs = transient = consecutive = 0
        while repairs <= 2 and transient <= self.max_transient:
            if consecutive >= 2 and len(self.models) > 1:
                # The model is overloaded: move to the next one and stay there for the rest of the run.
                nxt = self.models[(self.models.index(self.model) + 1) % len(self.models)]
                logger.warning("%s model %s overloaded; switching to %s", self.name, self.model, nxt)
                self.model, consecutive = nxt, 0
            self.budget.require_llm()
            try:
                resp = self._call(system, user_msg, schema)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"network: {exc}"
                transient += 1
                consecutive += 1
                backoff_sleep(transient, base=self.retry_base, cap=self.retry_cap)
                continue
            except LLMConfigError as exc:
                self.errors.append(str(exc))
                raise
            except LLMError as exc:
                last_error = str(exc)
                if "retryable" in last_error:
                    transient += 1
                    consecutive += 1
                    backoff_sleep(transient, base=self.retry_base, cap=self.retry_cap)
                    continue
                break
            consecutive = 0
            self.budget.record_llm(self.model, resp.input_tokens, resp.output_tokens)
            try:
                data = json.loads(extract_json(resp.text))
                result = output_model.model_validate(data)
                if cache:
                    self.cache.set(key, result.model_dump(mode="json"))
                return result
            except (json.JSONDecodeError, ValidationError) as exc:
                repairs += 1
                last_error = f"malformed output: {str(exc)[:500]}"
                user_msg = (user + "\n\nYour previous answer did not match the required JSON schema. Error:\n"
                            + str(exc)[:1500] + "\nReturn ONLY corrected JSON using exactly the schema's field names.")
        msg = f"{self.name} LLM call failed: {last_error}"
        self.errors.append(msg)
        raise LLMError(msg)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import anthropic  # local import keeps tests free of the dependency when unused
        self._anthropic = anthropic
        # Keys created outside a workspace must name one on every request.
        workspace = env("ANTHROPIC_WORKSPACE_ID")
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        self.client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"), max_retries=2, timeout=180,
                                          default_headers=headers)
        self._use_format = True

    @property
    def available(self) -> bool:
        return bool(env("ANTHROPIC_API_KEY"))

    def verify_key(self) -> None:
        a = self._anthropic
        try:
            self.client.models.list(limit=1)
        except a.BadRequestError as exc:
            if "workspace" in str(exc.message).lower():
                raise LLMConfigError("this API key is not scoped to a workspace — create a key inside a workspace "
                                     "or add the ANTHROPIC_WORKSPACE_ID secret")
            raise LLMConfigError(f"anthropic rejected the request: {exc.message}")
        except (a.AuthenticationError, a.PermissionDeniedError) as exc:
            raise LLMConfigError(f"anthropic rejected the key: {exc.message}")

    def _call(self, system, user, schema):
        a = self._anthropic
        output_config: dict = {"effort": "low"}
        if schema and self._use_format:
            output_config["format"] = {"type": "json_schema", "schema": optional_instead_of_nullable(schema)}
        elif schema:
            user = user + schema_instruction(schema)  # prompt-only mode: the model still needs the field list
        try:
            msg = self.client.messages.create(
                model=self.model, max_tokens=self.max_output_tokens, system=system,
                messages=[{"role": "user", "content": user}], output_config=output_config,
            )
        except a.BadRequestError as exc:
            if "workspace" in str(exc.message).lower():
                raise LLMConfigError("anthropic: this API key is not scoped to a workspace. Create a key inside a "
                                     "workspace in the Anthropic Console, or add the ANTHROPIC_WORKSPACE_ID secret")
            if self._use_format and "format" in output_config:
                logger.warning("Structured output rejected (%s); falling back to prompt-only JSON.", exc.message)
                self._use_format = False
                return self._call(system, user, schema)
            raise LLMError(f"anthropic bad request: {exc.message}")
        except a.AuthenticationError:
            raise LLMConfigError("anthropic authentication failed — check ANTHROPIC_API_KEY")
        except a.PermissionDeniedError:
            raise LLMConfigError("anthropic permission denied for this model/key")
        except a.RateLimitError:
            raise LLMError("anthropic rate limited (retryable)")
        except a.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMError(f"anthropic server error {exc.status_code} (retryable)")
            raise LLMError(f"anthropic API error {exc.status_code}: {exc.message}")
        except a.APIConnectionError as exc:
            raise LLMError(f"anthropic connection error (retryable): {exc}")
        if msg.stop_reason == "refusal":
            raise LLMError("anthropic refused the request")
        text = "".join(b.text for b in msg.content if b.type == "text")
        if msg.stop_reason == "max_tokens" and not text.strip().endswith("}"):
            logger.warning("LLM output hit max_tokens; JSON may be truncated.")
        return LLMResponse(text, msg.usage.input_tokens, msg.usage.output_tokens)


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions; also the base for other OpenAI-compatible endpoints."""
    name = "openai"
    URL = "https://api.openai.com/v1/chat/completions"
    KEY_ENV = "OPENAI_API_KEY"
    MAX_TOKENS_FIELD = "max_completion_tokens"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = httpx.Client(timeout=180)

    @property
    def available(self) -> bool:
        return bool(env(self.KEY_ENV))

    _use_json_schema = True

    def verify_key(self) -> None:
        resp = self.client.get(self.URL.rsplit("/chat/completions", 1)[0] + "/models",
                               headers={"Authorization": f"Bearer {env(self.KEY_ENV) or ''}"})
        if resp.status_code in (400, 401, 403):
            raise LLMConfigError(f"{self.name} rejected the key (HTTP {resp.status_code}): {resp.text[:200]}")

    def _call(self, system, user, schema):
        # The schema is always stated in the prompt (some endpoints ignore response_format schemas),
        # and also sent as a structured-output constraint where the endpoint accepts it.
        content = user + schema_instruction(schema)
        fmt = ({"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": True}}
               if schema and self._use_json_schema else {"type": "json_object"})
        body = {"model": self.model, self.MAX_TOKENS_FIELD: self.max_output_tokens, "response_format": fmt,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        resp = self.client.post(self.URL, json=body, headers={"Authorization": f"Bearer {env(self.KEY_ENV) or ''}"})
        if resp.status_code == 400 and self._use_json_schema and schema:
            logger.warning("%s rejected json_schema response_format; using json_object + schema in prompt", self.name)
            self._use_json_schema = False
            return self._call(system, user, schema)
        if resp.status_code in (401, 403):
            raise LLMConfigError(f"{self.name} HTTP {resp.status_code}: API key rejected — check {self.KEY_ENV}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise LLMError(f"{self.name} HTTP {resp.status_code} (retryable)")
        if resp.status_code != 200:
            raise LLMError(f"{self.name} HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResponse(data["choices"][0]["message"].get("content") or "",
                           usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


class GeminiProvider(OpenAIProvider):
    """Gemini through Google's OpenAI-compatible endpoint (API key sent as a Bearer token)."""
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    KEY_ENV = "GEMINI_API_KEY"
    MAX_TOKENS_FIELD = "max_tokens"


def build_llm_provider(settings, budget, cache_root) -> LLMProvider:
    cls = {"anthropic": AnthropicProvider, "gemini": GeminiProvider, "openai": OpenAIProvider}.get(settings.llm_provider)
    if cls is None:
        raise LLMError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}")
    fallbacks = list(settings.llm_setting("fallback_models", []) or [])
    retry = {k: settings.llm_setting(k) for k in ("max_retries", "retry_base_seconds", "retry_cap_seconds")
             if settings.llm_setting(k) is not None}
    provider = cls(settings.llm_model, budget, cache_root, int(settings.get("llm.max_output_tokens", 8000)),
                   fallback_models=fallbacks, retry=retry)
    if not provider.available:
        raise LLMError(f"LLM provider {settings.llm_provider} has no API key configured")
    return provider


__all__ = ["LLMProvider", "LLMError", "BudgetExceeded", "build_llm_provider", "strict_json_schema"]
