import { useEffect, useMemo, useState } from 'react'
import { apiJson } from '../api'

export default function DictionaryPage() {
  const [dict, setDict] = useState({})
  const [word, setWord] = useState('')
  const [replacement, setReplacement] = useState('')
  const [search, setSearch] = useState('')
  const [file, setFile] = useState(null)
  const [mode, setMode] = useState('merge')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = async () => setDict(await apiJson('/api/dictionary'))
  useEffect(() => { load().catch(error => setError(error.message)) }, [])
  async function perform(action) {
    setBusy(true); setError(''); setNotice('')
    try { await action() } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  const filtered = useMemo(() => Object.fromEntries(Object.entries(dict).filter(([key,value]) => `${key} ${value}`.toLowerCase().includes(search.toLowerCase()))), [dict, search])
  async function save(event) {
    event.preventDefault()
    await perform(async () => {
      setDict(await apiJson('/api/dictionary', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({word,replacement})}))
      setWord('');setReplacement('');setNotice('Entry saved to the shared dictionary.')
    })
  }
  async function importFile(event) {
    event.preventDefault()
    if (!file) return
    if (mode === 'replace' && !confirm('Replace the entire shared dictionary with this file? Existing entries will be removed.')) return
    await perform(async () => {
      const form=new FormData();form.append('file',file);form.append('mode',mode)
      const result=await apiJson('/api/dictionary/import',{method:'POST',body:form})
      setDict(result);setNotice(`Dictionary ${mode === 'replace' ? 'replaced' : 'merged'}. ${Object.keys(result).length} entries saved for all sessions.`)
    })
  }
  return <section>
    <h2>Replacement Dictionary</h2>
    <p className="muted">A shared local JSON file retains entries across browser sessions and server restarts. Matching is case-insensitive and longer terms match first. Only listed terms are masked.</p>
    {error && <div className="err" role="alert">{error}</div>}
    {notice && <div className="ok" role="status">{notice}</div>}
    <form onSubmit={save}><h3>Add a keyword</h3><div className="pair">
      <input aria-label="Confidential word or phrase" required placeholder="Confidential word or phrase" value={word} onChange={e=>setWord(e.target.value)}/>
      <input aria-label="Replacement" required placeholder="Replacement e.g. [PARTY_A]" value={replacement} onChange={e=>setReplacement(e.target.value)}/>
      <button disabled={busy}>Add / update</button>
    </div></form>
    <form className="card" onSubmit={importFile}><h3>Upload a dictionary</h3>
      <p className="muted">Upload UTF-8 CSV or Excel (.xlsx) with <strong>Word</strong> and <strong>Replacement</strong> column headers. Excel reads the first sheet. Keep identifiers such as account numbers formatted as text to preserve leading zeros. The entire file is validated before saving.</p>
      <input aria-label="Dictionary CSV or Excel file" type="file" accept=".csv,.xlsx" required onChange={e=>setFile(e.target.files?.[0] || null)}/>
      <label>Import mode<select value={mode} onChange={e=>setMode(e.target.value)}><option value="merge">Add / merge with existing dictionary</option><option value="replace">Replace the entire dictionary</option></select></label>
      <p className="muted">{mode==='merge'?'Existing terms remain; uploaded replacements win for matching terms. Within the upload, the last matching row wins.':'All existing terms will be removed and replaced by the uploaded entries.'}</p>
      <button disabled={busy || !file}>{busy?'Saving…':mode==='replace'?'Upload & replace dictionary':'Upload & merge dictionary'}</button>
    </form>
    <div className="row"><input aria-label="Search dictionary" placeholder="Search dictionary" value={search} onChange={e=>setSearch(e.target.value)}/>
      <button disabled={busy} onClick={()=>perform(load)}>Refresh shared dictionary</button>
      <button disabled={busy} onClick={()=>{if(confirm('Clear the entire shared dictionary?')) perform(async()=>setDict(await apiJson('/api/dictionary',{method:'DELETE'})))}}>Clear all</button>
      <a href="/api/dictionary/export?format=csv" target="_blank" rel="noreferrer">Export CSV</a><a href="/api/dictionary/export?format=json" target="_blank" rel="noreferrer">Export JSON</a>
    </div>
    <p className="muted">{Object.keys(dict).length} saved entries</p>
    {Object.entries(filtered).map(([key,value])=><div className="row" key={key}><code>{key}</code><span>{value}</span><button disabled={busy} onClick={()=>perform(async()=>setDict(await apiJson(`/api/dictionary/${encodeURIComponent(key)}`,{method:'DELETE'})))}>Delete</button></div>)}
  </section>
}
