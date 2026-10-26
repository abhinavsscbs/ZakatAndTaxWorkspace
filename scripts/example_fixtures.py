"""Generate synthetic benchmark inputs locally; never publish uploaded documents."""
from pathlib import Path

FIXTURES = {
    'reference.txt': 'SYNTHETIC BENCHMARK POLICY — not actual law.\nArticle 1: Under this fictional policy, the standard VAT rate is 15 percent.\nArticle 2: Quarterly filings are due on the last day of the following month.\nArticle 3: Questions about Zakat thresholds cannot be answered from this policy.\n',
    'older.txt': 'Services Agreement\n1. The Customer pays SAR 100,000 within 30 days of invoice receipt.\n2. The Supplier delivers consulting services for twelve months.\n3. Either party may terminate on 60 days written notice.\n4. All fees exclude applicable VAT, which is shown separately on invoices.\n',
    'newer.txt': 'Services Agreement\n1. The Customer pays SAR 120,000 within 15 days of invoice receipt.\n2. The Supplier delivers consulting services for twelve months.\n3. Either party may terminate on 30 days written notice.\n4. All fees exclude applicable VAT, which is shown separately on invoices.\n',
}

def prepare(directory=None):
    directory = Path(directory) if directory else Path(__file__).resolve().parent / 'fixtures'
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in FIXTURES.items():
        path = directory / name
        if not path.exists():
            path.write_text(text, encoding='utf-8')
    return directory

if __name__ == '__main__':
    print(prepare())
