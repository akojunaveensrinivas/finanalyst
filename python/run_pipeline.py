"""
run_pipeline.py
Orchestrates the full analysis pipeline and streams JSON progress events to stdout.
Called by the Next.js API route via child_process.spawn.

Each line of stdout is a JSON event:
  { step, status, message }           -- progress update
  { step: "result", data: {...} }     -- final payload
  { step: "error",  message: str }    -- fatal error
"""

import sys
import json
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def emit(step: str, status: str, message: str = "", data=None):
    event = {"step": step, "status": status, "message": message}
    if data is not None:
        event["data"] = data
    print(json.dumps(event, default=str), flush=True)


def run(ticker: str, market: str, lens: str):
    try:
        from data_fetcher import fetch
        from normaliser import normalise
        from ratio_calculator import calculate
        from audit_agent import audit
        from lens_agent import analyse

        # ── Step 1: Fetch ──────────────────────────────────────────────────
        emit("fetch", "running", f"Fetching financial data for {ticker}…")
        raw = fetch(ticker, market)
        n_annual = len(raw.get("annual_5yr", {}))
        company_name = raw.get("market_data", {}).get("company_name", ticker)
        emit("fetch", "done", f"{company_name} — {n_annual} annual periods fetched")

        # ── Step 2: Normalise ──────────────────────────────────────────────
        emit("normalise", "running", "Detecting exceptional items…")
        norm = normalise(raw)
        flag_count = len(norm.get("flags", []))
        confidence = norm.get("confidence", "unknown")
        emit("normalise", "done",
             f"Confidence: {confidence.upper()} — {flag_count} flag(s) noted")

        # ── Step 3: Ratios ─────────────────────────────────────────────────
        emit("ratios", "running", "Calculating 26 financial ratios…")
        ratio_result = calculate(norm)
        n_valid = sum(
            1 for r in ratio_result["ratios"].values() if r.get("value") is not None
        )
        rag = ratio_result.get("signals", {}).get("rag", "N/A").upper()
        emit("ratios", "done", f"{n_valid}/27 ratios computed — overall RAG: {rag}")

        # ── Step 4: Audit ──────────────────────────────────────────────────
        emit("audit", "running", "Running gatekeeper checks…")
        audit_result = audit(norm, ratio_result)
        audit_status = audit_result["status"]
        emit("audit", "done", f"Audit: {audit_status}")

        if audit_status == "BLOCK":
            emit("error", "blocked", audit_result.get("reason", "Audit blocked analysis"))
            return

        # ── Step 5: Lens agent ────────────────────────────────────────────
        lens_label = {"ib": "Investment Banking", "cf": "Corporate Finance",
                      "investor": "Investor"}.get(lens, lens.upper())
        emit("analysis", "running",
             f"Running {lens_label} analysis — searching live data…")
        analysis = analyse(lens, norm, ratio_result, audit_result)

        if analysis.get("status") == "error":
            emit("error", "failed", analysis.get("error", "Lens agent failed"))
            return

        # ── Result ────────────────────────────────────────────────────────
        # Trim description from market_data to keep payload small
        md = dict(norm.get("market_data", {}))
        md.pop("description", None)

        emit("result", "done", "Analysis complete", {
            "analysis":  analysis,
            "ratios":    ratio_result,
            "normalised": {
                "ticker":      norm.get("ticker"),
                "market":      norm.get("market"),
                "currency":    norm.get("currency"),
                "confidence":  norm.get("confidence"),
                "flags":       norm.get("flags", []),
                "market_data": md,
                "annual_5yr":  norm.get("annual_5yr", {}),
            },
            "audit": audit_result,
        })

    except Exception as exc:
        emit("error", "exception",
             f"Pipeline error: {exc}\n{traceback.format_exc()}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        emit("error", "failed", "Usage: run_pipeline.py TICKER MARKET LENS")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3])
