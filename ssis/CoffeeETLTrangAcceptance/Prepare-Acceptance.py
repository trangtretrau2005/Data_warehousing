"""Prepare eight native SSDT inputs and package IDs. No SQL, UI or execution."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',default='CoffeeDW_Trang_SSIS_TN03_20261120')
    args=parser.parse_args()
    if not re.fullmatch(r'CoffeeDW_Trang_[A-Za-z0-9_]+',args.database): raise ValueError('Isolated DB required')
    fixtures=ROOT/'results/native_build_20261120/ssis/fixtures'
    original=ROOT/'data/raw/Coffee.csv'
    source_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    if source_hash!='929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce':
        raise ValueError('This acceptance protocol requires the unchanged reference snapshot')
    cases=[
      ('01_First23',fixtures/'first_23_months.csv',4071,0,4071,0,0,4071,784231),
      ('02_AddDecember',fixtures/'month_201312.csv',177,0,177,0,0,4248,819811),
      ('03_ReplayDecember',fixtures/'month_201312.csv',177,0,0,0,177,4248,819811),
      ('04_CorrectSales',fixtures/'correction_sales_plus_10.csv',4248,0,0,1,4247,4248,819821),
      ('05_RestoreOriginal',original,4248,0,0,1,4247,4248,819811),
      ('06_FullOneBadNumeric',fixtures/'invalid_full_one_numeric.csv',4247,1,0,0,4247,4248,819811),
      ('07_InvalidEight',fixtures/'invalid_8_rows.csv',6,2,0,0,6,4248,819811),
      ('08_FinalOriginal',original,4248,0,0,0,4248,4248,819811),
    ]
    suite_id=str(uuid4())
    manifest={'suite_id':suite_id,'database':args.database,'server':'.','prepared_utc':datetime.now(timezone.utc).isoformat(),
      'status':'PREPARED_NOT_EXECUTED','parent_package':'00_AcceptAll.dtsx','source_sha256':source_hash,
      'execution_policy':'One supported SSDT F5 on parent. Never invoke DtsDebugHost directly or bypass runtime edition checks.',
      'precondition':'Target DB already initialized; fact must be empty. No drop/delete/reset by this project.',
      'cases':[]}
    xml=ET.Element('Acceptance',SuiteID=suite_id,Database=args.database)
    for number,(name,path,accepted,rejected,inserted,updated,unchanged,warehouse_rows,sales) in enumerate(cases,1):
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream); rows=list(reader)
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        assert len(rows)==accepted+rejected
        # The two malformed fixtures preserve source order and have known bad rows.
        valid_rows=rows[(2 if number==7 else 1 if number==6 else 0):]
        valid_sales=sum(Decimal(r['Sales']) for r in valid_rows)
        if number==1:
            budget=sum(Decimal(r['Budget Sales']) for r in rows)
            profit=sum(Decimal(r['Profit']) for r in rows)
        else: budget,profit=Decimal(746160),Decimal(259543)
        case={'number':number,'package':name+'.dtsx','batch_id':str(uuid4()),'source_path':str(path.resolve()),
          'source_filename':path.name,'source_sha256':sha,'source_count':len(rows),
          'expected_accepted':accepted,'expected_rejected':rejected,'expected_inserted':inserted,
          'expected_updated':updated,'expected_unchanged':unchanged,'expected_valid_sales':str(valid_sales),
          'expected_warehouse_rows':warehouse_rows,'expected_warehouse_sales':sales,
          'expected_warehouse_budget':str(budget),'expected_warehouse_profit':str(profit)}
        manifest['cases'].append(case)
        ET.SubElement(xml,'Case',**{k:str(v) for k,v in case.items()})
    data=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    (HERE/'acceptance_manifest.json').write_bytes(data)
    xml.set('ManifestSHA256',hashlib.sha256(data).hexdigest())
    ET.indent(xml)
    ET.ElementTree(xml).write(HERE/'acceptance_inputs.xml',encoding='utf-8',xml_declaration=True)
    print(f'Prepared SuiteID={suite_id}; eight unique BatchIDs; no package/database execution')


if __name__=='__main__':main()
