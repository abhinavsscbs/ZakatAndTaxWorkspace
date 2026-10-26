import { useEffect, useState } from 'react'
import ComparisonPage from './pages/ComparisonPage'
import DictionaryPage from './pages/DictionaryPage'
import TaxPage from './pages/TaxPage'
import ChatPage from './pages/ChatPage'
import { provider as initialProvider, setProvider, apiJson } from './api'

export default function App() {
  const [tab, setTab] = useState('contracts')
  const [tool, setTool] = useState('compare')
  const [provider, changeProvider] = useState(initialProvider)
  const [providers, setProviders] = useState({})
  const [connection, setConnection] = useState('connecting')
  async function loadProviders() {
    setConnection('connecting')
    try {
      const data = await apiJson('/api/providers')
      if (!data.providers?.openai || !data.providers?.cohere) throw new Error('Backend provider configuration is missing')
      setProviders(data.providers)
      setConnection('connected')
      setError('')
    } catch (error) {
      setConnection('offline')
      setError(error.message)
    }
  }
  const [runs, setRuns] = useState([])
  const [pending, setPending] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    const start = () => { setPending(n => n + 1); setElapsed(0); setError('') }
    const end = e => { setPending(n => Math.max(0,n-1)); if (e.detail.steps?.length) setRuns(r => [e.detail, ...r].slice(0,12)) }
    const fail = e => { if (!e.detail.ended) setPending(n => Math.max(0,n-1)); setError(e.detail.message) }
    window.addEventListener('operation-start', start); window.addEventListener('operation-end', end); window.addEventListener('operation-error', fail)
    loadProviders()
    return () => { window.removeEventListener('operation-start', start); window.removeEventListener('operation-end', end); window.removeEventListener('operation-error', fail) }
  }, [])
  useEffect(() => { if (!pending) return; const interval = setInterval(() => setElapsed(t=>t+.1),100); return () => clearInterval(interval) }, [pending])
  return <div className="app">
    <aside className="sidebar"><div className="brand"><span className="brand-icon">Z</span><div>Zakat & Tax<span>INTELLIGENCE WORKSPACE</span></div></div>
      <div className="nav-label">YOUR WORKSPACE</div>
      <button className={`nav ${tab==='contracts'?'active':''}`} onClick={()=>setTab('contracts')}>▤ <span>Contract Comparison<small>Compare, analyze & review</small></span></button>
      <button className={`nav ${tab==='chat'?'active':''}`} onClick={()=>setTab('chat')}>✧ <span>Tax AI Chat<small>Research grounded in your sources</small></span></button>
      <div className="sidebar-bottom"><span className="dot"/> Two providers. One workspace.<p>Independent embeddings · Traceable answers</p></div>
    </aside>
    <main className="content"><header className="topbar"><span>Workspace / {tab==='contracts'?'Contract Comparison':'Tax AI Chat'}</span><label className="provider">AI provider <select aria-label="AI provider" disabled={pending>0} value={provider} onChange={e=>{changeProvider(e.target.value);setProvider(e.target.value)}}><option value="openai">OpenAI · Global API</option><option value="cohere">Cohere API</option></select></label></header>
      <div className="hero"><div><div className="eyebrow">PRECISION IN EVERY PROVISION</div><h1>{tab==='contracts'?'Clarity across your contracts.':'Your sources. Clearer answers.'}</h1><p>{tab==='contracts'?'Spot changes, understand tax implications, and keep every review traceable.':'Ask in English or Arabic. Retrieve evidence from your own tax knowledge library.'}</p></div><span className="pill">{connection==='offline'?'○ Backend unavailable':connection==='connecting'?'○ Checking backend…':providers[provider]?.configured?'● API key configured':'○ API key required'}</span></div>
      <div className="stats"><div><small>GENERATION MODEL</small><strong>{connection==='connected'?providers[provider]?.chat:connection==='offline'?'Backend unavailable':'Connecting…'}</strong></div><div><small>EMBEDDING MODEL</small><strong>{connection==='connected'?providers[provider]?.embedding:connection==='offline'?'Backend unavailable':'Connecting…'}</strong></div><div><small>OBSERVABILITY</small><strong>{connection==='connected'?'Per-step timing & token usage':connection==='offline'?'Waiting for backend':'Checking backend…'}</strong></div></div>
      {error && <div role="alert" className="err">{error}{connection==='offline' && <button onClick={loadProviders}>Retry connection</button>}</div>}
      <div hidden={tab!=='contracts'}><nav className="subtabs" aria-label="Contract tools">{[['compare','Compare contracts'],['tax','Tax analysis'],['dictionary','Replacement dictionary']].map(([id,name])=><button key={id} className={tool===id?'selected':''} onClick={()=>setTool(id)}>{name}</button>)}</nav><div hidden={tool!=='compare'}><ComparisonPage/></div><div hidden={tool!=='tax'}><TaxPage/></div><div hidden={tool!=='dictionary'}><DictionaryPage/></div></div>
      <div hidden={tab!=='chat'}><ChatPage provider={provider}/></div>
      <section className="timings"><div className="row"><div><div className="eyebrow">EXECUTION TRACE</div><h2>Every step, accounted for.</h2></div><span className="pill" aria-live="polite">{pending?`Processing · ${Math.round(elapsed / 60)} min`:'Ready'}</span></div><p className="muted">{pending?'Running on the server. Step durations appear when this request completes.':'Request history includes API usage, retries, and server processing time.'}</p>{!runs.length && <div className="empty">Run a comparison, upload a source, or ask a question to see your execution trace.</div>}{runs.map(run=><details key={run.request_id} open><summary>{run.path} <span>{run.provider} · {Math.round(run.total_ms / 60000)} min</span></summary><div className="trace-id">Request {run.request_id}</div><div className="table-scroll"><table><thead><tr><th>Step</th><th>Status</th><th>Time</th><th>API details</th></tr></thead><tbody>{run.steps.map((step,i)=><tr key={i}><td>{step.name.replaceAll('_',' ')}</td><td><span className={`badge ${step.status}`}>{step.status}</span></td><td>{Math.round(step.duration_ms / 60000)} min</td><td><small>{step.model}{step.attempts?` · ${step.attempts} attempt(s)`:''}{step.usage?` · ${JSON.stringify(step.usage)}`:''}</small></td></tr>)}</tbody></table></div></details>)}</section>
      <footer>Zakat & Tax Toolkit <span>Evidence first. Human judgment always.</span></footer>
    </main></div>
}
