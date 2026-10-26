import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tableCsv } from './csv.js'

test('CSV preserves headers, Arabic, commas, quotes, and multiline cells', () => {
  assert.equal(tableCsv([
    ['Tax', 'Detail'],
    ['ضريبة', 'A, B "quoted"\nnext line']
  ]), '\uFEFF"Tax","Detail"\r\n"ضريبة","A, B ""quoted""\nnext line"\r\n')
})

test('CSV neutralizes formulas without dropping normal values', () => {
  assert.equal(tableCsv([['=SUM(A1)', ' +1', '@CMD', '-2', '15%', null]]),
    '\uFEFF"\'=SUM(A1)","\' +1","\'@CMD","\'-2","15%",""\r\n')
})
