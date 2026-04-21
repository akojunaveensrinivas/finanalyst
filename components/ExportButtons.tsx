'use client'

import { useState } from 'react'

interface Props {
  result: any
  lens:   string
}

export default function ExportButtons({ result, lens }: Props) {
  const [pdfLoading,   setPdfLoading]   = useState(false)
  const [excelLoading, setExcelLoading] = useState(false)

  const ticker = result?.normalised?.ticker ?? 'report'
  const slug   = `FinAnalyst_${ticker.replace(/\./g, '_')}_${lens.toUpperCase()}`

  // ── PDF export ────────────────────────────────────────────────────────────
  const exportPDF = async () => {
    setPdfLoading(true)
    try {
      const { default: jsPDF } = await import('jspdf')
      const doc = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
      const W = doc.internal.pageSize.getWidth()
      const margin = 18
      const maxW = W - margin * 2
      let y = margin

      const checkPage = (needed = 12) => {
        if (y + needed > 275) { doc.addPage(); y = margin }
      }

      const line = (text: string, size = 10, bold = false, color = '#111827') => {
        checkPage()
        doc.setFontSize(size)
        doc.setFont('helvetica', bold ? 'bold' : 'normal')
        doc.setTextColor(color)
        const wrapped = doc.splitTextToSize(text, maxW)
        doc.text(wrapped, margin, y)
        y += wrapped.length * (size * 0.45) + 2
      }

      const divider = () => {
        checkPage(4)
        doc.setDrawColor('#e5e7eb')
        doc.line(margin, y, W - margin, y)
        y += 4
      }

      // Cover
      doc.setFillColor('#1e1b4b')
      doc.rect(0, 0, W, 40, 'F')
      doc.setFontSize(18); doc.setFont('helvetica', 'bold'); doc.setTextColor('#ffffff')
      const name = result.normalised?.market_data?.company_name ?? ticker
      doc.text('FinAnalyst Report', margin, 16)
      doc.setFontSize(11); doc.setFont('helvetica', 'normal'); doc.setTextColor('#a5b4fc')
      doc.text(`${name} (${ticker})  ·  ${lens.toUpperCase()} Lens`, margin, 26)
      doc.text(`Generated ${new Date().toLocaleDateString()}`, margin, 33)
      y = 52

      // Summary
      line('Executive Summary', 13, true)
      divider()
      line(result.analysis?.summary ?? 'N/A', 10)
      y += 4

      // Sections
      const sections: any[] = result.analysis?.sections ?? []
      for (const s of sections) {
        checkPage(30)
        line(s.title, 11, true)
        const ragStr = (s.rag ?? 'N/A').toUpperCase()
        const dirStr = s.direction ?? ''
        line(`${s.value}   [${ragStr}]   ${dirStr}`, 10, false, '#374151')
        line(s.interpretation ?? '', 9, false, '#4b5563')
        if (s.vs_comps)      line(`vs. peers: ${s.vs_comps}`, 9, false, '#6b7280')
        if (s.verdict)       line(s.verdict, 9, false, '#6b7280')
        if (s.peer_benchmark) line(`benchmark: ${s.peer_benchmark}`, 9, false, '#6b7280')
        y += 3
        divider()
      }

      // IB extras
      const risks: any[] = result.analysis?.risks ?? []
      if (risks.length) {
        line('Risk Register', 13, true)
        divider()
        for (const r of risks) {
          checkPage(18)
          line(`${r.title} — ${r.severity}`, 10, true)
          line(r.description ?? '', 9)
          if (r.mitigant) line(`Mitigant: ${r.mitigant}`, 9, false, '#6b7280')
          y += 2
        }
      }

      // Investor extras — bull/bear
      const bull: any[] = result.analysis?.bull_case ?? []
      const bear: any[] = result.analysis?.bear_case ?? []
      if (bull.length) {
        line('Bull Case', 13, true)
        divider()
        for (const b of bull) { checkPage(12); line(`▲ ${b.point}`, 10); line(b.data ?? '', 9, false, '#6b7280'); y += 1 }
      }
      if (bear.length) {
        line('Bear Case', 13, true)
        divider()
        for (const b of bear) { checkPage(12); line(`▼ ${b.point}`, 10); line(b.data ?? '', 9, false, '#6b7280'); y += 1 }
      }

      // Disclaimer
      checkPage(14)
      y += 4
      doc.setDrawColor('#fbbf24')
      doc.line(margin, y, W - margin, y); y += 4
      line(
        'For informational and educational purposes only. Not investment advice. ' +
        'Data sourced from public filings via yfinance. Verify all figures before acting.',
        8, false, '#9ca3af'
      )

      doc.save(`${slug}.pdf`)
    } catch (err) {
      console.error('PDF export error:', err)
      alert('PDF export failed — check console for details.')
    } finally {
      setPdfLoading(false)
    }
  }

  // ── Excel export ──────────────────────────────────────────────────────────
  const exportExcel = async () => {
    setExcelLoading(true)
    try {
      const XLSX = await import('xlsx')
      const wb = XLSX.utils.book_new()

      // Sheet 1: Summary
      const md = result.normalised?.market_data ?? {}
      const sig = result.ratios?.signals ?? {}
      const summaryRows = [
        ['FinAnalyst Report', ''],
        ['Company',     md.company_name ?? ticker],
        ['Ticker',      ticker],
        ['Lens',        lens.toUpperCase()],
        ['Currency',    result.normalised?.currency ?? ''],
        ['Sector',      md.sector ?? ''],
        ['Industry',    md.industry ?? ''],
        ['Country',     md.country ?? ''],
        ['Price',       md.price ?? ''],
        ['Market Cap',  md.market_cap ?? ''],
        ['EV',          md.ev ?? ''],
        ['Overall RAG', sig.rag?.toUpperCase() ?? ''],
        ['Direction',   sig.direction ?? ''],
        ['Confidence',  result.normalised?.confidence ?? ''],
        ['Audit',       result.audit?.status ?? ''],
        ['Generated',   new Date().toISOString()],
        ['', ''],
        ['Summary', result.analysis?.summary ?? ''],
        ['', ''],
        ['Disclaimer',
         'For informational and educational purposes only. Not investment advice.'],
      ]
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(summaryRows), 'Summary')

      // Sheet 2: Ratios
      const ratioRows: (string | number)[][] = [
        ['Ratio', 'Display Value', 'Raw Value', 'Unit', 'RAG', 'Direction', 'YoY %', 'Confidence'],
      ]
      const ratioMap: Record<string, any> = result.ratios?.ratios ?? {}
      for (const [name, r] of Object.entries(ratioMap)) {
        ratioRows.push([
          name,
          r.display ?? 'N/A',
          r.value   ?? '',
          r.unit    ?? '',
          (r.rag    ?? 'N/A').toUpperCase(),
          r.direction ?? 'N/A',
          r.yoy_pct != null ? `${(r.yoy_pct * 100).toFixed(1)}%` : 'N/A',
          r.confidence ?? 'N/A',
        ])
      }
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(ratioRows), 'Ratios')

      // Sheet 3: Trends (5-year values per ratio)
      const annual = result.normalised?.annual_5yr ?? {}
      const dates = Object.keys(annual).sort().reverse()
      const trendRows: (string | number | null)[][] = [['Ratio', ...dates]]
      for (const [name, r] of Object.entries(ratioMap)) {
        trendRows.push([name, ...(r as any).values_5yr.slice(0, dates.length)])
      }
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(trendRows), 'Trends')

      // Sheet 4: Raw Financials
      const allFields = new Set(dates.flatMap(d => Object.keys(annual[d] ?? {})))
      allFields.delete('currency')
      const rawRows: (string | number | null)[][] = [['Field', ...dates]]
      for (const field of allFields) {
        rawRows.push([field, ...dates.map(d => annual[d]?.[field] ?? null)])
      }
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rawRows), 'Raw Financials')

      // Sheet 5: Peers (IB)
      const comps: any[] = result.analysis?.comps ?? []
      if (comps.length) {
        const peerRows = [['Company', 'EV/EBITDA', 'P/E', 'Source']]
        for (const c of comps) peerRows.push([c.company, c.ev_ebitda, c.pe, c.source])
        XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(peerRows), 'Peers')
      }

      XLSX.writeFile(wb, `${slug}.xlsx`)
    } catch (err) {
      console.error('Excel export error:', err)
      alert('Excel export failed — check console for details.')
    } finally {
      setExcelLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={exportPDF}
        disabled={pdfLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700
                   bg-white border border-gray-300 rounded-lg hover:bg-gray-50
                   disabled:opacity-50 transition-colors"
      >
        {pdfLoading ? (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        )}
        PDF
      </button>

      <button
        onClick={exportExcel}
        disabled={excelLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700
                   bg-white border border-gray-300 rounded-lg hover:bg-gray-50
                   disabled:opacity-50 transition-colors"
      >
        {excelLoading ? (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        )}
        Excel
      </button>
    </div>
  )
}
