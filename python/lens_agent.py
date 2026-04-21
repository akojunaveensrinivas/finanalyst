"""
lens_agent.py
Input:  lens name + normalised dict + ratio_result dict + audit_result dict
Output: {
    lens, ticker, status, summary, sections, confidence_scores,
    deal_context?, deal_signal?, risks?,  generated_at, model
}

Calls Claude API with the appropriate skill file and web search tool.
Handles the full tool-use loop for live comp/news lookup.
"""

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
MAX_TOKENS = 8192
SKILLS_DIR = Path(__file__).parent.parent / "skills"

LENS_TO_SKILL = {
    "ib":       "ib.md",
    "cf":       "cf.md",
    "investor": "investor.md",
}

LENS_RATIO_KEYS = {
    "ib": [
        "ev_ebitda", "debt_ebitda", "interest_coverage", "revenue_cagr_5yr",
        "ebitda_margin", "ebit_margin", "ev_revenue", "pe_ratio", "debt_equity",
    ],
    "cf": [
        "roic", "roce", "roe", "debt_to_assets", "fcf_conversion",
        "working_capital_days", "current_ratio", "quick_ratio",
        "capex_revenue", "pat_margin",
    ],
    "investor": [
        "gross_margin_stability", "accrual_ratio", "fcf_yield", "shareholder_yield",
        "revenue_cagr_3yr", "revenue_cagr_5yr", "operating_leverage", "pb_ratio",
        "dividend_consistency", "gross_margin",
    ],
}


# ---------------------------------------------------------------------------
# Web search (duckduckgo — free, no API key)
# ---------------------------------------------------------------------------

def _web_search(query: str, max_results: int = 5) -> str:
    """Execute a web search. Returns formatted text results."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results found for: {query}"
        lines = [f"Search: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')[:300]}")
            lines.append("")
        return "\n".join(lines)
    except ImportError:
        return (
            f"[Web search unavailable — duckduckgo_search not installed. "
            f"Query was: {query}. Install with: pip install duckduckgo-search]"
        )
    except Exception as e:
        return f"[Search error for '{query}': {str(e)}]"


# ---------------------------------------------------------------------------
# Tool definition for Claude
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for live financial data, comparable company multiples, "
        "recent news, and sector benchmarks. Use this for peer valuation data "
        "and recent company news."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific — include company name, metric, and year.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1–10). Default 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Context builder — what Claude sees about the company
# ---------------------------------------------------------------------------

def _build_financial_context(
    lens: str,
    normalised: dict,
    ratio_result: dict,
    audit_result: dict,
) -> str:
    """Build the financial context string passed to Claude as the user message."""

    ticker = normalised.get("ticker", "UNKNOWN")
    market = normalised.get("market", "")
    currency = normalised.get("currency", "USD")
    confidence = normalised.get("confidence", "unknown")
    md = normalised.get("market_data", {})
    ratios = ratio_result.get("ratios", {})
    inflections = ratio_result.get("inflections", [])
    signals = ratio_result.get("signals", {})
    flags = normalised.get("flags", [])

    lines = [
        f"# Company Financial Data",
        f"",
        f"**Ticker:** {ticker}  **Market:** {market}  **Currency:** {currency}",
        f"**Company:** {md.get('company_name', 'N/A')}",
        f"**Sector:** {md.get('sector', 'N/A')}  **Industry:** {md.get('industry', 'N/A')}",
        f"**Country:** {md.get('country', 'N/A')}",
        f"",
        f"## Market Data (current)",
        f"- Price: {md.get('price', 'N/A')} {currency}",
        f"- Market Cap: {_fmt(md.get('market_cap'))} {currency}",
        f"- Enterprise Value: {_fmt(md.get('ev'))} {currency}",
        f"- Shares Outstanding: {_fmt(md.get('shares_outstanding'))}",
        f"- 52-week High: {md.get('52w_high', 'N/A')}  Low: {md.get('52w_low', 'N/A')}",
        f"- Beta: {md.get('beta', 'N/A')}",
        f"",
        f"## Data Quality",
        f"- Normaliser confidence: {confidence.upper()}",
        f"- Audit status: {audit_result.get('status', 'N/A')}",
        f"- Annual periods available: {len(normalised.get('annual_5yr', {}))}",
    ]

    if flags:
        lines.append(f"- Flags: {len(flags)} item(s) noted")
        for f in flags[:3]:
            lines.append(f"  * [{f.get('type')}] {f.get('description', '')[:120]}")

    lines += [
        f"",
        f"## Overall Signals",
        f"- Portfolio RAG: {signals.get('rag', 'N/A').upper()}",
        f"- Overall direction: {signals.get('direction', 'N/A')}",
        f"- RAG breakdown: {signals.get('rag_breakdown', {})}",
    ]

    if inflections:
        lines.append(f"")
        lines.append(f"## Inflection Points")
        for inf in inflections:
            lines.append(f"- [{inf['type']}] {inf['period']}: {inf['description']}")

    # Lens-specific ratios
    lens_keys = LENS_RATIO_KEYS.get(lens, list(ratios.keys()))
    lines += ["", f"## Ratios ({lens.upper()} lens)", ""]

    for key in lens_keys:
        r = ratios.get(key)
        if r is None:
            continue
        val = r.get("display", "N/A")
        rag = (r.get("rag") or "N/A").upper()
        direction = r.get("direction") or "N/A"
        yoy = r.get("yoy_pct")
        yoy_str = f"  YoY: {yoy:+.1%}" if yoy is not None else ""
        trend = r.get("values_5yr", [])
        trend_str = (
            "  5yr: [" + ", ".join(_fmt_v(v) for v in trend) + "]"
            if trend else ""
        )
        lines.append(f"- **{key}**: {val}  [{rag}] {direction}{yoy_str}{trend_str}")

    # Annual period summary (raw key financials)
    annual = normalised.get("annual_5yr", {})
    if annual:
        lines += ["", "## Annual Financials (newest first)", ""]
        key_fields = ["revenue", "gross_profit", "ebit", "ebitda", "net_income",
                      "operating_cash_flow", "free_cash_flow", "capex",
                      "total_debt", "total_equity", "total_assets",
                      "current_assets", "current_liabilities"]
        for date in sorted(annual.keys(), reverse=True):
            p = annual[date]
            lines.append(f"**{date}** ({currency})")
            for f in key_fields:
                v = p.get(f)
                if v is not None:
                    lines.append(f"  {f}: {v:,.0f}")
            lines.append("")

    return "\n".join(lines)


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"{v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M"
    return f"{v:,.0f}"


def _fmt_v(v) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


# ---------------------------------------------------------------------------
# Claude tool-use loop
# ---------------------------------------------------------------------------

def _run_claude(system_prompt: str, user_message: str) -> str:
    """
    Run a Claude conversation with web_search tool support.
    Returns the final text response (expected to be JSON).
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{"role": "user", "content": user_message}]

    for _iteration in range(10):  # max 10 tool-use rounds
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )

        # If no more tool calls, return the final text
        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_blocks)

        # Execute tool calls and collect results
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "web_search":
                query = block.input.get("query", "")
                max_r = block.input.get("max_results", 5)
                result_text = _web_search(query, max_r)
            else:
                result_text = f"[Unknown tool: {block.name}]"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    # Exhausted iterations — return whatever the last text was
    return "[Max tool iterations reached]"


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a Claude response string."""
    # Try to find a JSON block in markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a raw JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Return an error dict if all parsing fails
    return {
        "error": "JSON parse failed",
        "raw_response": text[:2000],
    }


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------

def analyse(
    lens: str,
    normalised: dict,
    ratio_result: dict,
    audit_result: dict,
) -> dict:
    """
    Run a lens agent analysis.

    Output contract:
    {
        lens, ticker, status, summary, sections,
        confidence_scores, deal_context?, deal_signal?,
        risks?, generated_at, model
    }
    """
    if lens not in LENS_TO_SKILL:
        return {
            "lens": lens,
            "status": "error",
            "error": f"Unknown lens '{lens}'. Valid: {list(LENS_TO_SKILL.keys())}",
        }

    # Load skill file
    skill_path = SKILLS_DIR / LENS_TO_SKILL[lens]
    try:
        system_prompt = skill_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "lens": lens,
            "status": "error",
            "error": f"Skill file not found: {skill_path}",
        }

    # Build financial context
    user_message = _build_financial_context(lens, normalised, ratio_result, audit_result)

    # Call Claude
    raw_response = _run_claude(system_prompt, user_message)

    # Parse JSON
    parsed = _extract_json(raw_response)

    # Enrich with metadata
    ticker = normalised.get("ticker", "UNKNOWN")
    parsed.update({
        "lens":         lens,
        "ticker":       ticker,
        "status":       "error" if "error" in parsed else "success",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model":        MODEL,
    })

    return parsed


# ---------------------------------------------------------------------------
# Test runner — python lens_agent.py [LENS] [TICKER] [MARKET]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from data_fetcher import fetch
    from normaliser import normalise
    from ratio_calculator import calculate
    from audit_agent import audit

    lens   = sys.argv[1] if len(sys.argv) > 1 else "ib"
    ticker = sys.argv[2] if len(sys.argv) > 2 else "TCS.NS"
    market = sys.argv[3] if len(sys.argv) > 3 else "IN"

    print(f"\nRunning {lens.upper()} lens on {ticker} ({market}) ...")
    print("Step 1: Fetch ...")
    raw = fetch(ticker, market)
    print("Step 2: Normalise ...")
    norm = normalise(raw)
    print("Step 3: Calculate ratios ...")
    ratios = calculate(norm)
    print("Step 4: Audit ...")
    audit_result = audit(norm, ratios)

    if audit_result["status"] == "BLOCK":
        print(f"\n  BLOCKED: {audit_result['reason']}")
        sys.exit(1)

    print(f"Step 5: Running {lens.upper()} lens agent (this may take 30-60 seconds) ...")
    result = analyse(lens, norm, ratios, audit_result)

    # Display summary
    status = result.get("status", "unknown")
    print(f"\n  Status: {status.upper()}")

    if status == "error":
        print(f"  Error: {result.get('error')}")
        if "raw_response" in result:
            print(f"  Raw (first 500 chars): {result['raw_response'][:500]}")
    else:
        print(f"  Model: {result.get('model')}")
        print(f"  Summary: {result.get('summary', '')[:300]}")

        sections = result.get("sections", [])
        print(f"\n  Sections ({len(sections)}):")
        for s in sections:
            rag = s.get("rag", "N/A").upper()
            print(f"    [{rag}] {s.get('title', '')[:80]}")
            print(f"           {s.get('interpretation', '')[:100]}")

        if "deal_context" in result:
            print(f"\n  Deal context: {result['deal_context']}")
            print(f"  Deal signal:  {result.get('deal_signal', 'N/A')}")

        if "framework_scores" in result:
            fs = result["framework_scores"]
            print(f"\n  Value score:  {fs.get('value', {}).get('score')}/10")
            print(f"  Growth score: {fs.get('growth', {}).get('score')}/10")
            print(f"  Best fit:     {fs.get('best_fit')}")

        if "three_questions" in result:
            tq = result["three_questions"]
            print(f"\n  Value creation: {tq.get('value_creation', {}).get('answer')}")
            print(f"  Cash quality:   {tq.get('cash_quality', {}).get('answer')}")
            print(f"  Capital alloc:  {tq.get('capital_allocation', {}).get('answer')}")

    # Save output
    out = f"{ticker.replace('.', '_')}_{lens}_analysis.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved -> {out}")
