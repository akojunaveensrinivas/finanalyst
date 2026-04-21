"""
Flask SSE server — deploy this on Railway.
The Next.js route proxies to it in production via PYTHON_BACKEND_URL.
"""
import json
import os
import sys
import traceback

from flask import Flask, Response, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

from data_fetcher    import fetch
from normaliser      import normalise
from ratio_calculator import calculate
from audit_agent     import audit
from lens_agent      import analyse as run_analysis

app = Flask(__name__)
CORS(app)


def _emit(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.route('/health')
def health():
    return {'status': 'ok'}


@app.route('/analyse')
def analyse_endpoint():
    ticker = request.args.get('ticker', '').strip()
    market = request.args.get('market', 'US').strip()
    lens   = request.args.get('lens',   'ib').strip()

    if not ticker:
        return {'error': 'ticker is required'}, 400

    def generate():
        try:
            yield _emit({'step': 'fetch', 'status': 'start', 'message': 'Fetching financial data...'})
            raw = fetch(ticker, market)
            yield _emit({'step': 'fetch', 'status': 'done', 'message': 'Data fetched'})

            yield _emit({'step': 'normalise', 'status': 'start', 'message': 'Normalising data...'})
            normalised = normalise(raw)
            yield _emit({'step': 'normalise', 'status': 'done', 'message': 'Normalised'})

            yield _emit({'step': 'ratios', 'status': 'start', 'message': 'Calculating ratios...'})
            ratio_result = calculate(normalised)
            yield _emit({'step': 'ratios', 'status': 'done', 'message': 'Ratios calculated'})

            yield _emit({'step': 'audit', 'status': 'start', 'message': 'Running audit...'})
            audit_result = audit(normalised, ratio_result)
            yield _emit({'step': 'audit', 'status': 'done', 'message': 'Audit complete'})

            if audit_result.get('status') == 'BLOCK':
                yield _emit({'step': 'error', 'status': 'error',
                             'message': audit_result.get('reason', 'Audit blocked pipeline')})
                return

            yield _emit({'step': 'analysis', 'status': 'start', 'message': 'Running AI analysis...'})
            analysis_result = run_analysis(lens, normalised, ratio_result, audit_result)
            yield _emit({'step': 'analysis', 'status': 'done', 'message': 'Analysis complete'})

            # Trim long description to keep payload small
            md = normalised.get('market_data', {})
            if md.get('description'):
                md['description'] = md['description'][:500]

            yield _emit({
                'step': 'result',
                'data': {
                    'normalised': normalised,
                    'ratios':     ratio_result,
                    'audit':      audit_result,
                    'analysis':   analysis_result,
                },
            })

        except Exception as exc:
            yield _emit({
                'step':      'error',
                'status':    'error',
                'message':   str(exc),
                'traceback': traceback.format_exc(),
            })

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':     'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
