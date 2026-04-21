'use client'

export type Lens = 'ib' | 'cf' | 'investor'

interface LensConfig {
  id: Lens
  label: string
  tagline: string
  audience: string
  questions: string[]
  accent: string
  selectedAccent: string
  iconPath: string
}

const LENSES: LensConfig[] = [
  {
    id: 'ib',
    label: 'Investment Banking',
    tagline: 'Deal-ready analysis for transactions',
    audience: 'M&A advisors, PE analysts, corporate development',
    questions: [
      'Is this company attractively priced vs. peers?',
      'What is the leverage and deal risk?',
      'Buy-side target, sell-side mandate, or ECM candidate?',
    ],
    accent: 'border-blue-200 hover:border-blue-400',
    selectedAccent: 'border-blue-500 bg-blue-50 ring-4 ring-blue-100',
    iconPath: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  },
  {
    id: 'cf',
    label: 'Corporate Finance',
    tagline: 'Operational health and capital efficiency',
    audience: 'CFOs, treasury teams, finance professionals',
    questions: [
      'Is the company creating or destroying value?',
      'Are profits converting to real cash?',
      'How well is management allocating capital?',
    ],
    accent: 'border-emerald-200 hover:border-emerald-400',
    selectedAccent: 'border-emerald-500 bg-emerald-50 ring-4 ring-emerald-100',
    iconPath: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  {
    id: 'investor',
    label: 'Investor',
    tagline: 'Value vs. growth with bull and bear cases',
    audience: 'Retail investors, fund managers, analysts',
    questions: [
      'Does this fit a value or growth framework?',
      'Is there a durable competitive moat?',
      'What are the bull and bear cases?',
    ],
    accent: 'border-violet-200 hover:border-violet-400',
    selectedAccent: 'border-violet-500 bg-violet-50 ring-4 ring-violet-100',
    iconPath: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z',
  },
]

interface Props {
  selected: Lens | null
  onSelect: (lens: Lens) => void
}

export default function LensSelector({ selected, onSelect }: Props) {
  return (
    <div className="w-full max-w-4xl">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">
        Choose your analysis lens
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {LENSES.map(lens => {
          const isSelected = selected === lens.id
          return (
            <button
              key={lens.id}
              onClick={() => onSelect(lens.id)}
              className={`relative text-left p-5 rounded-2xl border-2 transition-all duration-150
                          ${isSelected ? lens.selectedAccent : `border-gray-200 bg-white ${lens.accent}`}`}
            >
              {/* Icon */}
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4
                              ${isSelected ? 'bg-white shadow-sm' : 'bg-gray-100'}`}>
                <svg
                  className={`w-5 h-5 ${isSelected ? 'text-gray-800' : 'text-gray-500'}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  strokeWidth={1.75}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d={lens.iconPath} />
                </svg>
              </div>

              {/* Label + tagline */}
              <div className="font-bold text-gray-900 text-base mb-1">{lens.label}</div>
              <div className="text-xs text-gray-500 mb-4 leading-snug">{lens.tagline}</div>

              {/* Questions */}
              <ul className="space-y-1.5">
                {lens.questions.map((q, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-600 leading-snug">
                    <span className="mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full bg-gray-300" />
                    {q}
                  </li>
                ))}
              </ul>

              {/* Audience */}
              <div className="mt-4 text-xs text-gray-400 italic">{lens.audience}</div>

              {/* Check badge */}
              {isSelected && (
                <div className="absolute top-4 right-4">
                  <div className="w-5 h-5 rounded-full bg-gray-900 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
