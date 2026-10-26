export let provider = localStorage.getItem('provider') || 'openai'
export function setProvider(value) { provider = value; localStorage.setItem('provider', value) }
export async function apiGet(path, options = {}) {
  return fetch(path, { ...options, headers: { ...options.headers, 'X-AI-Provider': provider } })
}
export async function apiJson(path, options = {}) {
  const started = performance.now()
  window.dispatchEvent(new CustomEvent('operation-start', { detail: { path } }))
  let ended = false
  try {
    const res = await apiGet(path, options)
    const raw = await res.text()
    if (!raw.trim()) {
      throw new Error(`The backend returned an empty response (HTTP ${res.status}). Check that Flask is running and the Vite proxy points to http://127.0.0.1:5000.`)
    }
    let data
    try {
      data = JSON.parse(raw)
    } catch {
      throw new Error(`The backend returned an unexpected response (HTTP ${res.status}). Check the API address and restart the frontend if its proxy configuration changed.`)
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('The backend returned an invalid API response.')
    }
    const telemetry = data.telemetry
    delete data.telemetry
    ended = true
    window.dispatchEvent(new CustomEvent('operation-end', { detail: { ...telemetry, path, client_ms: performance.now() - started, error: data.error } }))
    if (!res.ok) throw new Error(data.error || 'Request failed')
    return data
  } catch (error) {
    window.dispatchEvent(new CustomEvent('operation-error', { detail: { message: error.message, ended } }))
    throw error
  }
}
export async function downloadFromJson(path, payload, filename) {
  const res = await apiGet(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
  if (!res.ok) throw new Error('Export failed')
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url)
}
export const postJson = (path, body) => apiJson(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
