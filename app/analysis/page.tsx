'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import ReportHeader   from '@/components/ReportHeader'
import RatioCard      from '@/components/RatioCard'
import ExportButtons  from '@/components/ExportButtons'

// ── Types ────────────────────────────────────────────────────────────────────

interface StepEvent {
  step:    string
  status:  string
  message: string
  data?:   any
}

// ── Loading view ─────────────────────────────────────────────────────────────

const STEP_LABELS: Record<string, string> = {
  fetch:    'Fetching financial data',
  normalise:'Normalising & validating',
  ratios:   'Calculating 26 ratios',
  audit:    'Running audit checks',
  analysis: 'Running AI analysis',
}

function LoadingView({ steps, name, lens }: { steps: StepEvent[]; name: string; lens: string }) {
  const allStepKeys = ['fetch', 'normalise', 'ratios', 'audit', 'analysis']
  const doneSteps   = new Set(steps.filter(s => s.status === 'done').map(s => s.step))
  const activeStep  = steps.length ? steps[steps.length - 1]?.step : null
  const lastMsg     = steps.length ? steps[steps.length - 1]?.message : ''

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="bg-indigo-950 text-white px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="text-indigo-300 hover:text-white text-sm flex items-center gap-1">
            ← Back
          </Link>
          <span className="text-indigo-300 text-sm font-mono">{name}</span>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-20">
        <div className="max-w-sm w-full text-center space-y-8">
          {/* Spinner */}
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full border-4 border-indigo-100 border-t-indigo-600 animate-spin" />
          </div>

          <div>
            <h2 className="text-xl font-bold text-gray-900 mb-1">Analysing {name}</h2>
            <p className="text-sm text-gray-500 capitalize">
              {lens} lens · {lastMsg || 'Starting…'}
            </p>
          </div>

          {/* Step list */}
          <div className="text-left space-y-3">
            {allStepKeys.map(key => {
              const done    = doneSteps.has(key)
              const active  = activeStep === key && !done
              const pending = !done && !active
              return (
                <div key={key} className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0
                    ${done   ? 'bg-green-500'  : ''}
                    ${active ? 'bg-indigo-500 animate-pulse' : ''}
                    ${pending ? 'bg-gray-200' : ''}`}>
                    {done && (
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7"/>
                      </svg>
                    )}
                  </div>
                  <span className={`text-sm ${done ? 'text-gray-600' : active ? 'text-indigo-700 font-medium' : 'text-gray-400'}`}>
                    {STEP_LABELS[key]}
                  </span>
                  {done && (() => {
                    const evt = steps.find(s => s.step === key && s.status === 'done')
                    return evt?.message
                      ? <span className="ml-auto text-xs text-gray-400 truncate max-w-32">{evt.message}</span>
                      : null
                  })()}
                </div>
              )
            })}
          </div>

          <p className="text-xs text-gray-400">
            AI analysis typically takes 30–90 seconds — searching live data and generating narrative.
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Error view ────────────────────────────────────────────────────────────────

function ErrorView({ message }: { message: string }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.07 16.5c-.77.833.193 2.5 1.732 2.5z"/>
          </svg>
        </div>
        <h2 className="text-xl font-bold text-gray-900">Analysis failed</h2>
        <p className="text-sm text-gray-500 leading-relaxed">{message}</p>
        <Link href="/" className="inline-block mt-4 px-5 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700">
          Try another company
        </Link>
      </div>
    </div>
  )
}

// ── RAG + signal helpers ──────────────────────────────────────────────────────

const RAG_BG: Record<string, string> = {
  green: 'bg-green-50 border-l-green-400',
  amber: 'bg-amber-50 border-l-amber-400',
  red:   'bg-red-50 border-l-red-400',
}

const SIGNAL_STYLES: Record<string, string> = {
  Attractive: 'bg-green-100 text-green-800 border border-green-300',
  Neutral:    'bg-gray-100  text-gray-700  border border-gray-300',
  Avoid:      'bg-red-100   text-red-800   border border-red-300',
}

// ── IB extras ────────────────────────────────────────────────────────────────

function IBExtras({ analysis }: { analysis: any }) {
  const { deal_context, deal_context_rationale, deal_signal, deal_signal_rationale,
          risks = [], comps = [], recent_news = [] } = analysis

  return (
    <div className="space-y-8 max-w-5xl mx-auto px-6">
      {/* Deal signal banner */}
      {deal_signal && (
        <div className={`rounded-2xl p-5 border ${SIGNAL_STYLES[deal_signal] ?? 'bg-gray-50 border-gray-200'}`}>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-sm font-bold uppercase tracking-wide">Deal Signal</span>
            <span className="font-black text-lg">{deal_signal}</span>
          </div>
          <p className="text-sm leading-relaxed">{deal_signal_rationale}</p>
        </div>
      )}

      {/* Deal context */}
      {deal_context && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold uppercase tracking-wide text-indigo-600">Deal Context</span>
            <span className="text-xs px-2 py-0.5 bg-indigo-600 text-white rounded-full capitalize">
              {deal_context.replace(/-/g, ' ')}
            </span>
          </div>
          <p className="text-sm text-indigo-900 leading-relaxed">{deal_context_rationale}</p>
        </div>
      )}

      {/* Comps table */}
      {comps.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Comparable Companies</h3>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                <tr>
                  {['Company', 'EV/EBITDA', 'P/E', 'Source'].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {comps.map((c: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{c.company}</td>
                    <td className="px-4 py-3 text-gray-700">{c.ev_ebitda}</td>
                    <td className="px-4 py-3 text-gray-700">{c.pe}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{c.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Risk register */}
      {risks.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Risk Register</h3>
          <div className="space-y-3">
            {risks.map((r: any, i: number) => {
              const sevColor = r.severity === 'High'
                ? 'text-red-700 bg-red-50 border-red-200'
                : r.severity === 'Medium'
                ? 'text-amber-700 bg-amber-50 border-amber-200'
                : 'text-gray-600 bg-gray-50 border-gray-200'
              return (
                <div key={i} className="border border-gray-200 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900 text-sm">{r.title}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${sevColor}`}>
                      {r.severity}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{r.description}</p>
                  {r.mitigant && (
                    <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-1.5">
                      <span className="font-medium">Mitigant:</span> {r.mitigant}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent news */}
      {recent_news.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Recent News</h3>
          <ul className="space-y-2">
            {recent_news.map((n: string, i: number) => (
              <li key={i} className="text-sm text-gray-600 flex gap-2">
                <span className="text-gray-400 mt-1 shrink-0">•</span>
                {n}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── CF extras ─────────────────────────────────────────────────────────────────

function CFExtras({ analysis }: { analysis: any }) {
  const { three_questions: tq, scorecard = [], peer_benchmarks = [] } = analysis
  if (!tq) return null

  const qItems = [
    { key: 'value_creation',    label: 'Creating or destroying value?',  field: tq.value_creation    },
    { key: 'cash_quality',      label: 'Are profits converting to cash?', field: tq.cash_quality      },
    { key: 'capital_allocation', label: 'How is capital being allocated?', field: tq.capital_allocation },
  ]

  const answerColor: Record<string, string> = {
    creating:   'text-green-700', destroying: 'text-red-700',
    borderline: 'text-amber-700', strong:     'text-green-700',
    weak:       'text-red-700',   mixed:      'text-amber-700',
    disciplined:'text-green-700', aggressive: 'text-amber-700',
    underinvesting: 'text-red-700',
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto px-6">
      {/* Three questions */}
      <div>
        <h3 className="text-base font-bold text-gray-900 mb-4">Three Core Questions</h3>
        <div className="grid grid-cols-1 gap-4">
          {qItems.map(({ label, field }) => {
            if (!field) return null
            const color = answerColor[field.answer?.toLowerCase() ?? ''] ?? 'text-indigo-700'
            return (
              <div key={label} className="bg-white border border-gray-200 rounded-2xl p-5">
                <p className="text-sm font-semibold text-gray-700 mb-1">{label}</p>
                <p className={`text-lg font-bold capitalize mb-2 ${color}`}>{field.answer}</p>
                <p className="text-sm text-gray-600 leading-relaxed">{field.rationale}</p>
                {field.roic_vs_wacc   && <p className="text-xs text-gray-400 mt-2">{field.roic_vs_wacc}</p>}
                {field.leakage_area   && <p className="text-xs text-amber-600 mt-2">Cash leaking via: {field.leakage_area}</p>}
                {field.capex_trend    && <p className="text-xs text-gray-400 mt-2">Capex trend: {field.capex_trend}</p>}
              </div>
            )
          })}
        </div>
      </div>

      {/* Capital allocation scorecard */}
      {scorecard.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Capital Allocation Scorecard</h3>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Pillar</th>
                  <th className="px-4 py-3 text-center font-semibold">Score</th>
                  <th className="px-4 py-3 text-left font-semibold">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {scorecard.map((row: any, i: number) => {
                  const score = row.score ?? 0
                  const barColor = score >= 4 ? 'bg-green-500' : score >= 3 ? 'bg-amber-500' : 'bg-red-400'
                  return (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{row.pillar}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 justify-center">
                          <span className="font-bold text-gray-800">{score}/5</span>
                          <div className="w-16 h-2 bg-gray-100 rounded-full">
                            <div className={`h-2 rounded-full ${barColor}`} style={{ width: `${(score / 5) * 100}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{row.rationale}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Peer benchmarks */}
      {peer_benchmarks.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Peer Benchmarks</h3>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                <tr>
                  {['Metric', 'This Company', 'Peer Average', 'Source'].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {peer_benchmarks.map((b: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{b.metric}</td>
                    <td className="px-4 py-3 text-gray-800 font-semibold">{b.company_value}</td>
                    <td className="px-4 py-3 text-gray-600">{b.peer_avg}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{b.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Investor extras ───────────────────────────────────────────────────────────

function InvestorExtras({ analysis }: { analysis: any }) {
  const { framework_scores: fs, moat, earnings_quality: eq,
          management_credibility: mc, bull_case = [], bear_case = [],
          recent_news = [] } = analysis

  return (
    <div className="space-y-8 max-w-5xl mx-auto px-6">
      {/* Framework scores */}
      {fs && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[
            { label: 'Value Framework (Buffett)', score: fs.value?.score, fits: fs.value?.fits, rationale: fs.value?.rationale },
            { label: 'Growth Framework',          score: fs.growth?.score, fits: fs.growth?.fits, rationale: fs.growth?.rationale },
          ].map(({ label, score, fits, rationale }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-gray-800">{label}</span>
                <span className="text-xl font-black text-indigo-700">{score ?? '?'}/10</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full mb-3">
                <div className="h-2 rounded-full bg-indigo-500 transition-all"
                  style={{ width: `${((score ?? 0) / 10) * 100}%` }} />
              </div>
              <p className="text-xs text-gray-500 mb-1">
                Fits this company: <span className="font-medium text-gray-700">{fits}</span>
              </p>
              <p className="text-xs text-gray-500 leading-relaxed">{rationale}</p>
            </div>
          ))}
        </div>
      )}
      {fs?.best_fit_rationale && (
        <p className="text-sm text-indigo-800 bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3">
          <span className="font-semibold">Best fit:</span> {fs.best_fit_rationale}
        </p>
      )}

      {/* Bull / Bear */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Bull */}
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
            <span className="text-green-600">▲</span> Bull Case
          </h3>
          <div className="space-y-3">
            {bull_case.map((b: any, i: number) => (
              <div key={i} className="bg-green-50 border border-green-200 rounded-xl p-4">
                <p className="text-sm font-semibold text-green-900 mb-1">{b.point}</p>
                <p className="text-xs text-green-700 leading-relaxed">{b.data}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Bear */}
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
            <span className="text-red-500">▼</span> Bear Case
          </h3>
          <div className="space-y-3">
            {bear_case.map((b: any, i: number) => (
              <div key={i} className="bg-red-50 border border-red-200 rounded-xl p-4">
                <p className="text-sm font-semibold text-red-900 mb-1">{b.point}</p>
                <p className="text-xs text-red-700 leading-relaxed">{b.data}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Moat */}
      {moat && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-gray-900">Competitive Moat</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium border
              ${moat.overall_strength === 'strong'   ? 'bg-green-100 text-green-800 border-green-200' :
                moat.overall_strength === 'moderate' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                'bg-gray-100 text-gray-700 border-gray-200'}`}>
              {(moat.overall_strength ?? 'unknown').toUpperCase()}
            </span>
          </div>
          {moat.types_present?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {moat.types_present.map((t: string) => (
                <span key={t} className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5">
                  {t}
                </span>
              ))}
            </div>
          )}
          {moat.supporting_data && (
            <p className="text-sm text-gray-600">{moat.supporting_data}</p>
          )}
        </div>
      )}

      {/* Earnings quality */}
      {eq && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-900">Earnings Quality</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium border
              ${eq.rating === 'High'   ? 'bg-green-100 text-green-800 border-green-200' :
                eq.rating === 'Medium' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                'bg-red-100 text-red-800 border-red-200'}`}>
              {eq.rating}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            {(['accrual_test', 'fcf_test', 'margin_stability_test', 'working_capital_test'] as const).map(t => (
              <div key={t} className={`flex items-center gap-2 text-xs rounded-lg px-2 py-1
                ${eq[t] === 'pass' ? 'bg-green-50 text-green-700' :
                  eq[t] === 'fail' ? 'bg-red-50 text-red-700' : 'bg-gray-50 text-gray-500'}`}>
                <span>{eq[t] === 'pass' ? '✓' : eq[t] === 'fail' ? '✗' : '?'}</span>
                <span className="capitalize">{t.replace(/_test$/, '').replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
          {eq.narrative && <p className="text-sm text-gray-600">{eq.narrative}</p>}
        </div>
      )}

      {/* Recent news */}
      {recent_news.length > 0 && (
        <div>
          <h3 className="text-base font-bold text-gray-900 mb-3">Recent News</h3>
          <ul className="space-y-2">
            {recent_news.map((n: string, i: number) => (
              <li key={i} className="text-sm text-gray-600 flex gap-2">
                <span className="text-gray-400 mt-1 shrink-0">•</span>
                {n}
              </li>
            ))}
          </ul>
        </div>
      )}</div>
  )
}

// ── Main report view ──────────────────────────────────────────────────────────

function ReportView({ result, lens, name }: { result: any; lens: string; name: string }) {
  const { analysis, ratios: ratioResult, normalised, audit } = result
  const sections: any[]  = analysis?.sections ?? []
  const inflections: any[] = ratioResult?.inflections ?? []
  const ratioMap: Record<string, any> = ratioResult?.ratios ?? {}

  // Extract sorted date list (newest-first) for chart X-axis
  const annualDates = Object.keys(normalised?.annual_5yr ?? {}).sort().reverse()

  const LENS_SECTION_HEADER: Record<string, string> = {
    ib:       'Investment Banking Analysis',
    cf:       'Corporate Finance Analysis',
    investor: 'Investor Analysis',
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-900 flex items-center gap-1">
            ← New analysis
          </Link>
          <span className="text-sm font-medium text-gray-700 truncate hidden sm:block">{name}</span>
          <ExportButtons result={result} lens={lens} />
        </div>
      </div>

      {/* Company header */}
      <ReportHeader
        ticker={normalised.ticker}
        market={normalised.market}
        currency={normalised.currency}
        confidence={normalised.confidence}
        auditStatus={audit.status}
        auditWarnings={audit.warnings ?? []}
        marketData={normalised.market_data ?? {}}
        lens={lens}
      />

      {/* Audit warnings */}
      {(audit.warnings ?? []).length > 0 && (
        <div className="bg-amber-50 border-b border-amber-200">
          <div className="max-w-5xl mx-auto px-6 py-3 space-y-1">
            {audit.warnings.map((w: string, i: number) => (
              <p key={i} className="text-xs text-amber-800 flex gap-2">
                <span className="shrink-0">⚠</span>{w}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Executive summary */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-base font-bold text-gray-900 mb-3">Executive Summary</h2>
          <p className="text-base text-gray-700 leading-relaxed">{analysis?.summary}</p>

          {/* Overall signal pills */}
          <div className="mt-4 flex flex-wrap gap-3">
            <div className={`px-3 py-1 rounded-full text-xs font-semibold border
              ${RAG_BG[ratioResult?.signals?.rag ?? '']?.split(' ')[0] ?? 'bg-gray-100'}
              text-gray-700 border-gray-200`}>
              Overall: {(ratioResult?.signals?.rag ?? 'N/A').toUpperCase()}
            </div>
            <div className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200 capitalize">
              Trend: {ratioResult?.signals?.direction ?? 'N/A'}
            </div>
            {lens === 'ib' && analysis?.deal_signal && (
              <div className={`px-3 py-1 rounded-full text-xs font-semibold border ${SIGNAL_STYLES[analysis.deal_signal] ?? ''}`}>
                {analysis.deal_signal}
              </div>
            )}
            {lens === 'investor' && analysis?.framework_scores && (
              <div className="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 border border-indigo-200 capitalize">
                Best fit: {analysis.framework_scores.best_fit}
              </div>
            )}
          </div>
        </div>

        {/* Inflection points */}
        {inflections.length > 0 && (
          <div className="mt-4 space-y-2">
            {inflections.map((inf: any, i: number) => (
              <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-2 flex gap-3 text-sm">
                <span className="text-amber-500 shrink-0">⚡</span>
                <span className="text-amber-900">{inf.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ratio sections */}
      <div className="max-w-5xl mx-auto px-6 pb-6 space-y-5">
        <h2 className="text-base font-bold text-gray-900">{LENS_SECTION_HEADER[lens]}</h2>
        <div className="grid grid-cols-1 gap-5">
          {sections.map((s: any, i: number) => {
            const ratioData = ratioMap[s.ratio_name] ?? {}
            return (
              <RatioCard
                key={i}
                title={s.title}
                ratioName={s.ratio_name}
                value={s.value}
                unit={ratioData.unit ?? 'x'}
                rag={s.rag}
                direction={s.direction}
                interpretation={s.interpretation}
                confidence={s.confidence ?? 'medium'}
                yoyPct={ratioData.yoy_pct}
                values5yr={ratioData.values_5yr}
                dates={annualDates}
                vsComps={s.vs_comps}
                verdict={s.verdict}
                peerBenchmark={s.peer_benchmark}
              />
            )
          })}
        </div>
      </div>

      {/* Lens-specific extras */}
      <div className="pb-12">
        {lens === 'ib'       && <IBExtras       analysis={analysis} />}
        {lens === 'cf'       && <CFExtras        analysis={analysis} />}
        {lens === 'investor' && <InvestorExtras  analysis={analysis} />}
      </div>

      {/* Disclaimer footer */}
      <footer className="border-t border-gray-200 bg-white px-6 py-6">
        <div className="max-w-5xl mx-auto space-y-2">
          <p className="text-xs text-gray-400 leading-relaxed">
            <span className="font-semibold text-gray-500">Disclaimer:</span> For informational
            and educational purposes only. Not investment advice. Data sourced from public filings
            via yfinance and may be delayed or incomplete. All ratios and narratives are generated
            by AI and may contain errors. Verify all figures against official filings before making
            any financial decision.
          </p>
          <p className="text-xs text-gray-400">
            Analysis generated by FinAnalyst · Powered by Claude · {new Date().toLocaleDateString()}
          </p>
        </div>
      </footer>
    </div>
  )
}

// ── Root page (requires Suspense for useSearchParams) ─────────────────────────

function AnalysisContent() {
  const searchParams = useSearchParams()
  const ticker = searchParams.get('ticker') ?? ''
  const market = searchParams.get('market') ?? 'US'
  const lens   = searchParams.get('lens')   ?? 'ib'
  const name   = searchParams.get('name')   ?? ticker

  const [phase,    setPhase]    = useState<'loading' | 'done' | 'error'>('loading')
  const [steps,    setSteps]    = useState<StepEvent[]>([])
  const [result,   setResult]   = useState<any>(null)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!ticker) { setPhase('error'); setErrorMsg('No ticker provided.'); return }

    const url = `/api/analyse?ticker=${encodeURIComponent(ticker)}&market=${encodeURIComponent(market)}&lens=${encodeURIComponent(lens)}`
    const es  = new EventSource(url)

    es.onmessage = (e) => {
      let event: StepEvent
      try { event = JSON.parse(e.data) } catch { return }

      if (event.step === 'result') {
        setResult(event.data)
        setPhase('done')
        es.close()
      } else if (event.step === 'error') {
        setErrorMsg(event.message || 'An unknown error occurred.')
        setPhase('error')
        es.close()
      } else if (event.step !== 'log') {
        setSteps(prev => {
          // Update existing step rather than duplicate
          const idx = prev.findIndex(s => s.step === event.step)
          if (idx >= 0) {
            const next = [...prev]
            next[idx] = event
            return next
          }
          return [...prev, event]
        })
      }
    }

    es.onerror = () => {
      if (phase !== 'done') {
        setErrorMsg('Connection to analysis server lost. The pipeline may still be running — try refreshing in 30 seconds.')
        setPhase('error')
      }
      es.close()
    }

    return () => es.close()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, market, lens])

  if (phase === 'loading') return <LoadingView steps={steps} name={name} lens={lens} />
  if (phase === 'error')   return <ErrorView message={errorMsg} />
  if (!result)             return <ErrorView message="No data returned from pipeline." />

  return <ReportView result={result} lens={lens} name={name} />
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-indigo-100 border-t-indigo-600 animate-spin" />
      </div>
    }>
      <AnalysisContent />
    </Suspense>
  )
}
