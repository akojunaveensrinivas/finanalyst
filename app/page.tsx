'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import CompanySearch, { Company } from '@/components/CompanySearch'
import LensSelector, { Lens } from '@/components/LensSelector'

export default function Home() {
  const [company, setCompany] = useState<Company | null>(null)
  const [lens, setLens] = useState<Lens | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleAnalyze = () => {
    if (!company || !lens) return
    setLoading(true)
    const params = new URLSearchParams({
      ticker: company.ticker,
      market: company.market,
      lens,
      name: company.name,
    })
    router.push(`/analysis?${params.toString()}`)
  }

  const handleCompanySelect = (c: Company) => {
    setCompany(c || null)
    if (!c) setLens(null)
  }

  const canAnalyze = Boolean(company && lens)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <span className="font-bold text-gray-900 text-lg">FinAnalyst</span>
            <span className="ml-2 text-xs text-gray-400 font-medium uppercase tracking-wide">AI Financial Analysis</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="bg-gradient-to-b from-indigo-950 to-indigo-900 px-6 py-16 text-center">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold text-white mb-4 leading-tight">
            What do the numbers actually mean?
          </h1>
          <p className="text-indigo-200 text-lg mb-10 leading-relaxed">
            Type a company name. Choose a lens. Get plain-English financial analysis — no jargon,
            no noise. Every ratio explained as a question any person can answer.
          </p>

          {/* Search — positioned over the fold */}
          <div className="relative flex justify-center">
            <CompanySearch onSelect={handleCompanySelect} selected={company} />
          </div>
        </div>
      </section>

      {/* Main content */}
      <main className="flex-1 px-6 py-12">
        <div className="max-w-4xl mx-auto space-y-10">

          {/* Lens selector — shown only after company selected */}
          {company && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
              <LensSelector selected={lens} onSelect={setLens} />
            </div>
          )}

          {/* Analyze button */}
          {canAnalyze && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-300 flex flex-col items-center gap-3">
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="group px-10 py-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400
                           text-white font-semibold text-base rounded-2xl shadow-lg
                           transition-all duration-150 flex items-center gap-3"
              >
                {loading ? (
                  <>
                    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading analysis...
                  </>
                ) : (
                  <>
                    Analyze {company?.name}
                    <svg className="w-4 h-4 transition-transform group-hover:translate-x-1"
                      fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </>
                )}
              </button>
              <p className="text-xs text-gray-400">
                Analysis takes 30–90 seconds — fetching live data and running AI models
              </p>
            </div>
          )}

          {/* How it works — shown before any selection */}
          {!company && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4">
              {[
                {
                  step: '01',
                  title: 'Search any company',
                  body: 'Type a name or ticker — India (NSE) and US markets supported. Fuzzy search handles abbreviations and typos.',
                },
                {
                  step: '02',
                  title: 'Pick your lens',
                  body: 'Investment Banking for deal analysis, Corporate Finance for operational health, or Investor for buy/sell thinking.',
                },
                {
                  step: '03',
                  title: 'Read plain English',
                  body: 'Every ratio appears as a question anyone can understand. No jargon. RAG signals, trends, and AI narrative included.',
                },
              ].map(item => (
                <div key={item.step} className="bg-white rounded-2xl p-6 border border-gray-200">
                  <div className="text-2xl font-black text-indigo-100 mb-3">{item.step}</div>
                  <div className="font-semibold text-gray-900 mb-2">{item.title}</div>
                  <div className="text-sm text-gray-500 leading-relaxed">{item.body}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Footer disclaimer */}
      <footer className="border-t border-gray-200 bg-white px-6 py-4">
        <div className="max-w-4xl mx-auto text-center text-xs text-gray-400">
          For informational and educational purposes only. Not investment advice.
          Data sourced from public filings via yfinance. Analysis generated by AI — verify before acting.
        </div>
      </footer>
    </div>
  )
}
