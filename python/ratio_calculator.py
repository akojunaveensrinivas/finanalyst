"""
ratio_calculator.py
Input:  normalised dict from normaliser.normalise()
Output: {
    ratios:      { name: RatioResult },
    trends:      { name: [float|None, ...] },   # newest-first, 5 values
    inflections: [ { type, period, description } ],
    signals:     { rag: "red"|"amber"|"green", direction: "improving"|"stable"|"deteriorating" }
}

Implements all 26 ratios with 4-type validation:
  NULL GUARD | ZERO DENOMINATOR | SANITY BOUNDS | CURRENCY TAG
"""

import math
import statistics
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Callable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# (min_expected, max_expected) — values outside this range get SANITY_FLAG
SANITY_BOUNDS: Dict[str, Tuple[float, float]] = {
    "ev_ebitda":             (-2,    80),
    "debt_ebitda":           (-1,    15),
    "interest_coverage":     (-50,  200),
    "revenue_cagr_5yr":      (-0.9,   5),
    "ebitda_margin":         (-1,     1),
    "ebit_margin":           (-1,     1),
    "ev_revenue":            (-1,    50),
    "pe_ratio":              (-50,  500),
    "debt_equity":           (-5,    30),
    "roic":                  (-2,     5),
    "roce":                  (-2,     5),
    "roe":                   (-5,     5),
    "debt_to_assets":        (-0.5,   3),
    "fcf_conversion":        (-10,   10),
    "working_capital_days":  (-730, 1460),
    "current_ratio":         (0,     20),
    "quick_ratio":           (0,     20),
    "capex_revenue":         (0,      2),
    "pat_margin":            (-2,     2),
    "gross_margin":          (-0.5,   1),
    "gross_margin_stability": (0,    0.5),
    "accrual_ratio":         (-2,     2),
    "fcf_yield":             (-1,     1),
    "shareholder_yield":     (-0.5,   1),
    "revenue_cagr_3yr":      (-0.9,   5),
    "operating_leverage":    (-20,   20),
    "pb_ratio":              (-5,   100),
    "dividend_consistency":  (0,      1),
}

# (threshold_green, threshold_amber, higher_is_better)
# For higher_is_better=True:  green if value >= t_green, amber if >= t_amber, else red
# For higher_is_better=False: green if value <= t_green, amber if <= t_amber, else red
RAG_THRESHOLDS: Dict[str, Tuple[float, float, bool]] = {
    "ev_ebitda":             (10,    15,    False),
    "debt_ebitda":           (2,     4,     False),
    "interest_coverage":     (5,     3,     True),
    "revenue_cagr_5yr":      (0.10,  0.05,  True),
    "ebitda_margin":         (0.20,  0.10,  True),
    "ebit_margin":           (0.15,  0.08,  True),
    "ev_revenue":            (3,     6,     False),
    "pe_ratio":              (20,    35,    False),
    "debt_equity":           (0.5,   1.5,   False),
    "roic":                  (0.15,  0.08,  True),
    "roce":                  (0.15,  0.08,  True),
    "roe":                   (0.15,  0.08,  True),
    "debt_to_assets":        (0.40,  0.60,  False),
    "fcf_conversion":        (0.80,  0.50,  True),
    "current_ratio":         (1.5,   1.0,   True),
    "quick_ratio":           (1.0,   0.70,  True),
    "capex_revenue":         (0.05,  0.15,  False),
    "pat_margin":            (0.15,  0.08,  True),
    "gross_margin":          (0.40,  0.20,  True),
    "gross_margin_stability": (0.02, 0.05,  False),  # std dev; lower = more stable
    "accrual_ratio":         (0.05,  0.15,  False),  # absolute value used in rag()
    "fcf_yield":             (0.05,  0.02,  True),
    "shareholder_yield":     (0.05,  0.02,  True),
    "revenue_cagr_3yr":      (0.10,  0.05,  True),
    "operating_leverage":    (2.0,   3.0,   False),  # absolute value; lower = more stable
    "pb_ratio":              (3,     6,     False),
    "dividend_consistency":  (0.80,  0.50,  True),
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _safe_div(num: Optional[float], denom: Optional[float]) -> Optional[float]:
    if num is None or denom is None or denom == 0:
        return None
    result = num / denom
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _cagr(start: Optional[float], end: Optional[float], years: float) -> Optional[float]:
    """CAGR from start to end over `years` periods. Both must be same-sign and > 0."""
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _yoy(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _n_years(date1: str, date2: str) -> float:
    """Fractional years between two ISO date strings."""
    try:
        d1 = datetime.fromisoformat(date1)
        d2 = datetime.fromisoformat(date2)
        return abs((d2 - d1).days) / 365.25
    except Exception:
        return 1.0


def _rag(name: str, value: Optional[float]) -> Optional[str]:
    if value is None or name not in RAG_THRESHOLDS:
        return None
    t_green, t_amber, higher_is_better = RAG_THRESHOLDS[name]

    # Accrual ratio and operating leverage use absolute values for RAG
    v = abs(value) if name in ("accrual_ratio", "operating_leverage") else value

    if higher_is_better:
        if v >= t_green:
            return "green"
        if v >= t_amber:
            return "amber"
        return "red"
    else:
        if v <= t_green:
            return "green"
        if v <= t_amber:
            return "amber"
        return "red"


def _direction(values: List[Optional[float]], name: str) -> Optional[str]:
    """Trend direction from list of values (newest-first). Requires >= 2 non-null."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    latest = clean[0]
    older_avg = statistics.mean(clean[1:])
    if older_avg == 0:
        return None
    diff_pct = (latest - older_avg) / abs(older_avg)
    if abs(diff_pct) < 0.05:
        return "stable"
    higher_is_better = RAG_THRESHOLDS.get(name, (None, None, True))[2]
    if higher_is_better:
        return "improving" if diff_pct > 0 else "deteriorating"
    else:
        return "improving" if diff_pct < 0 else "deteriorating"


def _format_display(value: Optional[float], unit: str, reason: Optional[str]) -> str:
    if value is None:
        return reason or "N/A"
    if unit == "%":
        return f"{value * 100:.1f}%"
    if unit == "x":
        return f"{value:.1f}x"
    if unit == "days":
        return f"{int(round(value))} days"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:.2f}"


def _validate_sanity(name: str, value: Optional[float]) -> Optional[str]:
    if value is None or name not in SANITY_BOUNDS:
        return None
    lo, hi = SANITY_BOUNDS[name]
    if value < lo or value > hi:
        return f"SANITY_FLAG: {value:.2f} outside expected range [{lo}, {hi}]"
    return None


# ---------------------------------------------------------------------------
# Period extraction
# ---------------------------------------------------------------------------

def _sorted_periods(annual_5yr: dict) -> List[Tuple[str, dict]]:
    return sorted(annual_5yr.items(), key=lambda x: x[0], reverse=True)


def _get(period: dict, *keys: str) -> Optional[float]:
    """Return first non-None value from the period dict among given keys."""
    for k in keys:
        v = period.get(k)
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------------
# Single-ratio builder
# ---------------------------------------------------------------------------

def _build(
    name: str,
    unit: str,
    lens: List[str],
    periods: List[Tuple[str, dict]],
    market_data: dict,
    compute: Callable[[dict, dict], Optional[float]],
    market_dependent: bool = False,
) -> dict:
    """
    Build a full RatioResult dict for one ratio.
    compute(period, market_data) -> float | None
    market_dependent: if True, values_5yr only contains the current value.
    """
    currency = market_data.get("currency", "USD")

    if market_dependent:
        # Only compute for the most recent period
        current_val = compute(periods[0][1], market_data) if periods else None
        values_5yr = [current_val]
        yoy_pct = None
    else:
        values_5yr = []
        for _, p in periods:
            try:
                v = compute(p, market_data)
            except Exception:
                v = None
            values_5yr.append(v)
        current_val = values_5yr[0] if values_5yr else None
        prior_val = values_5yr[1] if len(values_5yr) > 1 else None
        yoy_pct = _yoy(current_val, prior_val)

    # Validation chain
    flag = _validate_sanity(name, current_val)
    reason = flag if flag else None

    return {
        "name":       name,
        "value":      current_val,
        "unit":       unit,
        "display":    _format_display(current_val, unit, reason),
        "currency":   currency,
        "rag":        _rag(name, current_val),
        "direction":  _direction(values_5yr, name),
        "flag":       flag,
        "reason":     reason,
        "values_5yr": values_5yr,
        "yoy_pct":    yoy_pct if not market_dependent else None,
        "lens":       lens,
    }


# ---------------------------------------------------------------------------
# Compute functions — one per ratio
# ---------------------------------------------------------------------------

# ── IB ──────────────────────────────────────────────────────────────────────

def _ev_ebitda(p: dict, md: dict) -> Optional[float]:
    return _safe_div(md.get("ev"), _get(p, "ebitda"))

def _debt_ebitda(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "total_debt"), _get(p, "ebitda"))

def _interest_coverage(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "ebit"), _get(p, "interest_expense"))

def _ebitda_margin(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "ebitda"), _get(p, "revenue"))

def _ebit_margin(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "ebit"), _get(p, "revenue"))

def _ev_revenue(p: dict, md: dict) -> Optional[float]:
    return _safe_div(md.get("ev"), _get(p, "revenue"))

def _pe_ratio(p: dict, md: dict) -> Optional[float]:
    # Use market P/E directly; fallback to price/eps
    if md.get("pe_ratio") is not None:
        return md["pe_ratio"]
    price = md.get("price")
    eps = _get(p, "eps_diluted", "eps_basic")
    return _safe_div(price, eps)

def _debt_equity(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "total_debt"), _get(p, "total_equity"))

# Revenue CAGR is computed separately (needs multiple periods)

# ── Corporate Finance ────────────────────────────────────────────────────────

def _roic(p: dict, md: dict) -> Optional[float]:
    ebit = _get(p, "ebit")
    pretax = _get(p, "pretax_income")
    tax = _get(p, "tax")
    if ebit is None:
        return None
    if pretax and pretax != 0 and tax is not None:
        tax_rate = max(0.0, min(0.50, tax / pretax))
    else:
        tax_rate = 0.25  # default assumption
    nopat = ebit * (1 - tax_rate)
    ic = _get(p, "invested_capital")
    if ic is None:
        equity = _get(p, "total_equity")
        debt = _get(p, "total_debt")
        cash = _get(p, "cash", "cash_and_equivalents")
        if equity is None or debt is None:
            return None
        ic = equity + debt - (cash or 0)
    return _safe_div(nopat, ic)

def _roce(p: dict, md: dict) -> Optional[float]:
    ebit = _get(p, "ebit")
    assets = _get(p, "total_assets")
    curr_liab = _get(p, "current_liabilities")
    if ebit is None or assets is None or curr_liab is None:
        return None
    ce = assets - curr_liab
    return _safe_div(ebit, ce)

def _roe(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "net_income"), _get(p, "total_equity"))

def _debt_to_assets(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "total_debt"), _get(p, "total_assets"))

def _fcf_conversion(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "free_cash_flow"), _get(p, "net_income"))

def _working_capital_days(p: dict, md: dict) -> Optional[float]:
    ca = _get(p, "current_assets")
    cl = _get(p, "current_liabilities")
    rev = _get(p, "revenue")
    if ca is None or cl is None or rev is None or rev == 0:
        return None
    wc = ca - cl
    return (wc / rev) * 365

def _current_ratio(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "current_assets"), _get(p, "current_liabilities"))

def _quick_ratio(p: dict, md: dict) -> Optional[float]:
    ca = _get(p, "current_assets")
    inv = _get(p, "inventory") or 0.0
    cl = _get(p, "current_liabilities")
    if ca is None or cl is None:
        return None
    return _safe_div(ca - inv, cl)

def _capex_revenue(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "capex"), _get(p, "revenue"))

def _pat_margin(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "net_income"), _get(p, "revenue"))

# ── Investor ─────────────────────────────────────────────────────────────────

def _gross_margin(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "gross_profit"), _get(p, "revenue"))

def _accrual_ratio(p: dict, md: dict) -> Optional[float]:
    net_income = _get(p, "net_income")
    ocf = _get(p, "operating_cash_flow")
    assets = _get(p, "total_assets")
    if net_income is None or ocf is None or assets is None or assets == 0:
        return None
    return (net_income - ocf) / assets

def _fcf_yield(p: dict, md: dict) -> Optional[float]:
    return _safe_div(_get(p, "free_cash_flow"), md.get("market_cap"))

def _shareholder_yield(p: dict, md: dict) -> Optional[float]:
    buybacks = _get(p, "buybacks") or 0.0
    divs = _get(p, "dividends_paid") or 0.0
    mcap = md.get("market_cap")
    if mcap is None or mcap == 0:
        return None
    return (abs(buybacks) + abs(divs)) / mcap

def _pb_ratio(p: dict, md: dict) -> Optional[float]:
    if md.get("pb_ratio") is not None:
        return md["pb_ratio"]
    price = md.get("price")
    bvps = md.get("book_value_per_share")
    return _safe_div(price, bvps)

def _dividend_consistency(p: dict, md: dict) -> Optional[float]:
    # Returns None here; aggregated separately across all periods
    return None

def _operating_leverage_compute(current: dict, prior: dict) -> Optional[float]:
    """Point-in-time operating leverage: %ΔEBIT / %ΔRevenue."""
    ebit_now = _get(current, "ebit")
    ebit_prior = _get(prior, "ebit")
    rev_now = _get(current, "revenue")
    rev_prior = _get(prior, "revenue")
    if any(v is None for v in [ebit_now, ebit_prior, rev_now, rev_prior]):
        return None
    if ebit_prior == 0 or rev_prior == 0:
        return None
    pct_ebit = (ebit_now - ebit_prior) / abs(ebit_prior)
    pct_rev = (rev_now - rev_prior) / abs(rev_prior)
    return _safe_div(pct_ebit, pct_rev)


# ---------------------------------------------------------------------------
# Multi-period special ratios
# ---------------------------------------------------------------------------

def _calc_revenue_cagr(periods: List[Tuple[str, dict]], n_years_target: int) -> dict:
    """Build a CAGR ratio result for revenue over n_years_target (3 or 5)."""
    name = f"revenue_cagr_{n_years_target}yr"
    rev_series = [(date, _get(p, "revenue")) for date, p in periods]
    rev_series = [(d, v) for d, v in rev_series if v is not None]

    current_val = None
    if len(rev_series) >= 2:
        newest_date, newest_rev = rev_series[0]
        # Pick the point closest to n_years_target years back
        target_idx = min(n_years_target, len(rev_series) - 1)
        oldest_date, oldest_rev = rev_series[target_idx]
        years = _n_years(oldest_date, newest_date)
        current_val = _cagr(oldest_rev, newest_rev, years)

    values_5yr = []
    for i in range(len(periods)):
        if i + 1 < len(rev_series):
            d_new, v_new = rev_series[i]
            d_old, v_old = rev_series[i + 1]
            yr = _n_years(d_old, d_new)
            values_5yr.append(_cagr(v_old, v_new, yr))
        else:
            values_5yr.append(None)

    flag = _validate_sanity(name, current_val)
    return {
        "name":       name,
        "value":      current_val,
        "unit":       "%",
        "display":    _format_display(current_val, "%", flag),
        "currency":   "N/A",
        "rag":        _rag(name, current_val),
        "direction":  _direction(values_5yr, name),
        "flag":       flag,
        "reason":     flag,
        "values_5yr": values_5yr,
        "yoy_pct":    None,
        "lens":       ["ib"] if n_years_target == 5 else ["investor"],
    }


def _calc_gross_margin_stability(periods: List[Tuple[str, dict]], market_data: dict) -> dict:
    """Standard deviation of gross margin over available history."""
    name = "gross_margin_stability"
    gms = [_gross_margin(p, market_data) for _, p in periods]
    gms_clean = [v for v in gms if v is not None]

    current_val = None
    if len(gms_clean) >= 2:
        current_val = statistics.stdev(gms_clean)

    flag = _validate_sanity(name, current_val)
    return {
        "name":       name,
        "value":      current_val,
        "unit":       "%",
        "display":    _format_display(current_val, "%", flag),
        "currency":   "N/A",
        "rag":        _rag(name, current_val),
        "direction":  None,  # stability score has no directional trend
        "flag":       flag,
        "reason":     flag,
        "values_5yr": gms,   # underlying gross margins for chart
        "yoy_pct":    None,
        "lens":       ["investor"],
    }


def _calc_operating_leverage(periods: List[Tuple[str, dict]], market_data: dict) -> dict:
    """Operating leverage per year (needs consecutive pairs)."""
    name = "operating_leverage"
    values_5yr = []
    for i in range(len(periods) - 1):
        v = _operating_leverage_compute(periods[i][1], periods[i + 1][1])
        values_5yr.append(v)
    values_5yr.append(None)  # pad to same length as periods

    current_val = values_5yr[0] if values_5yr else None
    flag = _validate_sanity(name, current_val)
    return {
        "name":       name,
        "value":      current_val,
        "unit":       "x",
        "display":    _format_display(current_val, "x", flag),
        "currency":   "N/A",
        "rag":        _rag(name, current_val),
        "direction":  _direction(values_5yr, name),
        "flag":       flag,
        "reason":     flag,
        "values_5yr": values_5yr,
        "yoy_pct":    None,
        "lens":       ["investor"],
    }


def _calc_dividend_consistency(periods: List[Tuple[str, dict]], market_data: dict) -> dict:
    """Fraction of available years in which dividends were paid."""
    name = "dividend_consistency"
    paid = []
    for _, p in periods:
        d = _get(p, "dividends_paid")
        paid.append(1.0 if (d is not None and abs(d) > 0) else 0.0)

    current_val = (sum(paid) / len(paid)) if paid else None
    flag = _validate_sanity(name, current_val)
    return {
        "name":       name,
        "value":      current_val,
        "unit":       "ratio",
        "display":    _format_display(current_val, "ratio", flag),
        "currency":   "N/A",
        "rag":        _rag(name, current_val),
        "direction":  None,
        "flag":       flag,
        "reason":     flag,
        "values_5yr": paid,
        "yoy_pct":    None,
        "lens":       ["investor"],
    }


# ---------------------------------------------------------------------------
# Inflection point detection
# ---------------------------------------------------------------------------

def _detect_inflections(periods: List[Tuple[str, dict]]) -> List[dict]:
    """
    Scan annual periods for three hard signals:
      1. Margin compression — EBITDA margin declining 2+ consecutive years
      2. Debt spike        — Debt/EBITDA rises > 1x in one year
      3. FCF turns negative — FCF flips from positive to negative
    """
    inflections = []
    n = len(periods)
    if n < 2:
        return inflections

    # Precompute per-period metrics (newest-first)
    ebitda_margins = []
    debt_ebitdas = []
    fcfs = []
    for date, p in periods:
        rev = _get(p, "revenue")
        ebitda = _get(p, "ebitda")
        debt = _get(p, "total_debt")
        fcf = _get(p, "free_cash_flow")
        ebitda_margins.append((date, _safe_div(ebitda, rev)))
        debt_ebitdas.append((date, _safe_div(debt, ebitda)))
        fcfs.append((date, fcf))

    # 1. Margin compression: 2+ consecutive declining years
    #    Periods are newest-first, so we look forward in the list (= backward in time)
    for i in range(len(ebitda_margins) - 2):
        d0, m0 = ebitda_margins[i]
        d1, m1 = ebitda_margins[i + 1]
        d2, m2 = ebitda_margins[i + 2]
        if m0 is not None and m1 is not None and m2 is not None:
            if m0 < m1 < m2:  # declining: oldest > prior > current
                inflections.append({
                    "type": "MARGIN_COMPRESSION",
                    "period": d0,
                    "description": (
                        f"EBITDA margin has compressed for 2+ consecutive years "
                        f"({m2:.1%} → {m1:.1%} → {m0:.1%})."
                    ),
                })
                break  # report once

    # 2. Debt spike: Debt/EBITDA rises > 1.0x in a single year
    for i in range(len(debt_ebitdas) - 1):
        d_now, de_now = debt_ebitdas[i]
        d_prior, de_prior = debt_ebitdas[i + 1]
        if de_now is not None and de_prior is not None and de_prior > 0:
            jump = de_now - de_prior
            if jump > 1.0:
                inflections.append({
                    "type": "DEBT_SPIKE",
                    "period": d_now,
                    "description": (
                        f"Debt/EBITDA jumped {jump:.1f}x in one year "
                        f"({de_prior:.1f}x → {de_now:.1f}x) — possible leveraged event."
                    ),
                })

    # 3. FCF turns negative
    for i in range(len(fcfs) - 1):
        d_now, fcf_now = fcfs[i]
        d_prior, fcf_prior = fcfs[i + 1]
        if fcf_now is not None and fcf_prior is not None:
            if fcf_now < 0 <= fcf_prior:
                inflections.append({
                    "type": "FCF_TURNED_NEGATIVE",
                    "period": d_now,
                    "description": (
                        f"Free cash flow turned negative in {d_now} "
                        f"(was {fcf_prior:,.0f} prior year)."
                    ),
                })

    return inflections


# ---------------------------------------------------------------------------
# Signal aggregation
# ---------------------------------------------------------------------------

def _aggregate_signals(ratios: dict) -> dict:
    """
    Roll up individual RAG scores into one portfolio-level signal.
    Direction is based on the majority direction across all ratios.
    """
    rag_scores = {"green": 0, "amber": 0, "red": 0}
    directions = {"improving": 0, "stable": 0, "deteriorating": 0}

    for r in ratios.values():
        rag = r.get("rag")
        if rag in rag_scores:
            rag_scores[rag] += 1
        direction = r.get("direction")
        if direction in directions:
            directions[direction] += 1

    total_rag = sum(rag_scores.values()) or 1
    green_pct = rag_scores["green"] / total_rag
    red_pct = rag_scores["red"] / total_rag

    if green_pct >= 0.60:
        overall_rag = "green"
    elif red_pct >= 0.40:
        overall_rag = "red"
    else:
        overall_rag = "amber"

    overall_dir = max(directions, key=directions.get)

    return {
        "rag": overall_rag,
        "direction": overall_dir,
        "rag_breakdown": rag_scores,
        "direction_breakdown": directions,
    }


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------

def calculate(normalised: dict) -> dict:
    """
    Calculate all 26 ratios from normalised financial data.

    Output contract:
    {
        ratios:      { name: RatioResult, ... },
        trends:      { name: [float|None, ...] },
        inflections: [ { type, period, description }, ... ],
        signals:     { rag, direction, rag_breakdown, direction_breakdown }
    }
    """
    annual = normalised.get("annual_5yr", {})
    market_data = normalised.get("market_data", {})
    periods = _sorted_periods(annual)

    ratios: Dict[str, dict] = {}

    # ── IB ratios ────────────────────────────────────────────────────────────
    ratios["ev_ebitda"] = _build(
        "ev_ebitda", "x", ["ib"], periods, market_data, _ev_ebitda, market_dependent=True)
    ratios["debt_ebitda"] = _build(
        "debt_ebitda", "x", ["ib"], periods, market_data, _debt_ebitda)
    ratios["interest_coverage"] = _build(
        "interest_coverage", "x", ["ib"], periods, market_data, _interest_coverage)
    ratios["ebitda_margin"] = _build(
        "ebitda_margin", "%", ["ib"], periods, market_data, _ebitda_margin)
    ratios["ebit_margin"] = _build(
        "ebit_margin", "%", ["ib"], periods, market_data, _ebit_margin)
    ratios["ev_revenue"] = _build(
        "ev_revenue", "x", ["ib"], periods, market_data, _ev_revenue, market_dependent=True)
    ratios["pe_ratio"] = _build(
        "pe_ratio", "x", ["ib"], periods, market_data, _pe_ratio, market_dependent=True)
    ratios["debt_equity"] = _build(
        "debt_equity", "x", ["ib"], periods, market_data, _debt_equity)
    ratios["revenue_cagr_5yr"] = _calc_revenue_cagr(periods, 5)

    # ── Corporate Finance ratios ─────────────────────────────────────────────
    ratios["roic"] = _build(
        "roic", "%", ["cf"], periods, market_data, _roic)
    ratios["roce"] = _build(
        "roce", "%", ["cf"], periods, market_data, _roce)
    ratios["roe"] = _build(
        "roe", "%", ["cf"], periods, market_data, _roe)
    ratios["debt_to_assets"] = _build(
        "debt_to_assets", "ratio", ["cf"], periods, market_data, _debt_to_assets)
    ratios["fcf_conversion"] = _build(
        "fcf_conversion", "ratio", ["cf"], periods, market_data, _fcf_conversion)
    ratios["working_capital_days"] = _build(
        "working_capital_days", "days", ["cf"], periods, market_data, _working_capital_days)
    ratios["current_ratio"] = _build(
        "current_ratio", "x", ["cf"], periods, market_data, _current_ratio)
    ratios["quick_ratio"] = _build(
        "quick_ratio", "x", ["cf"], periods, market_data, _quick_ratio)
    ratios["capex_revenue"] = _build(
        "capex_revenue", "%", ["cf"], periods, market_data, _capex_revenue)
    ratios["pat_margin"] = _build(
        "pat_margin", "%", ["cf"], periods, market_data, _pat_margin)

    # ── Investor ratios ──────────────────────────────────────────────────────
    ratios["gross_margin_stability"] = _calc_gross_margin_stability(periods, market_data)
    ratios["accrual_ratio"] = _build(
        "accrual_ratio", "ratio", ["investor"], periods, market_data, _accrual_ratio)
    ratios["fcf_yield"] = _build(
        "fcf_yield", "%", ["investor"], periods, market_data, _fcf_yield, market_dependent=True)
    ratios["shareholder_yield"] = _build(
        "shareholder_yield", "%", ["investor"], periods, market_data, _shareholder_yield, market_dependent=True)
    ratios["revenue_cagr_3yr"] = _calc_revenue_cagr(periods, 3)
    ratios["operating_leverage"] = _calc_operating_leverage(periods, market_data)
    ratios["pb_ratio"] = _build(
        "pb_ratio", "x", ["investor"], periods, market_data, _pb_ratio, market_dependent=True)
    ratios["dividend_consistency"] = _calc_dividend_consistency(periods, market_data)

    # Gross margin (underlying — used in stability; also useful standalone for investor)
    ratios["gross_margin"] = _build(
        "gross_margin", "%", ["investor"], periods, market_data, _gross_margin)

    # ── Derived trends dict ──────────────────────────────────────────────────
    trends = {name: r["values_5yr"] for name, r in ratios.items()}

    # ── Inflection detection ─────────────────────────────────────────────────
    inflections = _detect_inflections(periods)

    # ── Aggregate signals ────────────────────────────────────────────────────
    signals = _aggregate_signals(ratios)

    return {
        "ratios":      ratios,
        "trends":      trends,
        "inflections": inflections,
        "signals":     signals,
    }


# ---------------------------------------------------------------------------
# Test runner — python ratio_calculator.py [TICKER] [MARKET]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, ".")
    from data_fetcher import fetch
    from normaliser import normalise

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    market = sys.argv[2] if len(sys.argv) > 2 else "US"

    print(f"\nFetch → Normalise → Calculate: {ticker} ...")
    raw = fetch(ticker, market)
    norm = normalise(raw)
    result = calculate(norm)

    ratios = result["ratios"]
    print(f"\n{'Ratio':<28} {'Value':>12}  {'RAG':<8} {'Direction'}")
    print("-" * 65)
    for name, r in ratios.items():
        rag_str = (r["rag"] or "N/A").upper()[:5]
        dir_str = r["direction"] or "-"
        print(f"  {name:<26} {r['display']:>12}  {rag_str:<8} {dir_str}")

    print(f"\nOverall signal: {result['signals']['rag'].upper()} / {result['signals']['direction']}")
    print(f"RAG breakdown:  {result['signals']['rag_breakdown']}")

    print(f"\nInflection points ({len(result['inflections'])}):")
    for inf in result["inflections"]:
        print(f"  [{inf['type']}] {inf['period']}: {inf['description']}")

    out = f"{ticker.replace('.', '_')}_ratios.json"
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"\nFull output saved -> {out}")
