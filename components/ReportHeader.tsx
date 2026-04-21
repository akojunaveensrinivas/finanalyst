'use client'

interface MarketData {
  company_name?: string
  sector?: string
  industry?: string
  country?: string
  exchange?: string
  price?: number | null
  market_cap?: number | null
  ev?: number | null
  pe_ratio?: number | null
  pb_ratio?: number | null
  beta?: number | null
  '52w_high'?: number | null
  '52w_low'?: number | null
  currency?: string
}

interface Props {
  ticker:       string
  market:       string
  currency:     string
  confidence:   string
  auditStatus:  string
  auditWarnings: string[]
  marketData:   MarketData
  lens:         string
}

const LENS_LABELS: Record<string, string> = {
  ib:       'Investment Banking',
  cf:       'Corporate Finance',
  investor: 'Investor',
}

const CONF_STYLES: Record<string, string> = {
  high:   'bg-green-100 text-green-800 border-green-200',
  medium: 'bg-amber-100 text-amber-800 border-amber-200',
  low:    'bg-red-100 text-red-800 border-red-200',
}

const AUDIT_STYLES: Record<string, string> = {
  PASS: 'bg-green-100 text-green-800',
  WARN: 'bg-amber-100 text-amber-800',
  BLOCK: 'bg-red-100 text-red-800',
}

function fmt(v: number | null | undefined, prefix = '', suffix = ''): string {
  if (v == null) return 'N/A'
  if (Math.abs(v) >= 1e12) return `${prefix}${(v / 1e12).toFixed(2)}T${suffix}`
  if (Math.abs(v) >= 1e9)  return `${prefix}${(v / 1e9).toFixed(2)}B${suffix}`
  if (Math.abs(v) >= 1e6)  return `${prefix}${(v / 1e6).toFixed(2)}M${suffix}`
  return `${prefix}${v.toLocaleString()}${suffix}`
}

export default function ReportHeader({
  ticker, market, currency, confidence, auditStatus,
  auditWarnings, marketData: md, lens,
}: Props) {
  const confStyle  = CONF_STYLES[confidence]  ?? CONF_STYLES.medium
  const auditStyle = AUDIT_STYLES[auditStatus] ?? AUDIT_STYLES.WARN

  return (
    <div className="bg-gradient-to-r from-indigo-950 to-indigo-900 text-white">
      {/* Company band */}
      <div className="px-6 pt-8 pb-5 max-w-5xl mx-auto">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 mb-1 flex-wrap">
              <h1 className="text-2xl font-bold">
                {md.company_name ?? ticker}
              </h1>
              <span className="font-mono text-indigo-300 text-base">{ticker}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-800 text-indigo-200 border border-indigo-700">
                {md.exchange ?? market}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-800 text-indigo-200 border border-indigo-700">
                {LENS_LABELS[lens] ?? lens.toUpperCase()} Lens
              </span>
            </div>
            <p className="text-indigo-300 text-sm">
              {md.sector}
              {md.industry ? ` · ${md.industry}` : ''}
              {md.country  ? ` · ${md.country}`  : ''}
            </p>
          </div>

          {/* Price block */}
          {md.price != null && (
            <div className="text-right">
              <div className="text-3xl font-bold">
                {md.price.toLocaleString()} <span className="text-lg text-indigo-300">{currency}</span>
              </div>
              {md['52w_high'] != null && md['52w_low'] != null && (
                <div className="text-xs text-indigo-400 mt-1">
                  52w: {md['52w_low']?.toLocaleString()} – {md['52w_high']?.toLocaleString()}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Key metrics row */}
        <div className="mt-4 flex flex-wrap gap-6">
          {[
            { label: 'Market Cap', value: fmt(md.market_cap, '', ` ${currency}`) },
            { label: 'EV',         value: fmt(md.ev, '', ` ${currency}`)         },
            { label: 'P/E',        value: md.pe_ratio != null ? `${md.pe_ratio.toFixed(1)}x` : 'N/A' },
            { label: 'P/B',        value: md.pb_ratio != null ? `${md.pb_ratio.toFixed(1)}x` : 'N/A' },
            { label: 'Beta',       value: md.beta != null ? md.beta.toFixed(2) : 'N/A' },
          ].map(item => (
            <div key={item.label}>
              <div className="text-xs text-indigo-400 uppercase tracking-wide">{item.label}</div>
              <div className="text-sm font-semibold text-white">{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Confidence strip */}
      <div className="border-t border-indigo-800 bg-indigo-950/50 px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs text-indigo-400">Data Quality</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${confStyle}`}>
              {confidence.toUpperCase()}
            </span>
          </div>
          <div className="w-px h-4 bg-indigo-800" />
          <div className="flex items-center gap-2">
            <span className="text-xs text-indigo-400">Audit</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${auditStyle}`}>
              {auditStatus}
            </span>
          </div>
          <div className="w-px h-4 bg-indigo-800" />
          <span className="text-xs text-indigo-400">
            Currency: <span className="text-indigo-200 font-medium">{currency}</span>
          </span>

          {/* Warnings */}
          {auditWarnings.length > 0 && (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-amber-400 text-xs">⚠</span>
              <span className="text-xs text-amber-300">
                {auditWarnings.length} caveat{auditWarnings.length > 1 ? 's' : ''} — see disclaimer
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
