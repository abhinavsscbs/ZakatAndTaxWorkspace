from dotenv import load_dotenv
load_dotenv()
import json
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask import g, send_from_directory
from werkzeug.exceptions import HTTPException
import time
from telemetry import begin, finish, event, step
from providers import MODELS, ProviderError
from knowledge import bp as knowledge_bp
from werkzeug.utils import secure_filename
from io import BytesIO

from config import Config
from services.comparison_service import ComparisonService
from services.dictionary_service import DictionaryService
from services.document_service import DocumentService
from services.tax_service import TaxService

app = Flask(__name__)
app.register_blueprint(knowledge_bp)

@app.before_request
def start_request():
    begin()
    g.provider = request.headers.get('X-AI-Provider', os.getenv('DEFAULT_PROVIDER', 'openai'))
    if g.provider not in MODELS:
        raise ValueError('Provider must be openai or cohere')
    event('request_started', method=request.method, path=request.path, provider=g.provider)

@app.after_request
def end_request(response):
    metrics = finish()
    if response.is_json and isinstance(response.get_json(), dict):
        payload = response.get_json()
        payload['telemetry'] = metrics
        response.set_data(app.json.dumps(payload))
    response.headers['X-Request-ID'] = g.request_id
    response.headers['Server-Timing'] = f"total;dur={metrics['total_ms']}"
    event('request_finished', method=request.method, path=request.path, status=response.status_code, **metrics)
    return response

@app.errorhandler(Exception)
def handle_error(exc):
    status = exc.code if isinstance(exc, HTTPException) else exc.status if isinstance(exc, ProviderError) else 400 if isinstance(exc, ValueError) else 500
    event('request_error', error_type=type(exc).__name__, status=status)
    return jsonify(error=str(exc) if status < 500 or isinstance(exc, ProviderError) else 'Internal server error; see request ID in logs'), status

@app.get('/api/providers')
def provider_status():
    return jsonify(providers={name: {**models, 'configured': bool(os.getenv(name.upper() + '_API_KEY'))} for name, models in MODELS.items()})

@app.get('/')
@app.get('/<path:path>')
def frontend(path='index.html'):
    root = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
    if path.startswith('api/'):
        return jsonify(error='Endpoint not found'), 404
    return send_from_directory(root, path if (root / path).is_file() else 'index.html')
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024

comparison_service = ComparisonService()
dictionary_service = DictionaryService()
tax_service = TaxService()


@app.get("/api/exports/<run_id>/<path:filename>")
def download_comparison(run_id, filename):
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("Invalid export ID")
    return send_from_directory(Config.DEFAULT_OUTPUT_DIR / run_id, filename, as_attachment=True)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "zakat-tax-toolkit"})


@app.post("/api/comparisons/run")
def run_comparisons():
    try:
        output_dir = str(Config.DEFAULT_OUTPUT_DIR / g.request_id)
        pairs_raw = request.form.get("pairs", "[]")
        pairs = json.loads(pairs_raw)
        if not isinstance(pairs, list) or not pairs or any(not isinstance(pair, dict) or not pair.get("older") or not pair.get("newer") or pair["older"] == pair["newer"] for pair in pairs):
            raise ValueError("Choose at least one pair of distinct older and newer contracts")

        files = request.files.getlist("files")
        file_map = {f.filename: f for f in files if f and f.filename}

        if not file_map:
            return jsonify({"error": "No files uploaded"}), 400

        results = comparison_service.run_batch(file_map, pairs, output_dir)
        return jsonify({"results": results})
    except Exception as exc:
        raise


@app.get("/api/dictionary")
def get_dictionary():
    return jsonify(dictionary_service.load())


@app.post("/api/dictionary")
def upsert_dictionary():
    body = request.get_json(force=True)
    key = body.get("word", "").strip()
    replacement = body.get("replacement", "").strip()
    case_sensitive = bool(body.get("case_sensitive", False))
    if not key or not replacement:
        return jsonify({"error": "Both word and replacement are required"}), 400

    updated = dictionary_service.upsert(key, replacement, case_sensitive=case_sensitive)
    return jsonify(updated)


@app.delete("/api/dictionary")
def clear_dictionary():
    return jsonify(dictionary_service.clear())


@app.delete("/api/dictionary/<key>")
def delete_dictionary_key(key):
    return jsonify(dictionary_service.delete(key))


@app.post("/api/dictionary/import")
def import_dictionary():
    mode = request.form.get("mode", "merge")
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "CSV or XLSX dictionary file is required"}), 400

    with step("dictionary_import", mode=mode):
        updated = dictionary_service.import_file(file, mode=mode)
    return jsonify(updated)


@app.get("/api/dictionary/export")
def export_dictionary():
    fmt = request.args.get("format", "json")
    if fmt == "csv":
        csv_content = dictionary_service.export_csv()
        return send_file(
            BytesIO(csv_content.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="replacement_dictionary.csv",
        )

    data = json.dumps(dictionary_service.load(), ensure_ascii=False, indent=2)
    return send_file(
        BytesIO(data.encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name="replacement_dictionary.json",
    )


@app.post("/api/tax/analyze")
def analyze_tax():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "Contract file is required"}), 400

        temp_path = DocumentService.save_temp_file(file)
        try:
            with step("document_extraction"):
                text = DocumentService.extract_text(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if not text.strip():
            return jsonify({"error": "No text extracted from file"}), 400

        mode = request.form.get('analysis_mode', 'general')
        if mode not in ('general', 'grounded'):
            raise ValueError('analysis_mode must be general or grounded')
        selected_ids = json.loads(request.form.get('selected_doc_ids', '[]'))
        if not isinstance(selected_ids, list) or any(not isinstance(item, str) for item in selected_ids):
            raise ValueError('selected_doc_ids must be a list of document IDs')
        results = tax_service.analyze_contract(text, file_name=Path(file.filename).name, selected_doc_ids=selected_ids, analysis_mode=mode)
        return jsonify(results)
    except Exception as exc:
        raise


@app.post("/api/tax/export/excel")
def export_tax_excel():
    body = request.get_json(force=True)
    with step("excel_export"):
        excel_bytes = tax_service.export_excel(body)
    return send_file(
        BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="enhanced_tax_analysis.xlsx",
    )


@app.post("/api/tax/export/json")
def export_tax_json():
    body = request.get_json(force=True)
    data = json.dumps(body, ensure_ascii=False, indent=2)
    return send_file(
        BytesIO(data.encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name="enhanced_tax_analysis.json",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
