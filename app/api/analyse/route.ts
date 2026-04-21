import { spawn } from 'child_process'
import path from 'path'

export const maxDuration = 300

const SSE_HEADERS = {
  'Content-Type':      'text/event-stream',
  'Cache-Control':     'no-cache',
  'Connection':        'keep-alive',
  'X-Accel-Buffering': 'no',
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const ticker = searchParams.get('ticker') ?? ''
  const market = searchParams.get('market') ?? 'US'
  const lens   = searchParams.get('lens')   ?? 'ib'

  if (!ticker) {
    return new Response(
      JSON.stringify({ error: 'ticker is required' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }
    )
  }

  // ── Production: proxy to Python backend (Railway) ────────────────────────
  const backendUrl = process.env.PYTHON_BACKEND_URL
  if (backendUrl) {
    const upstreamUrl = `${backendUrl}/analyse?ticker=${encodeURIComponent(ticker)}&market=${encodeURIComponent(market)}&lens=${encodeURIComponent(lens)}`
    try {
      const upstream = await fetch(upstreamUrl, {
        headers: { Accept: 'text/event-stream' },
        // @ts-expect-error — Node 18+ fetch supports this
        duplex: 'half',
      })
      return new Response(upstream.body, { headers: SSE_HEADERS })
    } catch (err: any) {
      const event = JSON.stringify({ step: 'error', status: 'failed', message: `Backend unreachable: ${err.message}` })
      return new Response(`data: ${event}\n\n`, { headers: SSE_HEADERS })
    }
  }

  // ── Development: spawn Python child process ───────────────────────────────
  const pythonDir  = path.join(process.cwd(), 'python')
  const scriptPath = path.join(pythonDir, 'run_pipeline.py')
  const pythonExe  = process.env.PYTHON_PATH ?? 'python'
  const encoder    = new TextEncoder()

  const stream = new ReadableStream({
    start(controller) {
      const proc = spawn(pythonExe, ['-u', scriptPath, ticker, market, lens], {
        cwd: pythonDir,
        env: { ...process.env },
      })

      let buffer = ''

      proc.stdout.on('data', (chunk: Buffer) => {
        buffer += chunk.toString()
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.trim()) controller.enqueue(encoder.encode(`data: ${line}\n\n`))
        }
      })

      proc.stderr.on('data', (chunk: Buffer) => {
        const text = chunk.toString().trim()
        if (text) {
          const event = JSON.stringify({ step: 'log', status: 'info', message: text })
          controller.enqueue(encoder.encode(`data: ${event}\n\n`))
        }
      })

      proc.on('close', (code) => {
        if (buffer.trim()) controller.enqueue(encoder.encode(`data: ${buffer}\n\n`))
        if (code !== 0) {
          const event = JSON.stringify({ step: 'error', status: 'failed', message: `Python process exited with code ${code}` })
          controller.enqueue(encoder.encode(`data: ${event}\n\n`))
        }
        controller.close()
      })

      proc.on('error', (err) => {
        const event = JSON.stringify({
          step: 'error', status: 'failed',
          message: `Failed to start Python (${pythonExe}): ${err.message}. Set PYTHON_PATH in .env.local if needed.`,
        })
        controller.enqueue(encoder.encode(`data: ${event}\n\n`))
        controller.close()
      })
    },
  })

  return new Response(stream, { headers: SSE_HEADERS })
}
