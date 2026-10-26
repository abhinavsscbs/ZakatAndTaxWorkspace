import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path
from filelock import FileLock
from config import Config


class DictionaryService:
    """Shared disk-backed dictionary. Lock updates and atomically replace JSON."""
    @property
    def path(self):
        return Path(Config.DICTIONARY_FILE).resolve()

    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(str(self.path) + '.lock', timeout=15)

    def load(self):
        # Atomic replacement makes unlocked readers see the old or new complete file.
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or any(not isinstance(key, str) or not key or not isinstance(value, str) for key, value in data.items()):
            raise ValueError('Replacement dictionary must be a JSON object of nonempty terms to replacement strings')
        return data

    def _write(self, data):
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.dictionary-', suffix='.json', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as target:
                json.dump(data, target, indent=2, ensure_ascii=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def save(self, data):
        with self._lock():
            self._write(data)

    def upsert(self, key, value, case_sensitive=False):
        with self._lock():
            data = self.load()
            # One case-insensitive entry per term; preserve the existing flat JSON format.
            for existing in list(data):
                if existing.casefold() == key.casefold():
                    del data[existing]
            data[key] = value
            self._write(data)
            return data

    def delete(self, key):
        with self._lock():
            data = self.load()
            data.pop(key, None)
            self._write(data)
            return data

    def clear(self):
        self.save({})
        return {}

    def import_file(self, file_storage, mode='merge'):
        if mode not in ('merge', 'replace'):
            raise ValueError('Import mode must be merge or replace')
        extension = Path(file_storage.filename or '').suffix.lower()
        if extension == '.csv':
            try:
                rows = list(csv.reader(io.StringIO(file_storage.read().decode('utf-8-sig'))))
            except (UnicodeDecodeError, csv.Error) as exc:
                raise ValueError('Upload a valid UTF-8 CSV with Word and Replacement columns') from exc
        elif extension == '.xlsx':
            from openpyxl import load_workbook
            try:
                workbook = load_workbook(io.BytesIO(file_storage.read()), read_only=True, data_only=False)
                try:
                    rows = list(workbook.worksheets[0].values)
                finally:
                    workbook.close()
            except Exception as exc:
                raise ValueError('Upload a valid .xlsx workbook with Word and Replacement columns on its first sheet') from exc
        else:
            raise ValueError('Upload a .csv or .xlsx dictionary; convert older .xls files to .xlsx first')
        if not rows:
            raise ValueError('Dictionary file is empty')
        headers = [str(value or '').strip().casefold() for value in rows[0]]
        if headers.count('word') != 1 or headers.count('replacement') != 1:
            raise ValueError('Include exactly one Word column and one Replacement column')
        word_index, replacement_index = headers.index('word'), headers.index('replacement')
        incoming = {}
        for number, row in enumerate(rows[1:], 2):
            if not any(value is not None and str(value).strip() for value in row):
                continue
            word = row[word_index] if len(row) > word_index else None
            replacement = row[replacement_index] if len(row) > replacement_index else None
            if word is None or replacement is None or not str(word).strip() or not str(replacement).strip():
                raise ValueError(f'Row {number} needs both a Word and a Replacement; no changes saved')
            if extension == '.xlsx' and any(isinstance(value, str) and value.startswith('=') for value in (word, replacement)):
                raise ValueError(f'Row {number} contains an Excel formula; use literal text values')
            word, replacement = str(word).strip(), str(replacement).strip()
            for existing in list(incoming):
                if existing.casefold() == word.casefold():
                    del incoming[existing]
            incoming[word] = replacement
        if not incoming:
            raise ValueError('No dictionary entries found; no changes saved')
        # Parse and validate the entire upload before touching the shared dictionary.
        with self._lock():
            current = {} if mode == 'replace' else self.load()
            for key, value in incoming.items():
                for existing in list(current):
                    if existing.casefold() == key.casefold():
                        del current[existing]
                current[key] = value
            self._write(current)
            return current

    def import_csv(self, file_storage, mode='merge'):
        return self.import_file(file_storage, mode)

    def export_csv(self):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Word', 'Replacement'])
        writer.writerows(self.load().items())
        return out.getvalue()

    @staticmethod
    def replace(text, replacements):
        if not replacements:
            return text, 0
        # Longest matches first, one pass: replacement values never trigger another rule.
        terms = sorted(replacements, key=len, reverse=True)
        pattern = re.compile('|'.join(re.escape(term) for term in terms), re.IGNORECASE)
        values = {key.lower():value for key, value in replacements.items()}
        return pattern.subn(lambda match: values[match.group(0).lower()], text)
