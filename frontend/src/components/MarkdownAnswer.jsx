import { useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { tableCsv } from './csv'

function DownloadableTable({ children, answerNumber }) {
  const table = useRef(null)
  function download() {
    const rows = Array.from(table.current.rows, row =>
      Array.from(row.cells, cell => cell.innerText ?? cell.textContent ?? '')
    )
    const blob = new Blob([tableCsv(rows)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const tables = Array.from(table.current.closest('.markdown-answer').querySelectorAll('table'))
    link.href = url
    link.download = `tax-answer-${answerNumber}-table-${tables.indexOf(table.current) + 1}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <div className="answer-table">
    <div className="table-actions"><button type="button" onClick={download}>Download CSV ↓</button></div>
    <div className="table-scroll"><table ref={table}>{children}</table></div>
  </div>
}

export default function MarkdownAnswer({ text, answerNumber }) {
  return <div dir="auto" className="markdown-answer">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      table: ({ children }) => <DownloadableTable answerNumber={answerNumber}>{children}</DownloadableTable>,
      a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />
    }}>{text}</ReactMarkdown>
  </div>
}
