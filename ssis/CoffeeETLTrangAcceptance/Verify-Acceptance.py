"""Read-only proof after one supported SSDT F5. Never runs/debugs a package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=HERE/'acceptance_manifest.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    raw=args.manifest.read_bytes(); manifest=json.loads(raw)
    if not re.fullmatch(r'CoffeeDW_Trang_[A-Za-z0-9_]+',manifest['database']):raise ValueError('Isolated DB required')
    folder=args.output or ROOT/'results/native_build_20261120/ssis/acceptance_runs'/manifest['suite_id']
    folder.mkdir(parents=True,exist_ok=True)
    result={'suite_id':manifest['suite_id'],'status':'NOT_VERIFIED','manifest_sha256':hashlib.sha256(raw).hexdigest(),'failures':[],'case_verification':[]}
    import pyodbc
    cn=pyodbc.connect(f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={manifest['server']};DATABASE={manifest['database']};Trusted_Connection=yes;TrustServerCertificate=yes;",autocommit=True)
    def fetch(sql,*values):
        cursor=cn.cursor().execute(sql,values)
        return [dict(zip((c[0] for c in cursor.description),row)) for row in cursor.fetchall()]
    try:
        exists=fetch("SELECT OBJECT_ID('audit.SSISAcceptanceSuite') ObjectID")[0]['ObjectID']
        if exists is None:
            result['failures'].append('No acceptance suite table: parent has not passed preflight/executed')
        else:
            suite=fetch('SELECT * FROM audit.SSISAcceptanceSuite WHERE SuiteID=?',manifest['suite_id'])
            receipts=fetch('SELECT * FROM audit.SSISAcceptanceCase WHERE SuiteID=? ORDER BY CaseNumber',manifest['suite_id'])
            result.update(native_suite=suite,native_case_receipts=receipts)
            if len(suite)!=1 or suite[0]['Status']!='PASS':result['failures'].append('Native parent has no PASS receipt')
            if suite and suite[0]['ManifestSHA256']!=result['manifest_sha256']:result['failures'].append('Native manifest checksum mismatch')
            if len(receipts)!=8:result['failures'].append('Eight native case receipts required')
            if not result['failures']:
                for case,receipt in zip(manifest['cases'],receipts):
                    if str(receipt['BatchID']).lower()!=case['batch_id'].lower():result['failures'].append(f"Case{case['number']} BatchID mismatch")
                    if hashlib.sha256(Path(case['source_path']).read_bytes()).hexdigest()!=case['source_sha256']:result['failures'].append(f"Case{case['number']} fixture changed since build")
                    if receipt['WarehouseRows']!=case['expected_warehouse_rows'] or receipt['WarehouseSales']!=case['expected_warehouse_sales']:result['failures'].append(f"Case{case['number']} native receipt totals mismatch")
                    output=folder/f"case_{case['number']:02d}.json"
                    env=dict(os.environ,PYTHONIOENCODING='utf-8')
                    command=[sys.executable,str(HERE.parent/'CoffeeETLTrang/Verify-NativeBatch.py'),'--source',case['source_path'],'--batch-id',case['batch_id'],'--database',manifest['database'],'--server',manifest['server'],'--output',str(output)]
                    completed=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)
                    (folder/f"case_{case['number']:02d}.log").write_text(completed.stdout+'\n'+completed.stderr,encoding='utf-8')
                    result['case_verification'].append({'number':case['number'],'exit_code':completed.returncode,'path':str(output)})
                    if completed.returncode!=0:result['failures'].append(f"Case{case['number']} raw/typed parser comparison failed")
        final=fetch('SELECT COUNT_BIG(*) Rows,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit FROM dw.FactSalesPerformance')[0]
        result['final_warehouse']=final
        if (final['Rows'],final['Sales'],final['BudgetSales'],final['Profit'])!=(4248,819811,746160,259543):result['failures'].append('Final original warehouse totals not restored')
        result['status']='PASS' if not result['failures'] else 'NOT_EXECUTED_OR_FAILED'
    finally:
        cn.close()
        (folder/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,default=str))
    if result['failures']:raise SystemExit(1)


if __name__=='__main__':main()
