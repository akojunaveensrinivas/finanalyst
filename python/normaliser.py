"""
normaliser.py
Input:  raw dict from data_fetcher.fetch()
Output: { ...raw, adjusted: {}, flags: [], confidence: "high"|"medium"|"low" }

Detects exceptional items in financial statements and sets data confidence.
Does NOT modify the raw data — only annotates it.
"""

from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sorted_periods(annual_5yr: dict) -> List[Tuple[str, dict]]:
    """Return (date, period) tuples sorted newest-first."""
    return sorted(annual_5yr.items(), key=lambda x: x[0], reverse=True)


def _safe_rate(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------------
# Exception detectors — each returns a flag dict or None
# ---------------------------------------------------------------------------

def _check_tax_anomaly(date: str, period: dict) -> Optional[dict]:
    rate = _safe_rate(period.get("tax"), period.get("pretax_income"))
    if rate is None:
        return None
    if rate < 0 or rate > 0.55:
        return {
            "type": "TAX_ANOMALY",
            "period": date,
            "description": f"Effective tax rate {rate:.1%} is outside 0–55% — possible deferred tax or one-time item.",
            "severity": "warn",
        }
    return None


def _check_ebit_pat_divergence(date: str, period: dict) -> Optional[dict]:
    revenue = period.get("revenue")
    ebit = period.get("ebit")
    net_income = period.get("net_income")
    if not all([revenue, ebit, net_income]) or revenue == 0:
        return None
    gap = (ebit - net_income) / abs(revenue)
    if abs(gap) > 0.15:
        return {
            "type": "EXCEPTIONAL_ITEMS_DETECTED",
            "period": date,
            "description": (
                f"EBIT and PAT margins diverge by {gap:.1%} — likely large below-the-line items "
                "(impairments, write-offs, or one-time gains)."
            ),
            "severity": "warn",
        }
    return None


def _check_revenue_jump(date: str, period: dict, prior: dict) -> Optional[dict]:
    revenue = period.get("revenue")
    prior_rev = prior.get("revenue")
    if not revenue or not prior_rev or prior_rev == 0:
        return None
    yoy = (revenue - prior_rev) / abs(prior_rev)
    if abs(yoy) > 0.30:
        direction = "increased" if yoy > 0 else "declined"
        return {
            "type": "LARGE_REVENUE_CHANGE",
            "period": date,
            "description": (
                f"Revenue {direction} {yoy:.1%} YoY — possible M&A, divestiture, or restatement. "
                "Trend ratios may not be comparable across periods."
            ),
            "severity": "warn",
        }
    return None


def _check_debt_spike(date: str, period: dict, prior: dict) -> Optional[dict]:
    debt = period.get("total_debt")
    prior_debt = prior.get("total_debt")
    if not debt or not prior_debt or prior_debt == 0:
        return None
    chg = (debt - prior_debt) / abs(prior_debt)
    if chg > 0.50:
        return {
            "type": "DEBT_SPIKE",
            "period": date,
            "description": f"Total debt rose {chg:.1%} YoY — possible large acquisition or refinancing event.",
            "severity": "warn",
        }
    return None


def _check_negative_ebitda(date: str, period: dict) -> Optional[dict]:
    ebitda = period.get("ebitda")
    revenue = period.get("revenue")
    if ebitda is None or not revenue or revenue <= 0:
        return None
    if ebitda < 0:
        return {
            "type": "NEGATIVE_EBITDA",
            "period": date,
            "description": f"EBITDA is negative in {date} despite positive revenue — operating loss.",
            "severity": "warn",
        }
    return None


def _check_negative_fcf(date: str, period: dict) -> Optional[dict]:
    fcf = period.get("free_cash_flow")
    if fcf is None or fcf >= 0:
        return None
    return {
        "type": "NEGATIVE_FCF",
        "period": date,
        "description": f"Free cash flow is negative in {date}.",
        "severity": "info",
    }


def _check_da_anomaly(date: str, period: dict) -> Optional[dict]:
    """Flag if D&A is implausibly large relative to revenue — may indicate impairment charge."""
    da = period.get("da")
    revenue = period.get("revenue")
    if not da or not revenue or revenue == 0:
        return None
    ratio = da / revenue
    if ratio > 0.30:
        return {
            "type": "LARGE_DA",
            "period": date,
            "description": f"D&A is {ratio:.1%} of revenue in {date} — possible impairment or accelerated depreciation.",
            "severity": "warn",
        }
    return None


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------

def normalise(raw: dict) -> dict:
    """
    Annotate raw data_fetcher output with exceptional item flags and confidence score.

    Output contract:
    {
        ...all raw fields,
        adjusted:   {},          # reserved for future quantitative adjustments
        flags:      [ { type, period, description, severity }, ... ],
        confidence: "high" | "medium" | "low"
    }
    """
    annual = raw.get("annual_5yr", {})
    periods = _sorted_periods(annual)
    flags: List[dict] = []

    # Data availability check
    n = len(periods)
    if n < 4:
        flags.append({
            "type": "INSUFFICIENT_HISTORY",
            "period": None,
            "description": (
                f"Only {n} annual period(s) available. "
                "CAGRs and multi-year trends will be truncated."
            ),
            "severity": "warn",
        })

    # Per-period checks
    for i, (date, period) in enumerate(periods):
        for checker in [_check_tax_anomaly, _check_ebit_pat_divergence,
                        _check_negative_ebitda, _check_negative_fcf, _check_da_anomaly]:
            result = checker(date, period)
            if result:
                flags.append(result)

        # Comparative checks (need prior period)
        if i < len(periods) - 1:
            prior_date, prior = periods[i + 1]
            for checker in [_check_revenue_jump, _check_debt_spike]:
                result = checker(date, period, prior)
                if result:
                    flags.append(result)

    # Confidence scoring
    warn_flags = [f for f in flags if f["severity"] in ("warn",)]
    if n >= 4 and len(warn_flags) == 0:
        confidence = "high"
    elif n >= 3 and len(warn_flags) <= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        **raw,
        "adjusted": {},
        "flags": flags,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, ".")
    from data_fetcher import fetch

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    market = sys.argv[2] if len(sys.argv) > 2 else "US"

    print(f"\nFetching + normalising {ticker} ...")
    raw = fetch(ticker, market)
    result = normalise(raw)

    print(f"\n  Confidence: {result['confidence'].upper()}")
    print(f"  Flags ({len(result['flags'])}):")
    for f in result["flags"]:
        print(f"    [{f['severity'].upper()}] {f['type']} {f.get('period') or ''}")
        print(f"      {f['description']}")

    out = f"{ticker.replace('.', '_')}_normalised.json"
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"\n  Saved -> {out}")
