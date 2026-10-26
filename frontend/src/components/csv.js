// UTF-8 BOM keeps Arabic readable in Excel; quote every cell for RFC 4180 CSV.
export function tableCsv(rows) {
  return '\uFEFF' + rows.map(row => row.map(value => {
    let text = String(value ?? '')
    // Prevent spreadsheet software from executing model-generated cell formulas.
    if (/^[\s\u0000-\u001f]*[=+@-]/u.test(text)) text = "'" + text
    return '"' + text.replaceAll('"', '""') + '"'
  }).join(',')).join('\r\n') + '\r\n'
}
