"""
audit_agent.py
Input:  normalised dict (from normaliser) + ratio_result dict (from ratio_calculator)
Output: { status: "PASS"|"WARN"|"BLOCK", checks: [], warnings: [], reason?, block_check? }

Gatekeeper — runs before any AI narrative is generated.
BLOCK = hard stop, no output shown to user.
WARN  = output shown with caveat banner.
PASS  = clean output.
"""

import random
from typing import Optional, List, Dict, Tuple


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

# If ALL of these are null in the latest period → BLOCK
REQUIRED_FIELDS = ["revenue", "net_income", "total_equity", "total_assets"]

# If revenue alone is null → immediate BLOCK (nothing computes without it)
REVENUE_FIELD = "revenue"

# If any of these are null → WARN (degraded analysis)
IMPORTANT_FIELDS = [
    "operating_cash_flow", "total_debt", "ebit",
    "current_assets", "current_liabilities", "ebitda",
]

# At least this many of the 27 ratios must have non-null values → else BLOCK
MIN_VALID_RATIOS = 8

# Independent recalculation specs for spot-check
# Each entry: (ratio_name, numerator_field, denominator_field)
SPOT_CHECK_SPECS = [
    ("pat_margin",    "net_income",      "revenue"),
    ("current_ratio", "current_assets",  "current_liabilities"),
    ("debt_equity",   "total_debt",      "total_equity"),
    ("debt_to_assets","total_debt",      "total_assets"),
    ("roe",           "net_income",      "total_equity"),
]

# Max fractional difference between spot-check value and reported value
SPOT_CHECK_TOLERANCE = 0.05


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_div(num: Optional[float], denom: Optional[float]) -> Optional[float]:
    if num is None or denom is None or denom == 0:
        return None
    return num / denom


def _latest_period(normalised: dict) -> Tuple[str, dict]:
    """Return (date, period_dict) for the most recent annual period."""
    annual = normalised.get("annual_5yr", {})
    if not annual:
        return ("", {})
    latest_date = max(annual.keys())
    return latest_date, annual[latest_date]


def _check_result(check: str, result: str, detail: str) -> dict:
    return {"check": check, "result": result, "detail": detail}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_required_fields(normalised: dict) -> dict:
    """BLOCK if revenue is null, or if ALL required fields are null in latest period."""
    date, period = _latest_period(normalised)

    if not period:
        return _check_result(
            "required_fields", "BLOCK",
            "No annual data returned from data fetch. Cannot proceed."
        )

    if period.get(REVENUE_FIELD) is None:
        return _check_result(
            "required_fields", "BLOCK",
            f"Revenue is null in latest period ({date}). "
            "Cannot calculate margins, CAGRs, or most ratios."
        )

    null_required = [f for f in REQUIRED_FIELDS if period.get(f) is None]
    if len(null_required) == len(REQUIRED_FIELDS):
        return _check_result(
            "required_fields", "BLOCK",
            f"All required fields ({', '.join(REQUIRED_FIELDS)}) are null in {date}. "
            "Data fetch likely failed or returned empty."
        )

    if null_required:
        return _check_result(
            "required_fields", "WARN",
            f"Missing required fields in {date}: {', '.join(null_required)}. "
            "Some ratios will return N/A."
        )

    return _check_result("required_fields", "PASS", f"All required fields present in {date}.")


def _check_ratio_coverage(ratio_result: dict) -> dict:
    """BLOCK if fewer than MIN_VALID_RATIOS ratios computed successfully."""
    ratios = ratio_result.get("ratios", {})
    valid = [name for name, r in ratios.items() if r.get("value") is not None]
    n_valid = len(valid)
    n_total = len(ratios)

    if n_valid < MIN_VALID_RATIOS:
        return _check_result(
            "ratio_coverage", "BLOCK",
            f"Only {n_valid}/{n_total} ratios have valid values (minimum {MIN_VALID_RATIOS} required). "
            "Data is too sparse to generate a meaningful analysis."
        )

    if n_valid < n_total * 0.70:
        return _check_result(
            "ratio_coverage", "WARN",
            f"{n_total - n_valid} of {n_total} ratios returned N/A. "
            "Analysis will be partial — some sections may be missing."
        )

    return _check_result(
        "ratio_coverage", "PASS",
        f"{n_valid}/{n_total} ratios computed successfully."
    )


def _check_currency_consistency(normalised: dict) -> dict:
    """BLOCK if multiple currencies detected across periods, or magnitude spike detected."""
    annual = normalised.get("annual_5yr", {})
    if not annual:
        return _check_result("currency_consistency", "WARN", "No annual data to check.")

    # Currency check
    currencies = {p.get("currency") for p in annual.values() if p.get("currency")}
    if len(currencies) > 1:
        return _check_result(
            "currency_consistency", "BLOCK",
            f"Multiple currencies detected across annual periods: {currencies}. "
            "Cross-currency comparison would corrupt ratios."
        )

    # Revenue magnitude spike check — a 100x jump in one year suggests unit change
    revenues = sorted(
        [(date, p["revenue"]) for date, p in annual.items() if p.get("revenue")],
        key=lambda x: x[0],
        reverse=True,
    )
    for i in range(len(revenues) - 1):
        d_now, r_now = revenues[i]
        d_prior, r_prior = revenues[i + 1]
        if r_prior > 0:
            ratio = r_now / r_prior
            if ratio > 100 or ratio < 0.01:
                return _check_result(
                    "currency_consistency", "BLOCK",
                    f"Revenue changed {ratio:.0f}x between {d_prior} and {d_now} — "
                    "possible unit mismatch (millions vs. units) in source data."
                )

    currency = next(iter(currencies), "unknown")
    return _check_result(
        "currency_consistency", "PASS",
        f"All periods use consistent currency ({currency}) with no magnitude anomalies."
    )


def _check_spot_recalculation(normalised: dict, ratio_result: dict) -> dict:
    """
    BLOCK if spot-check recalculation differs from reported value by > 5%.
    Picks up to 3 ratios from SPOT_CHECK_SPECS where both reported and recomputed values exist.
    """
    date, period = _latest_period(normalised)
    ratios = ratio_result.get("ratios", {})

    # Filter to specs where we have both a reported value and can recompute
    candidates = []
    for ratio_name, num_field, denom_field in SPOT_CHECK_SPECS:
        reported = ratios.get(ratio_name, {}).get("value")
        recomputed = _safe_div(period.get(num_field), period.get(denom_field))
        if reported is not None and recomputed is not None:
            candidates.append((ratio_name, reported, recomputed))

    if not candidates:
        return _check_result(
            "spot_recalculation", "WARN",
            "Could not find 3 eligible ratios for spot-check (insufficient field data)."
        )

    # Pick up to 3 deterministically (sorted to keep consistent across runs)
    selected = sorted(candidates, key=lambda x: x[0])[:3]

    failures = []
    details = []
    for name, reported, recomputed in selected:
        diff_pct = abs(reported - recomputed) / max(abs(reported), 1e-10)
        status = "OK" if diff_pct <= SPOT_CHECK_TOLERANCE else "FAIL"
        details.append(
            f"{name}: reported={reported:.4f}, recomputed={recomputed:.4f}, "
            f"diff={diff_pct:.1%} [{status}]"
        )
        if status == "FAIL":
            failures.append(name)

    if failures:
        return _check_result(
            "spot_recalculation", "BLOCK",
            f"Spot-check failed for: {', '.join(failures)}. "
            f"Discrepancy > {SPOT_CHECK_TOLERANCE:.0%} suggests data pipeline error. "
            f"Details: {' | '.join(details)}"
        )

    return _check_result(
        "spot_recalculation", "PASS",
        f"Spot-check passed for {len(selected)} ratios. {' | '.join(details)}"
    )


def _check_data_history(normalised: dict) -> dict:
    """WARN if fewer than 4 years of annual data are available."""
    n = len(normalised.get("annual_5yr", {}))
    if n < 2:
        return _check_result(
            "data_history", "BLOCK",
            f"Only {n} year(s) of annual data available. "
            "Cannot calculate trends or CAGRs."
        )
    if n < 4:
        return _check_result(
            "data_history", "WARN",
            f"Only {n} years of annual data available (need 4+ for full trend analysis). "
            "5-year CAGRs and multi-year inflections will be truncated."
        )
    return _check_result(
        "data_history", "PASS",
        f"{n} years of annual data available."
    )


def _check_exceptional_items(normalised: dict) -> dict:
    """WARN if normaliser flagged exceptional items."""
    flags = normalised.get("flags", [])
    warn_flags = [f for f in flags if f.get("severity") == "warn"]

    if not warn_flags:
        return _check_result(
            "exceptional_items", "PASS",
            "No exceptional items detected in financial statements."
        )

    descriptions = [f["description"] for f in warn_flags[:3]]
    suffix = f" (+{len(warn_flags) - 3} more)" if len(warn_flags) > 3 else ""
    return _check_result(
        "exceptional_items", "WARN",
        f"{len(warn_flags)} exceptional item flag(s) detected{suffix}: "
        + " | ".join(descriptions)
    )


def _check_internal_consistency(ratio_result: dict) -> dict:
    """
    WARN if internal ratio signals contradict each other.
    Proxy for narrative contradiction — full check requires lens_agent output.
    """
    ratios = ratio_result.get("ratios", {})
    contradictions = []

    def val(name):
        return ratios.get(name, {}).get("value")

    def rag(name):
        return ratios.get(name, {}).get("rag")

    # 1. High PAT margin but negative FCF conversion → earnings may not be real cash
    pat = val("pat_margin")
    fcf_conv = val("fcf_conversion")
    if pat is not None and fcf_conv is not None:
        if pat > 0.15 and fcf_conv < 0:
            contradictions.append(
                f"PAT margin is strong ({pat:.1%}) but FCF conversion is negative ({fcf_conv:.2f}) "
                "— earnings quality concern."
            )

    # 2. Low debt/equity but high interest coverage concern inverse
    de = val("debt_equity")
    ic = val("interest_coverage")
    if de is not None and ic is not None:
        if de > 2.0 and ic < 2.0:
            contradictions.append(
                f"High leverage (D/E {de:.1f}x) combined with weak interest coverage ({ic:.1f}x) "
                "— debt service risk."
            )

    # 3. Green overall RAG but 40%+ of individual ratios are red
    signals = ratio_result.get("signals", {})
    breakdown = signals.get("rag_breakdown", {})
    total = sum(breakdown.values())
    if total > 0 and breakdown.get("red", 0) / total > 0.40:
        overall = signals.get("rag")
        if overall == "green":
            contradictions.append(
                f"Overall RAG is green but {breakdown['red']}/{total} individual ratios are red "
                "— aggregate signal may be misleading."
            )

    # 4. ROIC < WACC proxy: if ROIC < 8% but ROE > 20%, check for leverage distortion
    roic = val("roic")
    roe = val("roe")
    if roic is not None and roe is not None:
        if roic < 0.08 and roe > 0.20:
            contradictions.append(
                f"ROE ({roe:.1%}) is high but ROIC ({roic:.1%}) is low — "
                "returns may be driven by leverage, not operating performance."
            )

    if contradictions:
        return _check_result(
            "internal_consistency", "WARN",
            f"{len(contradictions)} internal signal contradiction(s): "
            + " | ".join(contradictions)
        )

    return _check_result(
        "internal_consistency", "PASS",
        "No internal signal contradictions detected."
    )


def _check_important_fields(normalised: dict) -> dict:
    """WARN if any important (non-required) fields are missing."""
    date, period = _latest_period(normalised)
    missing = [f for f in IMPORTANT_FIELDS if period.get(f) is None]
    if not missing:
        return _check_result(
            "important_fields", "PASS",
            f"All important fields present in {date}."
        )
    return _check_result(
        "important_fields", "WARN",
        f"Missing in {date}: {', '.join(missing)}. "
        "Related ratios will return N/A."
    )


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------

def audit(normalised: dict, ratio_result: dict) -> dict:
    """
    Run all gatekeeper checks and return audit result.

    Output contract:
    {
        status:      "PASS" | "WARN" | "BLOCK",
        checks:      [ { check, result, detail }, ... ],
        warnings:    [ str, ... ],
        reason:      str | None,      # human-readable BLOCK reason
        block_check: str | None,      # name of the check that triggered BLOCK
    }
    """
    checks = [
        _check_required_fields(normalised),
        _check_ratio_coverage(ratio_result),
        _check_currency_consistency(normalised),
        _check_spot_recalculation(normalised, ratio_result),
        _check_data_history(normalised),
        _check_exceptional_items(normalised),
        _check_internal_consistency(ratio_result),
        _check_important_fields(normalised),
    ]

    # Determine overall status — one BLOCK anywhere = BLOCK
    block_check = None
    reason = None
    warnings = []

    for c in checks:
        if c["result"] == "BLOCK" and block_check is None:
            block_check = c["check"]
            reason = c["detail"]
        if c["result"] == "WARN":
            warnings.append(c["detail"])

    if block_check:
        status = "BLOCK"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status":      status,
        "checks":      checks,
        "warnings":    warnings,
        "reason":      reason,
        "block_check": block_check,
    }


# ---------------------------------------------------------------------------
# Test runner — python audit_agent.py [TICKER] [MARKET]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, ".")
    from data_fetcher import fetch
    from normaliser import normalise
    from ratio_calculator import calculate

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    market = sys.argv[2] if len(sys.argv) > 2 else "US"

    print(f"\nRunning full pipeline audit: {ticker} ({market}) ...")
    raw = fetch(ticker, market)
    norm = normalise(raw)
    ratios = calculate(norm)
    result = audit(norm, ratios)

    status = result["status"]
    status_display = {"PASS": "✓ PASS", "WARN": "⚠ WARN", "BLOCK": "✗ BLOCK"}.get(status, status)
    print(f"\n  Status: {status_display}")

    print(f"\n  Check results:")
    for c in result["checks"]:
        icon = {"PASS": "✓", "WARN": "⚠", "BLOCK": "✗"}.get(c["result"], "?")
        print(f"    {icon} [{c['result']:<5}] {c['check']}")
        print(f"           {c['detail'][:120]}")

    if result["warnings"]:
        print(f"\n  Warnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"    - {w[:120]}")

    if result["reason"]:
        print(f"\n  BLOCK reason: {result['reason']}")
        print(f"  Triggered by: {result['block_check']}")

    out = f"{ticker.replace('.', '_')}_audit.json"
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"\n  Saved -> {out}")
