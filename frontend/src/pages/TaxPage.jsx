import { useEffect, useState } from 'react'
import { apiJson, downloadFromJson } from '../api'
import MarkdownAnswer from '../components/MarkdownAnswer'

export default function TaxPage() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('grounded')
  const [documents, setDocuments] = useState([])
  const [selected, setSelected] = useState([])
  const [area, setArea] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function refreshSources() {
    setLoading(true)
    setError('')
    try {
      const data = await apiJson('/api/docs')
      setDocuments(data.documents)
      setSelected(ids => ids.filter(id => data.documents.some(doc => doc.id === id)))
    } catch (error) {
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { refreshSources() }, [])

  const areas = [...new Set(documents.map(doc => doc.area))].sort()
  const filtered = documents.filter(doc => (!area || doc.area === area) && doc.id.toLowerCase().includes(search.toLowerCase()))
  const run = async () => {
    if (!file || (mode === 'grounded' && !selected.length)) return
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('analysis_mode', mode)
      form.append('selected_doc_ids', JSON.stringify(mode === 'grounded' ? selected : []))
      const data = await apiJson('/api/tax/analyze', { method: 'POST', body: form })
      setResult(data)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }
  async function exportResult(format) {
    try {
      await downloadFromJson(`/api/tax/export/${format}`, result, `enhanced_tax_analysis.${format === 'excel' ? 'xlsx' : 'json'}`)
    } catch (error) { setError(error.message) }
  }

  return <section>
    <h2>Enhanced Tax Analysis</h2>
    <p className="muted">Analyze the exact uploaded contract text against your selected sources of truth. Dictionary replacements are applied before API calls. Upload a PDF, DOCX or TXT contract of up to 16,000 characters.</p>
    <details className="tax-explainer"><summary>How does this analysis work?</summary>
      <p>The app reads the uploaded contract, replaces dictionary terms locally, and splits the exact resulting text into clauses or sections without summarizing or rewriting it. Every extracted character is retained, apart from the requested term replacements.</p>
      <p><strong>Source-grounded:</strong> searches only the reference documents you select, retrieves up to six passages per clause, and uses those passages to explain implications and recommendations with citations. Evidence gaps produce an undetermined risk.</p>
      <p><strong>General analysis:</strong> uses the model’s knowledge without consulting your source library. Its risk labels are estimated from the response wording.</p>
      <p>Manage confidential terms under Replacement dictionary. Entries are shared across sessions in a persistent local JSON file. Upload or replace reference documents in Tax AI Chat’s knowledge library, then refresh the list here. Selecting a document does not verify its authority or currency. Check that its jurisdiction and effective date apply.</p>
    </details>
    <label>Contract to analyze<input type="file" disabled={busy} accept=".pdf,.docx,.txt" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
    <fieldset className="tax-source-picker" disabled={busy}>
      <legend>Analysis basis</legend>
      <div className="row">
        <label className="checkbox"><input type="radio" name="tax-mode" value="grounded" checked={mode === 'grounded'} onChange={() => setMode('grounded')}/> Selected sources of truth</label>
        <label className="checkbox"><input type="radio" name="tax-mode" value="general" checked={mode === 'general'} onChange={() => setMode('general')}/> General analysis (no reference sources)</label>
      </div>
      {mode === 'grounded' ? <>
        <div className="row"><strong>{selected.length} source(s) selected</strong><button type="button" disabled={loading} onClick={refreshSources}>{loading ? 'Loading…' : 'Refresh sources'}</button></div>
        <div className="pair"><label>Find a source<input value={search} placeholder="Search document IDs" onChange={e => setSearch(e.target.value)}/></label><label>Tax area<select value={area} onChange={e => setArea(e.target.value)}><option value="">All areas</option>{areas.map(item => <option key={item}>{item}</option>)}</select></label></div>
        {documents.length > 0 && <div className="row"><button type="button" disabled={!filtered.length} onClick={() => setSelected(ids => [...new Set([...ids, ...filtered.map(doc => doc.id)])])}>Select visible sources</button><button type="button" disabled={!selected.length} onClick={() => setSelected([])}>Clear selection</button></div>}
        <div className="tax-source-list">{filtered.map(doc => <label key={doc.id} className="checkbox"><input type="checkbox" checked={selected.includes(doc.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, doc.id] : ids.filter(id => id !== doc.id))}/><span>{doc.id}<small>{doc.area} · {doc.characters.toLocaleString()} characters</small></span></label>)}</div>
        {!loading && !documents.length && <p className="muted">No reference documents yet. Upload sources in Tax AI Chat, then refresh this list.</p>}
        {!!documents.length && !filtered.length && <p className="muted">No sources match these filters.</p>}
        <p className="muted">Only checked documents are used, including checked sources hidden by a filter. Choose at least one. Switching AI providers may build a separate embedding index.</p>
      </> : <p className="muted">This mode does not consult uploaded tax references. Conclusions are general model-generated drafts.</p>}
    </fieldset>
    {error && <div role="alert" className="err">{error}</div>}
    <button disabled={busy || loading || !file || (mode === 'grounded' && !selected.length)} onClick={run}>{busy ? 'Analyzing…' : mode === 'grounded' ? 'Analyze against selected sources' : 'Run general analysis'}</button>
    {result && <div className="tax-results">
      <div className="card"><strong>{result.file_name}</strong><p>{result.analysis_method}</p>{result.selected_doc_ids?.length > 0 && <p>Selected references: {result.selected_doc_ids.join(', ')}</p>}<p className="muted">{result.input_method}</p><p className="muted">{result.replacement_info?.matches_replaced ?? 0} dictionary matches replaced · {result.replacement_info?.configured_terms ?? 0} configured terms</p></div>
      <details><summary>Exact contract text after dictionary replacements</summary><pre dir="auto" className="exact-contract-text">{result.contract_text}</pre></details>
      <h3>Clause Analyses ({result.total_clauses})</h3>
      {result.analysis_results?.map((row, idx) => <div key={idx} className="card">
        <div className="row"><h4>{row.clause_data?.title}</h4><span className="pill">Risk: {row.risk_level}</span></div>
        <p className="muted">{row.clause_data?.category} · {row.evidence_status === 'supported' ? 'Source-cited assessment' : row.evidence_status === 'insufficient' ? 'Insufficient source evidence' : 'General analysis — no reference sources'} · {row.sources_used} cited source(s)</p>
        <details><summary>Exact clause text after dictionary replacements</summary><p dir="auto">{row.clause_data?.full_text}</p></details>
        <MarkdownAnswer text={row.tax_analysis} answerNumber={`clause-${idx + 1}`}/>
        {row.tax_info?.source_chunks?.length > 0 && <details><summary>Reference evidence ({row.tax_info.source_chunks.length} retrieved passages)</summary>
          <p className="muted">Similarity ranks relevance; it is not a confidence score or proof of legal applicability.</p>
          {row.tax_info.source_chunks.map(source => <blockquote key={`${source.doc_id}:${source.chunk}`}><strong>[{source.doc_id}:{source.chunk}]</strong><small> · {row.tax_info.cited_sources?.some(item => item.doc_id === source.doc_id && item.chunk === source.chunk) ? 'Cited in assessment' : 'Retrieved context'}</small><p dir="auto">{source.text}</p></blockquote>)}
        </details>}
      </div>)}
      <div className="row"><button onClick={() => exportResult('excel')}>Export Excel with evidence</button><button onClick={() => exportResult('json')}>Export JSON</button></div>
    </div>}
  </section>
}
