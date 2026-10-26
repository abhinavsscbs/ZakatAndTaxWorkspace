import sys
from pathlib import Path
import fitz
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from app import app
from telemetry import begin
from flask import g
from services.document_service import DocumentService

def test_mixed_pdf_ocr_and_timings(tmp_path,monkeypatch):
    path=tmp_path/'mixed.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page();page.insert_text((72,72),'Searchable first page')
        pdf.new_page()
        pdf.save(path)
    calls=[]
    def ocr(image,**options):
        calls.append(options)
        return 'Scanned second page'
    monkeypatch.setattr('pytesseract.image_to_string',ocr)
    monkeypatch.setenv('OCR_LANG','eng+ara')
    with app.test_request_context():
        begin()
        text=DocumentService.extract_text(str(path))
        assert 'Searchable first page' in text and 'Scanned second page' in text
        assert len(calls)==1 and calls[0]['lang']=='eng+ara'
        assert [s['name'] for s in g.steps]==['pdf_page_extraction','pdf_page_extraction','ocr_page']
        assert g.steps[-1]['page']==2

def test_ocr_missing_binary_message(tmp_path,monkeypatch):
    import pytest
    import pytesseract
    path=tmp_path/'scan.pdf'
    with fitz.open() as pdf:
        pdf.new_page();pdf.save(path)
    def missing(*a,**k):raise pytesseract.TesseractNotFoundError()
    monkeypatch.setattr('pytesseract.image_to_string',missing)
    with pytest.raises(ValueError,match='requires Tesseract'):
        DocumentService.extract_text(str(path))
