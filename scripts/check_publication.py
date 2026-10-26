"""Reject runtime artifacts, documents, binaries, and credential patterns in tracked files."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = {'.gitignore', '.env.example', 'README.md'}
SOURCE_DIRS = {'backend', 'frontend', 'scripts', 'tests', 'docs', '.github'}
SUFFIXES = {'.py', '.js', '.jsx', '.css', '.html', '.md', '.json', '.yml', '.yaml'}


def allowed(path):
    parts = path.parts
    if str(path) in TOP_LEVEL or str(path) == 'backend/requirements.txt':
        return True
    return (parts[0] in SOURCE_DIRS and path.suffix in SUFFIXES
            and not any(part in {'node_modules','dist','__pycache__','fixtures'} for part in parts)
            and path.name not in {'replacement_dictionary.json'})


def source_files():
    candidates = [ROOT / name for name in TOP_LEVEL]
    for directory in SOURCE_DIRS:
        candidates.extend((ROOT / directory).rglob('*'))
    return sorted(path.relative_to(ROOT) for path in candidates if path.is_file() and allowed(path.relative_to(ROOT)))


def main():
    top = subprocess.run(['git','rev-parse','--show-toplevel'],cwd=ROOT,capture_output=True,text=True)
    if top.returncode == 0 and Path(top.stdout.strip()).resolve() == ROOT:
        files = [Path(name) for name in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()]
    else:
        files = source_files()
    errors=[]
    for path in files:
        if not allowed(path):
            errors.append(f'Disallowed tracked file: {path}')
            continue
        try:
            text=(ROOT/path).read_text(encoding='utf-8')
        except (UnicodeError,OSError):
            errors.append(f'Not a UTF-8 source file: {path}')
            continue
        if re.search(r'sk-(?:proj-)?[A-Za-z0-9_-]{24,}',text) or re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text) or re.search(r'gh[pousr]_[A-Za-z0-9]{30,}',text):
            errors.append(f'Possible credential in: {path}')
    if errors:
        print('\n'.join(errors));return 1
    print(f'Publication check passed: {len(files)} source/configuration/documentation files; no uploaded documents or runtime data.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
