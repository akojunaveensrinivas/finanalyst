'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Fuse from 'fuse.js'
import companiesData from '@/data/companies.json'

export interface Company {
  name: string
  ticker: string
  exchange: string
  sector: string
  industry: string
  market: string
  fy_end: string
  filing_standard: string
  aliases: string[]
}

interface Props {
  onSelect: (company: Company) => void
  selected: Company | null
}

const companies = companiesData as Company[]

const fuse = new Fuse(companies, {
  keys: [
    { name: 'name',    weight: 0.5 },
    { name: 'aliases', weight: 0.35 },
    { name: 'ticker',  weight: 0.15 },
  ],
  threshold: 0.45,
  includeScore: true,
  ignoreLocation: true,
})

const MARKET_LABELS: Record<string, string> = { IN: 'India', US: 'US' }
const EXCHANGE_COLORS: Record<string, string> = {
  NSE: 'bg-blue-100 text-blue-700',
  BSE: 'bg-indigo-100 text-indigo-700',
  NASDAQ: 'bg-green-100 text-green-700',
  NYSE: 'bg-emerald-100 text-emerald-700',
}

export default function CompanySearch({ onSelect, selected }: Props) {
  const [query, setQuery] = useState(selected?.name ?? '')
  const [results, setResults] = useState<Company[]>([])
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const search = useCallback((value: string) => {
    if (!value.trim()) {
      setResults([])
      setOpen(false)
      return
    }
    const hits = fuse.search(value).slice(0, 8).map(r => r.item)
    setResults(hits)
    setOpen(hits.length > 0)
    setActiveIdx(-1)
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setQuery(v)
    if (selected) onSelect(null as unknown as Company) // clear prior selection on re-type
    search(v)
  }

  const handleSelect = (company: Company) => {
    setQuery(company.name)
    setResults([])
    setOpen(false)
    setActiveIdx(-1)
    onSelect(company)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault()
      handleSelect(results[activeIdx])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        inputRef.current && !inputRef.current.contains(e.target as Node) &&
        listRef.current  && !listRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Sync query text if parent resets selected to null
  useEffect(() => {
    if (!selected) setQuery('')
  }, [selected])

  return (
    <div className="w-full max-w-2xl">
      {/* Input */}
      <div className="relative">
        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
          </svg>
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search by company name, ticker, or abbreviation..."
          className="w-full pl-12 pr-4 py-4 text-base bg-white border-2 border-gray-200 rounded-2xl
                     shadow-sm focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100
                     focus:outline-none transition-all placeholder-gray-400"
          autoComplete="off"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setResults([]); setOpen(false); onSelect(null as unknown as Company); inputRef.current?.focus() }}
            className="absolute inset-y-0 right-4 flex items-center text-gray-400 hover:text-gray-600"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Dropdown */}
      {open && results.length > 0 && (
        <div
          ref={listRef}
          className="absolute z-50 mt-2 w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-xl overflow-hidden"
        >
          {results.map((company, idx) => {
            const exchangeColor = EXCHANGE_COLORS[company.exchange] ?? 'bg-gray-100 text-gray-600'
            return (
              <button
                key={company.ticker}
                onClick={() => handleSelect(company)}
                className={`w-full px-4 py-3 text-left border-b border-gray-50 last:border-0
                            transition-colors ${idx === activeIdx ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="font-semibold text-gray-900 truncate">{company.name}</span>
                    <span className="ml-2 text-sm text-gray-500 font-mono">{company.ticker}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${exchangeColor}`}>
                      {company.exchange}
                    </span>
                    <span className="text-xs text-gray-400 hidden sm:block">{company.sector}</span>
                  </div>
                </div>
              </button>
            )
          })}
          <div className="px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t border-gray-100">
            {results.length} result{results.length !== 1 ? 's' : ''} — press Enter to select
          </div>
        </div>
      )}

      {/* Selection confirmation */}
      {selected && (
        <div className="mt-3 flex items-center gap-3 px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-xl">
          <div className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
          <div className="min-w-0">
            <span className="font-semibold text-indigo-900">{selected.name}</span>
            <span className="ml-2 text-sm text-indigo-600 font-mono">{selected.ticker}</span>
            <span className="ml-2 text-sm text-indigo-500">— {selected.sector}</span>
          </div>
          <div className="ml-auto text-xs text-indigo-400 shrink-0">
            FY: {selected.fy_end} · {MARKET_LABELS[selected.market] ?? selected.market}
          </div>
        </div>
      )}
    </div>
  )
}
