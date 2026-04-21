'use client'

import dynamic from 'next/dynamic'

const TrendChart = dynamic(() => import('./TrendChart'), { ssr: false })

interface Props {
  title:          string          // plain-English question
  ratioName:      string
  value:          string          // formatted display value
  unit:           string
  rag:            string | null
  direction:      string | null
  interpretation: string
  confidence:     string
  yoyPct?:        number | null
  values5yr?:     (number | null)[]
  dates?:         string[]        // YYYY-MM-DD, newest-first
  vsComps?:       string | null   // IB: peer comparison sentence
  verdict?:       string | null   // CF: combined RAG+direction sentence
  peerBenchmark?: string | null   // CF: peer benchmark
}

const RAG_STYLES: Record<string, string> = {
  green: 'bg-green-100 text-green-800 border border-green-200',
  amber: 'bg-amber-100 text-amber-800 border border-amber-200',
  red:   'bg-red-100 text-red-800 border border-red-200',
}

const DIR_ICONS: Record<string, { icon: string; color: string }> = {
  improving:    { icon: '↑', color: 'text-green-600' },
  stable:       { icon: '→', color: 'text-gray-400'  },
  deteriorating:{ icon: '↓', color: 'text-red-500'   },
}

const CONF_DOT: Record<string, string> = {
  high:   'bg-green-400',
  medium: 'bg-amber-400',
  low:    'bg-red-400',
}

export default function RatioCard({
  title, ratioName, value, unit, rag, direction,
  interpretation, confidence, yoyPct,
  values5yr, dates, vsComps, verdict, peerBenchmark,
}: Props) {
  const ragStyle  = RAG_STYLES[rag ?? ''] ?? 'bg-gray-100 text-gray-600 border border-gray-200'
  const dirInfo   = DIR_ICONS[direction ?? '']
  const confDot   = CONF_DOT[confidence] ?? 'bg-gray-300'
  const hasTrend  = values5yr && dates && values5yr.filter(v => v != null).length >= 2

  const yoyStr = yoyPct != null
    ? `${yoyPct >= 0 ? '+' : ''}${(yoyPct * 100).toFixed(1)}% YoY`
    : null

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-gray-900 leading-snug flex-1">
          {title}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${ragStyle}`}>
            {(rag ?? 'N/A').toUpperCase()}
          </span>
        </div>
      </div>

      {/* Metrics row */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        {dirInfo && (
          <span className={`text-lg font-bold ${dirInfo.color}`} title={direction ?? ''}>
            {dirInfo.icon}
          </span>
        )}
        {direction && (
          <span className="text-sm text-gray-500 capitalize">{direction}</span>
        )}
        {yoyStr && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium
            ${yoyPct! >= 0 ? 'bg-blue-50 text-blue-700' : 'bg-orange-50 text-orange-700'}`}>
            {yoyStr}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${confDot}`} />
          <span className="text-xs text-gray-400 capitalize">{confidence} confidence</span>
        </div>
      </div>

      {/* 5-year trend chart */}
      {hasTrend && (
        <TrendChart values={values5yr!} dates={dates!} unit={unit} rag={rag} />
      )}

      {/* AI interpretation */}
      <p className="text-sm text-gray-700 leading-relaxed">{interpretation}</p>

      {/* Optional extras */}
      {verdict && (
        <p className="text-sm font-medium text-gray-800 bg-gray-50 rounded-lg px-3 py-2">
          {verdict}
        </p>
      )}
      {vsComps && (
        <p className="text-xs text-gray-500 italic border-l-2 border-gray-200 pl-3">
          vs. peers: {vsComps}
        </p>
      )}
      {peerBenchmark && (
        <p className="text-xs text-gray-500 italic border-l-2 border-gray-200 pl-3">
          benchmark: {peerBenchmark}
        </p>
      )}

      {/* Ratio name chip */}
      <div className="pt-1">
        <span className="text-xs text-gray-300 font-mono">{ratioName}</span>
      </div>
    </div>
  )
}
