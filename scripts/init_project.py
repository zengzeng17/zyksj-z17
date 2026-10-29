#!/usr/bin/env python3
"""Install the reusable authoring scaffold without overwriting any file."""
import argparse,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.output.expanduser().resolve();asset=Path(__file__).resolve().parents[1]/'assets/project';created=[];kept=[]
root.mkdir(parents=True,exist_ok=True)
for src in asset.rglob('*'):
 if not src.is_file():continue
 dst=root/src.relative_to(asset)
 if dst.exists():kept.append(str(dst.relative_to(root)));continue
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);created.append(str(dst.relative_to(root)))
for n in ['cases','references']:(root/n).mkdir(exist_ok=True)
contract=root/'docs/data-format.md'
if not contract.exists():shutil.copy2(Path(__file__).resolve().parents[1]/'references/report-contract.md',contract);created.append('docs/data-format.md')
print(json.dumps({'project':str(root),'created':created,'preserved_existing':kept},ensure_ascii=False))
