import yfinance as yf
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Field maps: yfinance label → our standard name
# Priority: first match wins (handles yfinance naming inconsistencies)
# ---------------------------------------------------------------------------

INCOME_FIELDS = {
    "Total Revenue": "revenue",
    "Gross Profit": "gross_profit",
    "Operating Income": "ebit",
    "EBIT": "ebit",
    "EBITDA": "ebitda",
    "Net Income": "net_income",
    "Interest Expense": "interest_expense",
    "Interest Expense Non Operating": "interest_expense",
    "Tax Provision": "tax",
    "Pretax Income": "pretax_income",
    "Basic EPS": "eps_basic",
    "Diluted EPS": "eps_diluted",
    "Reconciled Depreciation": "da",
    "Depreciation And Amortization": "da",
    "Selling General And Administration": "sga",
    "Research And Development": "rd",
    "Total Operating Expenses": "total_opex",
}

BALANCE_FIELDS = {
    "Total Assets": "total_assets",
    "Total Liabilities Net Minority Interest": "total_liabilities",
    "Stockholders Equity": "total_equity",
    "Common Stock Equity": "total_equity",
    "Total Debt": "total_debt",
    "Net Debt": "net_debt",
    "Cash And Cash Equivalents": "cash",
    "Cash Cash Equivalents And Short Term Investments": "cash_and_equivalents",
    "Current Assets": "current_assets",
    "Current Liabilities": "current_liabilities",
    "Inventory": "inventory",
    "Receivables": "accounts_receivable",
    "Accounts Receivable": "accounts_receivable",
    "Accounts Payable": "accounts_payable",
    "Long Term Debt": "long_term_debt",
    "Short Long Term Debt": "short_term_debt",
    "Capital Lease Obligations": "lease_obligations",
    "Invested Capital": "invested_capital",
    "Working Capital": "working_capital",
    "Net PPE": "net_ppe",
    "Goodwill And Other Intangible Assets": "goodwill_intangibles",
    "Retained Earnings": "retained_earnings",
}

CASHFLOW_FIELDS = {
    "Operating Cash Flow": "operating_cash_flow",
    "Capital Expenditure": "capex",
    "Free Cash Flow": "free_cash_flow",
    "Depreciation Amortization Depletion": "da",
    "Depreciation And Amortization": "da",
    "Dividends Paid": "dividends_paid",
    "Payment Of Dividends And Other Cash Distributions": "dividends_paid",
    "Common Stock Dividend Paid": "dividends_paid",
    "Cash Dividends Paid Total": "dividends_paid",
    "Repurchase Of Capital Stock": "buybacks",
    "Repurchase Of Common Stock": "buybacks",
    "Common Stock Repurchase": "buybacks",
    "Common Stock Issuance": "stock_issuance",
    "Investing Cash Flow": "investing_cash_flow",
    "Financing Cash Flow": "financing_cash_flow",
    "Changes In Working Capital": "working_capital_change",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(val) -> Optional[float]:
    """Convert any yfinance value to float or None. Never NaN/Inf."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _process_statement(df: pd.DataFrame, field_map: dict, max_periods: int) -> dict:
    """
    Convert a yfinance statement DataFrame into a period-keyed dict.
    Columns are dates (most recent first). Rows are line items.
    """
    if df is None or df.empty:
        return {}

    df = df.iloc[:, :max_periods]
    periods = {}

    for col in df.columns:
        period_key = col.strftime("%Y-%m-%d") if isinstance(col, pd.Timestamp) else str(col)
        period_data = {}

        for yf_name, our_name in field_map.items():
            if yf_name in df.index and our_name not in period_data:
                val = _clean(df.loc[yf_name, col])
                if val is not None:
                    period_data[our_name] = val

        if period_data:
            periods[period_key] = period_data

    return periods


def _merge_periods(income: dict, balance: dict, cashflow: dict, max_n: int, currency: str) -> dict:
    """Merge three statement dicts by date key. Derive EBITDA and FCF where missing."""
    all_dates = set(income) | set(balance) | set(cashflow)
    merged_all = {}

    for date in sorted(all_dates, reverse=True)[:max_n]:
        d = {}
        # Layer order: cashflow < balance < income (income wins on overlaps)
        d.update(cashflow.get(date, {}))
        d.update(balance.get(date, {}))
        d.update(income.get(date, {}))

        # Derive EBITDA if not directly available
        if "ebitda" not in d and "ebit" in d and "da" in d:
            d["ebitda"] = d["ebit"] + d["da"]

        # Normalise capex to positive
        if "capex" in d and d["capex"] is not None and d["capex"] < 0:
            d["capex"] = abs(d["capex"])

        # Derive FCF if not directly available
        if "free_cash_flow" not in d:
            ocf = d.get("operating_cash_flow")
            capex = d.get("capex")
            if ocf is not None and capex is not None:
                d["free_cash_flow"] = ocf - capex

        # Tag currency on every period
        d["currency"] = currency
        merged_all[date] = d

    return merged_all


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------

def fetch(ticker: str, market: str = "US") -> dict:
    """
    Fetch financial data for a ticker symbol.

    Output contract:
    {
        ticker:       str,
        market:       str,
        currency:     str,
        annual_5yr:   { "YYYY-MM-DD": { field: value, ... }, ... },
        quarterly_8q: { "YYYY-MM-DD": { field: value, ... }, ... },
        market_data:  { price, market_cap, ev, pe_ratio, ... },
        fetched_at:   ISO 8601 UTC string
    }
    """
    t = yf.Ticker(ticker)
    info = t.info or {}
    currency = info.get("currency", "USD")

    # Fetch all six statement DataFrames
    annual_income   = _process_statement(t.financials,            INCOME_FIELDS,   5)
    annual_balance  = _process_statement(t.balance_sheet,         BALANCE_FIELDS,  5)
    annual_cashflow = _process_statement(t.cashflow,              CASHFLOW_FIELDS, 5)

    q_income   = _process_statement(t.quarterly_financials,    INCOME_FIELDS,   8)
    q_balance  = _process_statement(t.quarterly_balance_sheet, BALANCE_FIELDS,  8)
    q_cashflow = _process_statement(t.quarterly_cashflow,      CASHFLOW_FIELDS, 8)

    annual_5yr   = _merge_periods(annual_income, annual_balance, annual_cashflow, 5, currency)
    quarterly_8q = _merge_periods(q_income,      q_balance,      q_cashflow,      8, currency)

    market_data = {
        "price":                   _clean(info.get("currentPrice") or info.get("regularMarketPrice")),
        "market_cap":              _clean(info.get("marketCap")),
        "ev":                      _clean(info.get("enterpriseValue")),
        "shares_outstanding":      _clean(info.get("sharesOutstanding")),
        "float_shares":            _clean(info.get("floatShares")),
        "pe_ratio":                _clean(info.get("trailingPE")),
        "forward_pe":              _clean(info.get("forwardPE")),
        "pb_ratio":                _clean(info.get("priceToBook")),
        "book_value_per_share":    _clean(info.get("bookValue")),
        "dividend_yield":          _clean(info.get("dividendYield")),
        "trailing_dividend_yield": _clean(info.get("trailingAnnualDividendYield")),
        "beta":                    _clean(info.get("beta")),
        "52w_high":                _clean(info.get("fiftyTwoWeekHigh")),
        "52w_low":                 _clean(info.get("fiftyTwoWeekLow")),
        "company_name":            info.get("longName") or info.get("shortName"),
        "sector":                  info.get("sector"),
        "industry":                info.get("industry"),
        "exchange":                info.get("exchange"),
        "country":                 info.get("country"),
        "currency":                currency,
        "employees":               info.get("fullTimeEmployees"),
        "description":             info.get("longBusinessSummary"),
    }

    return {
        "ticker":       ticker,
        "market":       market,
        "currency":     currency,
        "annual_5yr":   annual_5yr,
        "quarterly_8q": quarterly_8q,
        "market_data":  market_data,
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Test runner — python data_fetcher.py [TICKER] [MARKET]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    market = sys.argv[2] if len(sys.argv) > 2 else "US"

    print(f"\nFetching: {ticker} ({market}) ...")
    result = fetch(ticker, market)

    md = result["market_data"]
    print(f"\n  Company:    {md.get('company_name')}")
    print(f"  Currency:   {result['currency']}")
    print(f"  Price:      {md.get('price')}")
    print(f"  Market Cap: {md.get('market_cap'):,.0f}" if md.get("market_cap") else "  Market Cap: N/A")
    print(f"  EV:         {md.get('ev'):,.0f}" if md.get("ev") else "  EV:         N/A")
    print(f"\n  Annual periods:    {list(result['annual_5yr'].keys())}")
    print(f"  Quarterly periods: {list(result['quarterly_8q'].keys())}")

    if result["annual_5yr"]:
        latest_key = list(result["annual_5yr"].keys())[0]
        latest = result["annual_5yr"][latest_key]
        key_fields = [
            "revenue", "gross_profit", "ebit", "ebitda",
            "net_income", "operating_cash_flow", "free_cash_flow",
            "capex", "total_debt", "total_equity", "total_assets",
            "current_assets", "current_liabilities", "da",
        ]
        print(f"\n  Latest annual ({latest_key}):")
        for f in key_fields:
            val = latest.get(f)
            if val is not None:
                print(f"    {f:<30} {val:>20,.0f}  {latest.get('currency', '')}")
            else:
                print(f"    {f:<30} {'N/A':>20}")

    out_file = f"{ticker.replace('.', '_')}_raw.json"
    with open(out_file, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"\n  Full output saved -> {out_file}")
