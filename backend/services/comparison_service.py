import json
import os
import re
from io import BytesIO
from pathlib import Path
import pandas as pd
from openpyxl.styles import Alignment, Font

from cohere_client import CohereClient
from telemetry import step
from flask import g
from config import Config
from services.document_service import DocumentService
from services.dictionary_service import DictionaryService


class ComparisonService:
    IMPACT_LEVELS = ["Not At All", "Slight", "Moderate", "Significant", "Extreme"]

    def __init__(self):
        self.ai = CohereClient()
        self.dict_service = DictionaryService()

    def apply_replacements(self, text):
        return DictionaryService.replace(text, self.dict_service.load())[0]

    def _extract_json(self, raw):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise
            return json.loads(match.group(0))

    def compare_texts(self, older_text, newer_text):
        prompt = f"""
Compare the two contracts and return JSON only in this schema:
{{
  "differences": [
    {{
      "difference_number": 1,
      "older_contract": "exact quote or Not Mentioned",
      "newer_contract": "exact quote or Not Mentioned",
      "difference_summary": "short summary",
      "impact_score": "one of: {', '.join(self.IMPACT_LEVELS)}"
    }}
  ],
  "overall_summary": "single concise conclusion"
}}

Rules:
- No markdown, no commentary, no extra keys.
- Use exact snippets from provided text.
- Do not include identical clauses.
- If no differences, return empty differences and explain that in overall_summary.

OLDER CONTRACT:
{older_text[:22000]}

NEWER CONTRACT:
{newer_text[:22000]}
"""
        raw = self.ai.chat(
            "You are a legal contract analyst. Return valid JSON only.",
            prompt,
            temperature=0.1,
            step_name="contract_comparison",
        )
        with step("comparison_validation"):
            data = self._extract_json(raw)
            if not isinstance(data, dict) or not isinstance(data.get("differences"), list) or not isinstance(data.get("overall_summary"), str):
                raise ValueError("Provider returned invalid comparison structure")
            for difference in data["differences"]:
                if not isinstance(difference, dict) or difference.get("impact_score") not in self.IMPACT_LEVELS:
                    raise ValueError("Provider returned invalid difference structure")
                for key, text in (("older_contract", older_text), ("newer_contract", newer_text)):
                    quote = difference.get(key)
                    if not isinstance(quote, str) or (quote != "Not Mentioned" and quote not in text):
                        raise ValueError("Provider returned a comparison quote absent from the source")
            return data

    def _to_excel(self, comparison_json, older_name, newer_name, output_dir):
        differences = comparison_json.get("differences", [])
        overall = comparison_json.get("overall_summary", "")

        rows = []
        for idx, item in enumerate(differences, start=1):
            rows.append(
                {
                    "Difference number": idx,
                    "Older Contract": item.get("older_contract", ""),
                    "Newer Contract": item.get("newer_contract", ""),
                    "Difference Summary": item.get("difference_summary", ""),
                    "Difference": item.get("difference_summary", ""),
                    "Impact Score": item.get("impact_score", ""),
                    "Overall Summary": overall,
                }
            )

        if not rows:
            rows = [
                {
                    "Difference number": "",
                    "Older Contract": "",
                    "Newer Contract": "",
                    "Difference Summary": "No material differences detected",
                    "Difference": "",
                    "Impact Score": "",
                    "Overall Summary": overall or "Contracts appear materially similar.",
                }
            ]

        df = pd.DataFrame(rows)
        safe_older = Path(older_name).name.replace("/", "_")
        safe_newer = Path(newer_name).name.replace("/", "_")

        output_dir = Path(output_dir or Config.DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"Comparison_{safe_older}_vs_{safe_newer}.xlsx"

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Comparison", index=False)
            ws = writer.sheets["Comparison"]
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 24

        return str(out_path)

    def run_single_pair(self, older_file, newer_file, output_dir):
        older_path = newer_path = None
        try:
            older_path = DocumentService.save_temp_file(older_file)
            newer_path = DocumentService.save_temp_file(newer_file)
            with step("document_extraction"):
                older_text = self.apply_replacements(DocumentService.extract_text(older_path))
                newer_text = self.apply_replacements(DocumentService.extract_text(newer_path))
            if not older_text or not newer_text:
                raise ValueError("Both contracts must contain readable text")
            if max(len(older_text), len(newer_text)) > 22000:
                raise ValueError("Each contract must be at most 22,000 characters; split longer contracts into sections")

            result_json = self.compare_texts(older_text, newer_text)
            with step("excel_export"):
                excel_path = self._to_excel(result_json, older_file.filename, newer_file.filename, output_dir)
            return {
                "older": older_file.filename,
                "newer": newer_file.filename,
                "comparison": result_json,
                "excel_path": excel_path,
                "download_url": "/api/exports/" + g.request_id + "/" + Path(excel_path).name,
            }
        finally:
            for p in [older_path, newer_path]:
                if p and os.path.exists(p):
                    os.remove(p)

    def run_batch(self, file_map, pairs, output_dir):
        results = []
        for i, pair in enumerate(pairs, start=1):
            older = file_map.get(pair.get("older"))
            newer = file_map.get(pair.get("newer"))
            if not older or not newer:
                results.append({
                    "pair": i,
                    "success": False,
                    "error": "Invalid file mapping in pair",
                    "older": pair.get("older"),
                    "newer": pair.get("newer"),
                })
                continue

            try:
                output = self.run_single_pair(older, newer, output_dir)
                results.append({"pair": i, "success": True, **output})
            except Exception as exc:
                results.append(
                    {
                        "pair": i,
                        "success": False,
                        "older": pair.get("older"),
                        "newer": pair.get("newer"),
                        "error": str(exc),
                    }
                )
        return results
