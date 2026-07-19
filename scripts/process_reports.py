\
from __future__ import annotations
import argparse, json
from pathlib import Path
from normalization import load_aliases
from import_gojek_pdf import import_gojek_pdf
from import_grab_pdf import import_grab_pdf
from build_analytics import build


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='local_data')
    ap.add_argument('--aliases',default='config/private_aliases.json')
    ap.add_argument('--output',default='docs/data/analytics.local.json')
    args=ap.parse_args()
    aliases=load_aliases(args.aliases); root=Path(args.input); records=[]
    for p in sorted((root/'gojek').glob('*.pdf')): records.extend(import_gojek_pdf(p,aliases))
    for p in sorted((root/'grab').glob('*.pdf')): records.extend(import_grab_pdf(p,aliases))
    # De-duplicate overlapping monthly reports without retaining booking codes.
    unique={}
    for r in records:
        key=(r['provider'],r['datetime'],r['origin'],r['destination'],r['amount'],r['currency'],r['category'])
        unique[key]=r
    out=build(list(unique.values()))
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(f'Processed {len(unique)} unique transactions -> {args.output}')

if __name__=='__main__':main()
