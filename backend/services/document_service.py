import mimetypes
import os
import re
import tempfile
from contextlib import nullcontext
from flask import has_request_context
from telemetry import step
from docx import Document
import fitz
import pdfplumber


class DocumentService:
    @staticmethod
    def _clean_text(text):
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

    @staticmethod
    def read_docx(path):
        doc = Document(path)
        from docx.text.paragraph import Paragraph
        parts = []
        # Preserve paragraphs and tables in document order, without whitespace cleanup.
        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)
            else:
                for row in block.rows:
                    parts.append('\t'.join(cell.text for cell in row.cells))
        return '\n'.join(parts)

    @staticmethod
    def read_pdf(path):
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                pages.append(txt)
        return DocumentService._clean_text("\n".join(pages))

    @staticmethod
    def read_pdf_fallback(path):
        with fitz.open(path) as doc:
            pages = [page.get_text("text") for page in doc]
        return DocumentService._clean_text("\n".join(pages))

    @staticmethod
    def extract_text(path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".docx":
            return DocumentService.read_docx(path)
        if ext == ".pdf":
            return DocumentService.extract_pdf(path)
        if ext == '.txt':
            with open(path, encoding='utf-8') as source:
                return source.read()
        raise ValueError(f"Unsupported file type: {ext}")

    @staticmethod
    def extract_pdf(path):
        import pytesseract
        from PIL import Image
        language = os.getenv('OCR_LANG', 'eng+ara')
        executable = os.getenv('TESSERACT_CMD')
        if executable:
            pytesseract.pytesseract.tesseract_cmd = executable
        parts = []
        with fitz.open(path) as document:
            max_pages = int(os.getenv('MAX_PDF_PAGES', '100'))
            if len(document) > max_pages:
                raise ValueError(f'PDF exceeds the {max_pages}-page limit; split it into smaller documents')
            for number, page in enumerate(document, start=1):
                timing = step('pdf_page_extraction', page=number) if has_request_context() else nullcontext()
                with timing:
                    text = page.get_text('text').strip()
                if not text:
                    timing = step('ocr_page', page=number, engine='tesseract', language=language) if has_request_context() else nullcontext()
                    with timing:
                        try:
                            # Render at 300 DPI, reducing resolution for oversized pages.
                            scale = min(300 / 72, (12_000_000 / max(page.rect.width * page.rect.height, 1)) ** .5)
                            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
                            image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                            text = pytesseract.image_to_string(image, lang=language, timeout=int(os.getenv('OCR_TIMEOUT_SECONDS', '60'))).strip()
                        except pytesseract.TesseractNotFoundError as exc:
                            raise ValueError('Scanned PDF requires Tesseract. Install it or set TESSERACT_CMD to its executable path.') from exc
                        except pytesseract.TesseractError as exc:
                            raise ValueError(f'OCR failed on page {number}. Check that the OCR_LANG language packs ({language}) are installed.') from exc
                        except RuntimeError as exc:
                            raise ValueError(f'OCR timed out on page {number}; split the PDF or increase OCR_TIMEOUT_SECONDS.') from exc
                parts.append(text)
        return '\n\n'.join(parts)

    @staticmethod
    def save_temp_file(file_storage):
        suffix = os.path.splitext(file_storage.filename or "")[1]
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            file_storage.stream.seek(0)
            file_storage.save(path)
            return path
        except Exception:
            os.unlink(path)
            raise

    @staticmethod
    def detect_mimetype(filename):
        return mimetypes.guess_type(filename)[0]
