"""Deterministic, business-model-specific revenue estimation.

The LLM only supplies evidence-linked inputs; every number here is computed in
Python and every assumption is written out. Nothing is invented: if inputs are
missing the estimate is left empty with confidence "Insufficient".
"""
from __future__ import annotations

from ..models import CompanyProfile, Confidence, ResearchExtraction, RevenueEstimate, SourceDoc
from ..qualification.confidence_scoring import classify_disclosed, classify_modelled, count_indicators
from ..utils.normalize import root_domain
from .pricing_research import paid_price_range

SUBSCRIPTION_MODELS = {"saas_subscription", "mobile_app_subscription", "freemium_consumer", "usage_based_api",
                       "online_education", "other"}


def usd(x: float | None) -> str:
    if x is None:
        return "n/a"
    if x >= 1_000_000:
        return f"${x / 1_000_000:,.2f}M"
    if x >= 1_000:
        return f"${x / 1_000:,.1f}K"
    return f"${x:,.0f}"


def _pair(lo, hi):
    if lo is None and hi is None:
        return None
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    return (min(lo, hi), max(lo, hi))


def estimate_revenue(ex: ResearchExtraction, sources: list[SourceDoc], settings) -> RevenueEstimate:
    by_id = {s.id: s for s in sources}
    A = settings.get("revenue_assumptions", {})
    min_low = int(settings.get("qualification.min_independent_indicators_low_confidence", 2))
    signals = [s for s in ex.signals if s.source_id in by_id]
    usable = [s for s in signals if s.claim_type != "unverified"]
    indicators = count_indicators(signals, bool(ex.pricing))
    evidence = [f"{s.signal_type.replace('_', ' ')}: {s.value_text}"
                f"{(' (as of ' + s.as_of + ')') if s.as_of else ''} [{s.claim_type.replace('_', ' ')}; "
                f"{'search snippet' if not by_id[s.source_id].fully_read else 'page read'}] — {by_id[s.source_id].url}"
                for s in signals]
    cited_urls = list(dict.fromkeys(by_id[s.source_id].url for s in usable))
    source_domains = len({root_domain(u) for u in cited_urls} - {""})

    # ---------------------------------------------------------------- A. disclosed figures
    for kind in ("mrr_disclosed", "arr_disclosed", "revenue_disclosed"):
        for s in usable:
            if s.signal_type != kind or not s.numeric_value or s.numeric_value <= 0:
                continue
            text = f"{s.value_text} {s.as_of}".lower()
            monthly = kind == "mrr_disclosed" or (kind == "revenue_disclosed" and ("month" in text or "/mo" in text))
            mrr = s.numeric_value if monthly else s.numeric_value / 12
            src = by_id[s.source_id]
            conf = classify_disclosed(s.claim_type, src.fully_read)
            if s.claim_type == "third_party_estimate":
                conf = Confidence.MEDIUM
            lo, hi = mrr * 0.9, mrr * 1.1
            calc = (f"Disclosed {'monthly' if monthly else 'annual'} figure {usd(s.numeric_value)} ({s.value_text}); "
                    + ("" if monthly else f"monthly equivalent = {usd(s.numeric_value)} / 12 = {usd(mrr)}; ")
                    + "range = ±10% for timing/rounding.")
            return RevenueEstimate(
                method=("ARR-derived monthly equivalent" if kind == "arr_disclosed" else
                        "Disclosed MRR" if monthly else "Disclosed annual revenue (monthly equivalent)"),
                mrr_low=lo, mrr_high=hi, arr_low=lo * 12, arr_high=hi * 12, confidence=conf,
                arr_derived=kind == "arr_disclosed", calculation=calc, evidence=evidence,
                assumptions=["Revenue assumed roughly flat since the disclosure date"] +
                            ([] if src.fully_read else ["Figure seen in a search snippet; source page not fully read"]),
                independent_indicators=indicators, source_urls=cited_urls)

    # ---------------------------------------------------------------- B. modelled estimates
    ri = ex.revenue_inputs
    assumptions = [a.text for a in ri.assumptions]
    model = ri.model_type if ri.model_type else ex.business_model

    def first_signal(*types):
        for t in types:
            for s in usable:
                if s.signal_type == t and s.numeric_value and s.numeric_value > 0:
                    return s
        return None

    est_lo = est_hi = None
    calc = ""
    customers_evidenced = arpu_evidenced = False

    if model in ("ecommerce",):
        orders = _pair(ri.monthly_orders_low, ri.monthly_orders_high)
        aov = _pair(ri.avg_order_value_low, ri.avg_order_value_high)
        if orders is None:
            t = first_signal("monthly_traffic")
            if t:
                cv = A.get("ecommerce_visit_to_order", [0.01, 0.03])
                orders = (t.numeric_value * cv[0], t.numeric_value * cv[1])
                assumptions.append(f"Visit-to-order conversion {cv[0]:.0%}–{cv[1]:.0%} (industry benchmark assumption)")
                calc += f"Orders = {t.numeric_value:,.0f} monthly visits × {cv[0]:.0%}–{cv[1]:.0%}. "
                customers_evidenced = True
        else:
            customers_evidenced = bool(ri.paying_customers_source_id)
        if aov is None and ex.pricing:
            pr = paid_price_range(ex.pricing)
            if pr:
                aov = pr
                assumptions.append("Average order value approximated from listed product prices")
                arpu_evidenced = True
        elif aov:
            arpu_evidenced = True
        if orders and aov:
            est_lo, est_hi = orders[0] * aov[0], orders[1] * aov[1]
            calc += (f"Monthly revenue = orders {orders[0]:,.0f}–{orders[1]:,.0f} × AOV {usd(aov[0])}–{usd(aov[1])} "
                     f"= {usd(est_lo)}–{usd(est_hi)}.")
    elif model == "marketplace":
        gmv = _pair(ri.monthly_gmv_low, ri.monthly_gmv_high)
        take = _pair(ri.take_rate_low, ri.take_rate_high)
        if gmv:
            customers_evidenced = True
            if take is None:
                tr = A.get("marketplace_take_rate", [0.05, 0.15])
                take = (tr[0], tr[1])
                assumptions.append(f"Take rate {tr[0]:.0%}–{tr[1]:.0%} (assumption; not disclosed)")
            else:
                arpu_evidenced = True
            est_lo, est_hi = gmv[0] * take[0], gmv[1] * take[1]
            calc = (f"Net revenue = monthly GMV {usd(gmv[0])}–{usd(gmv[1])} × take rate {take[0]:.0%}–{take[1]:.0%} "
                    f"= {usd(est_lo)}–{usd(est_hi)} (GMV is not revenue).")
    if est_lo is None and model in SUBSCRIPTION_MODELS | {"marketplace", "ecommerce"}:
        arpu = _pair(ri.arpu_monthly_low, ri.arpu_monthly_high)
        if arpu:
            arpu_evidenced = bool(ex.pricing)
        else:
            pr = paid_price_range(ex.pricing)
            if pr:
                arpu = pr
                arpu_evidenced = True
                assumptions.append(f"ARPU {usd(pr[0])}–{usd(pr[1])}/month taken from public paid plans "
                                   "(lowest paid plan to typical plan)")
        paying = _pair(ri.paying_customers_low, ri.paying_customers_high)
        if paying and ri.paying_customers_source_id in by_id:
            customers_evidenced = True
            calc_c = f"paying customers {paying[0]:,.0f}–{paying[1]:,.0f} (sourced)"
        else:
            paying, calc_c = None, ""
            s = first_signal("paying_customers", "business_customers")
            if s:
                paying = (s.numeric_value * 0.9, s.numeric_value * 1.05)
                customers_evidenced = True
                calc_c = f"paying/business customers ≈ {s.numeric_value:,.0f} ({s.value_text})"
            else:
                s = first_signal("total_users")
                if s:
                    conv = A.get("freemium_paid_conversion", [0.02, 0.05])
                    act = A.get("active_share_of_total_users", [0.15, 0.35])
                    paying = (s.numeric_value * act[0] * conv[0], s.numeric_value * act[1] * conv[1])
                    customers_evidenced = True
                    assumptions.append(f"{act[0]:.0%}–{act[1]:.0%} of stated users are active; "
                                       f"{conv[0]:.0%}–{conv[1]:.0%} of active users pay (freemium benchmark assumption)")
                    calc_c = (f"paying = {s.numeric_value:,.0f} users × {act[0]:.0%}–{act[1]:.0%} active × "
                              f"{conv[0]:.0%}–{conv[1]:.0%} paid = {paying[0]:,.0f}–{paying[1]:,.0f}")
                else:
                    s = first_signal("app_downloads")
                    if s:
                        conv = A.get("app_downloads_to_paying_monthly", [0.002, 0.01])
                        paying = (s.numeric_value * conv[0], s.numeric_value * conv[1])
                        assumptions.append(f"{conv[0]:.1%}–{conv[1]:.1%} of lifetime downloads are current paying "
                                           "subscribers (mobile benchmark assumption)")
                        calc_c = (f"paying = {s.numeric_value:,.0f} downloads × {conv[0]:.1%}–{conv[1]:.1%} "
                                  f"= {paying[0]:,.0f}–{paying[1]:,.0f}")
        if arpu and paying:
            est_lo, est_hi = paying[0] * arpu[0], paying[1] * arpu[1]
            calc = f"MRR = {calc_c} × ARPU {usd(arpu[0])}–{usd(arpu[1])}/month = {usd(est_lo)}–{usd(est_hi)}."

    if est_lo is None or est_hi is None or est_hi <= 0:
        return RevenueEstimate(method="No defensible model — inputs not publicly available",
                               confidence=Confidence.INSUFFICIENT, evidence=evidence, assumptions=assumptions,
                               independent_indicators=indicators, source_urls=cited_urls,
                               calculation="Insufficient public inputs (customers/users/orders and pricing).")
    spread = est_hi / est_lo if est_lo > 0 else 99
    conf = classify_modelled(customers_evidenced=customers_evidenced, arpu_evidenced=arpu_evidenced,
                             indicators=indicators, source_domains=source_domains, min_low=min_low, spread=spread)
    return RevenueEstimate(method=f"{model.replace('_', ' ')} model", mrr_low=est_lo, mrr_high=est_hi,
                           arr_low=est_lo * 12, arr_high=est_hi * 12, confidence=conf, calculation=calc,
                           evidence=evidence, assumptions=assumptions, independent_indicators=indicators,
                           source_urls=cited_urls)


def revenue_range_text(rev: RevenueEstimate) -> str:
    if rev.mrr_low is None:
        return "Not publicly available"
    return f"{usd(rev.mrr_low)}–{usd(rev.mrr_high)} / month"


def apply_to_profile(profile: CompanyProfile, settings) -> None:
    profile.revenue = estimate_revenue(profile.extraction, profile.sources, settings)
