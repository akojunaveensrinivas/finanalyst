'use client'

import {
  Chart as ChartJS,
  CategoryScale, LinearScale,
  PointElement, LineElement,
  Filler, Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

interface Props {
  values: (number | null)[]  // newest-first
  dates:  string[]           // newest-first YYYY-MM-DD strings
  unit:   string
  rag?:   string | null
}

const RAG_COLORS: Record<string, { line: string; fill: string }> = {
  green:   { line: '#16a34a', fill: 'rgba(22,163,74,0.08)'   },
  amber:   { line: '#d97706', fill: 'rgba(217,119,6,0.08)'   },
  red:     { line: '#dc2626', fill: 'rgba(220,38,38,0.08)'   },
  default: { line: '#6366f1', fill: 'rgba(99,102,241,0.08)'  },
}

function fmtTick(v: number, unit: string) {
  if (unit === '%')    return `${(v * 100).toFixed(0)}%`
  if (unit === 'x')   return `${v.toFixed(1)}x`
  if (unit === 'days') return `${Math.round(v)}d`
  return v.toFixed(2)
}

function fmtTip(v: number, unit: string) {
  if (unit === '%')    return `${(v * 100).toFixed(1)}%`
  if (unit === 'x')   return `${v.toFixed(2)}x`
  if (unit === 'days') return `${Math.round(v)} days`
  return v.toFixed(3)
}

export default function TrendChart({ values, dates, unit, rag }: Props) {
  const rev = [...values].reverse()
  const revDates = [...dates].reverse().map(d => d.slice(0, 7))
  const points = revDates
    .map((label, i) => ({ label, y: rev[i] }))
    .filter((p): p is { label: string; y: number } => p.y != null)

  if (points.length < 2) {
    return <p className="text-xs text-gray-400 italic py-4">Insufficient data for trend chart</p>
  }

  const c = RAG_COLORS[rag ?? 'default'] ?? RAG_COLORS.default

  return (
    <div className="h-28">
      <Line
        data={{
          labels: points.map(p => p.label),
          datasets: [{
            data:              points.map(p => p.y),
            borderColor:       c.line,
            backgroundColor:   c.fill,
            fill:              true,
            tension:           0.35,
            pointRadius:       4,
            pointHoverRadius:  6,
            pointBackgroundColor: c.line,
            borderWidth:       2,
          }],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx: any) => fmtTip(ctx.parsed.y, unit) } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#9ca3af' } },
            y: {
              grid: { color: 'rgba(0,0,0,0.04)' },
              ticks: { font: { size: 10 }, color: '#9ca3af', callback: (v: any) => fmtTick(v, unit) },
            },
          },
          animation: { duration: 400 },
        } as any}
      />
    </div>
  )
}
