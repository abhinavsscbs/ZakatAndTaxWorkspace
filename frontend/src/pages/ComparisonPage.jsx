import { useMemo, useState } from 'react'
import { apiJson } from '../api'

export default function ComparisonPage() {
  const [files, setFiles] = useState([])
  const [pairs, setPairs] = useState([{ older: '', newer: '' }])
  const [results, setResults] = useState([])
  const [busy, setBusy] = useState(false)

  const names = useMemo(() => files.map((f) => f.name), [files])

  const setPair = (index, field, value) => {
    const copy = [...pairs]
    copy[index] = { ...copy[index], [field]: value }
    setPairs(copy)
  }

  const addPair = () => setPairs([...pairs, { older: '', newer: '' }])

  const run = async () => {
    if (files.length < 2) return alert('Upload at least 2 files')
    setBusy(true)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      form.append('pairs', JSON.stringify(pairs))

      const data = await apiJson('/api/comparisons/run', {
        method: 'POST',
        body: form
      })
      setResults(data.results || [])
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <h2>Contract Comparison</h2>
      <label>Upload contracts (PDF/DOCX)</label>
      <input
        type="file"
        multiple
        accept=".pdf,.docx,.txt"
        onChange={(e) => setFiles(Array.from(e.target.files || []))}
      />

      <p className="muted">Upload versions, choose your pairs, and export a detailed Excel comparison. Up to 22,000 characters per contract.</p>

      <div className="row">
        <h3>Comparison Pairs</h3>
        <button onClick={addPair}>Add Pair</button>
      </div>

      {pairs.map((p, idx) => (
        <div className="pair" key={idx}>
          <select value={p.older} onChange={(e) => setPair(idx, 'older', e.target.value)}>
            <option value="">Older contract</option>
            {names.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <select value={p.newer} onChange={(e) => setPair(idx, 'newer', e.target.value)}>
            <option value="">Newer contract</option>
            {names.filter((n) => n !== p.older).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      ))}

      <button disabled={busy} onClick={run}>{busy ? 'Running...' : 'Run Comparisons'}</button>

      {results.length > 0 && (
        <div>
          <h3>Results</h3>
          {results.map((r) => (
            <div key={r.pair} className={r.success ? 'ok' : 'err'}>
              Pair {r.pair}: {r.older} vs {r.newer} - {r.success ? 'Success' : r.error}
              {r.success && <><p>{r.comparison?.overall_summary}</p>{r.comparison?.differences?.map((d,i)=><div className="card" key={i}><strong>{d.impact_score} · {d.difference_summary}</strong><div className="pair"><blockquote>{d.older_contract}</blockquote><blockquote>{d.newer_contract}</blockquote></div></div>)}<a href={r.download_url}>Download Excel ↗</a></>}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
