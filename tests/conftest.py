import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from founder_agent.config import Settings, load_settings


@pytest.fixture
def settings() -> Settings:
    return load_settings(Path(__file__).resolve().parents[1] / "config.yaml")


class FakeResponse:
    """Minimal stand-in for httpx.Response."""

    def __init__(self, text="", status_code=200, json_data=None, content_type="text/html"):
        self.text = text
        self.status_code = status_code
        self._json = json_data
        self.headers = {"content-type": content_type}

    def json(self):
        return self._json


class FakeClient:
    """Replays canned responses by URL substring, and records what was asked for."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.requested: list[str] = []
        self.stats = {}

    def _match(self, url):
        self.requested.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response
        return None

    async def get(self, url, **kwargs):
        return self._match(url)

    async def post(self, url, **kwargs):
        return self._match(url)

    async def get_json(self, url, **kwargs):
        resp = self._match(url)
        return resp.json() if resp is not None else None


@pytest.fixture
def fake_client():
    return FakeClient
