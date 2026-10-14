"""Reproduce the 2025 table from two archived IRS PDFs (authoring dependency only)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from validate_model import ROOT, ModelError, require
from validate_interactions import seal


def extract_rows(pages):
    rows = []
    for number, text in pages:
        for line in text.splitlines():
            if re.fullmatch(r'(?:[0-9,]+\s+){5}[0-9,]+', line.strip()):
                values = [int(x.replace(',', '')) for x in line.split()]
                rows.append({'lower': values[0], 'upper_exclusive': values[1], 'tax': values[2:], 'pdf_page': number})
    rows.sort(key=lambda r:r['lower'])
    edge = 0
    for row in rows:
        require(row['lower'] == edge and row['upper_exclusive'] > edge, 'Table overlap, gap or duplicate row')
        edge = row['upper_exclusive']
    require(edge == 100000 and len(rows) == 2062, 'Incomplete IRS table extraction')
    return rows


def reproduce(root=ROOT):
    from pypdf import PdfReader
    ledger = json.loads((root / 'model/claim-ledger.json').read_text())
    sources = {s['id']:s for s in ledger['sources']}
    texts = []
    for id, start, end in [('p1040-2025-snapshot', 2, 13), ('i1040-2025-snapshot', 68, 79)]:
        source = sources[id]
        path = root / source['path']
        require(hashlib.sha256(path.read_bytes()).hexdigest() == source['content_sha256'], 'Archived IRS PDF bytes changed')
        pdf = PdfReader(path)
        require(len(pdf.pages) == source['pdf_pages'], 'PDF page count changed')
        texts.append(extract_rows((n, pdf.pages[n-1].extract_text()) for n in range(start,end+1)))
    projection = lambda rows:[{k:v for k,v in row.items() if k != 'pdf_page'} for row in rows]
    require(projection(texts[0]) == projection(texts[1]), 'IRS publications disagree or extraction failed')
    table = json.loads((root / 'model/ordinary-tax-table-2025-v1.json').read_text())
    result = {**table, 'rows':texts[0]}
    result['sha256'] = seal(result)
    require(result == table, 'Imported table differs from pinned artifact')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        result = reproduce()
        with args.output.open('x') as file:file.write(json.dumps(result,indent=2)+'\n')
        print('Verified all 2,062 intervals against both archived IRS publications.')
        return 0
    except (ModelError,OSError,ValueError,ImportError):
        print('Table import failed; install authoring requirements and check archived inputs/output.',file=sys.stderr)
        return 1


if __name__ == '__main__':raise SystemExit(main())
