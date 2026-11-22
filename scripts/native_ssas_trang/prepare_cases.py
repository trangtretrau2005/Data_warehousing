"""Prepare read-only MDX cases and matching SQL expected values, without SSAS writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyodbc

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "ssas/CoffeeCubeTrang"
EVIDENCE = ROOT / "results/native_build_20261120/ssas/integrated_ssis_source"
CUBE = "[Coffee Performance]"
MARKETS = "[Dim Location].[Market].[Market].Members"
MEASURES = "{[Measures].[Sales],[Measures].[Budget Sales],[Measures].[Gap],[Measures].[Profit],[Measures].[Budget Achievement],[Measures].[Profit Margin]}"
SQL_CONN = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=CoffeeDW_Trang_SSIS_TN03_20261120;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"


def query_inventory(inner="", where=""):
    source = f"(SELECT {inner} ON 0 FROM {CUBE})" if inner else CUBE
    return f"SELECT {{[Measures].[Inventory]}} ON 0, NON EMPTY {MARKETS} ON 1 FROM {source}" + (f" WHERE {where}" if where else "")


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cases = [
        {"id": "all_markets_24months", "mdx": f"SELECT {MEASURES} ON 0,{MARKETS} ON 1 FROM {CUBE}",
         "sql": "SELECT Market,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit,SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement,SUM(Profit)/NULLIF(SUM(Sales),0) ProfitMargin FROM mart.vw_Detail GROUP BY Market ORDER BY Market"},
        {"id": "central_201201_states", "mdx": f"SELECT {MEASURES} ON 0, NON EMPTY DESCENDANTS([Dim Location].[Geography].[Market].&[Central],[Dim Location].[Geography].[State],SELF) ON 1 FROM {CUBE} WHERE ([Dim Date].[Date Key].&[20120101])",
         "sql": "SELECT State,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit,SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement,SUM(Profit)/NULLIF(SUM(Sales),0) ProfitMargin FROM mart.vw_Detail WHERE DateKey=20120101 AND Market='Central' GROUP BY State ORDER BY State"},
        {"id": "west_201201_states", "mdx": f"SELECT {MEASURES} ON 0, NON EMPTY DESCENDANTS([Dim Location].[Geography].[Market].&[West],[Dim Location].[Geography].[State],SELF) ON 1 FROM {CUBE} WHERE ([Dim Date].[Date Key].&[20120101])",
         "sql": "SELECT State,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit,SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement,SUM(Profit)/NULLIF(SUM(Sales),0) ProfitMargin FROM mart.vw_Detail WHERE DateKey=20120101 AND Market='West' GROUP BY State ORDER BY State"},
        {"id": "dice_coffee_201201_central_east", "mdx": f"SELECT {{[Measures].[Sales],[Measures].[Budget Sales],[Measures].[Profit]}} ON 0, {{[Dim Location].[Market].&[Central],[Dim Location].[Market].&[East]}} ON 1 FROM {CUBE} WHERE ([Dim Date].[Date Key].&[20120101],[Dim Product].[Product Type].&[Coffee])",
         "sql": "SELECT Market,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit FROM mart.vw_Detail WHERE DateKey=20120101 AND Market IN ('Central','East') AND ProductType='Coffee' GROUP BY Market ORDER BY Market"},
        {"id": "south_201308_signed_gap", "mdx": f"SELECT {{[Measures].[Sales],[Measures].[Budget Sales],[Measures].[Gap],[Measures].[Profit]}} ON 0, ORDER(NONEMPTY([Dim Product].[Product Name].[Product Name].Members,[Measures].[Sales]),[Measures].[Gap],BASC) ON 1 FROM {CUBE} WHERE ([Dim Date].[Date Key].&[20130801],[Dim Location].[Market].&[South])",
         "sql": "SELECT ProductName,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit FROM mart.vw_Detail WHERE DateKey=20130801 AND Market='South' GROUP BY ProductName ORDER BY Gap,ProductName"},
        {"id": "budget_zero_preserves_null_ratio", "mdx": f"SELECT {MEASURES} ON 0, {{[Dim Product].[Product Name].&[Green Tea]}} ON 1 FROM {CUBE} WHERE ([Dim Date].[Date Key].&[20120101],[Dim Location].[Area Code].&[702])",
         "sql": "SELECT N'Green Tea' ProductName,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit,SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement,SUM(Profit)/NULLIF(SUM(Sales),0) ProfitMargin FROM mart.vw_Detail WHERE DateKey=20120101 AND AreaCode='702' AND ProductName='Green Tea'"},
        {"id": "joint_dates_markets_ratio_from_totals", "mdx": f"SELECT {MEASURES} ON 0, {{[Dim Location].[Market].[All]}} ON 1 FROM (SELECT {{[Dim Date].[Date Key].&[20120101],[Dim Date].[Date Key].&[20130801]}} ON 0, {{[Dim Location].[Market].&[Central],[Dim Location].[Market].&[East]}} ON 1 FROM {CUBE})",
         "sql": "SELECT N'All' Market,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Sales)-SUM(BudgetSales) Gap,SUM(Profit) Profit,SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement,SUM(Profit)/NULLIF(SUM(Sales),0) ProfitMargin FROM mart.vw_Detail WHERE DateKey IN (20120101,20130801) AND Market IN ('Central','East')"},
        {"id": "inventory_latest_selected_empty_no_fallback", "mdx": f"SELECT {{[Measures].[Inventory]}} ON 0, {{[Dim Product].[Product Name].&[Chamomile]}} ON 1 FROM (SELECT {{[Dim Date].[Date Key].&[20130101],[Dim Date].[Date Key].&[20130801]}} ON 0 FROM {CUBE}) WHERE ([Dim Location].[Area Code].&[720])",
         "sql": "SELECT N'Chamomile' ProductName,SUM(Inventory) Inventory FROM mart.vw_Detail WHERE DateKey=20130801 AND AreaCode='720' AND ProductName='Chamomile'",
         "expected_inventory_month": "2013-08-01", "inventory_policy": "latest selected August is empty; do not fall back to January Inventory1091"},
    ]
    inventory_cases = [
        ("inventory_all", "", "", "2013-12-01", ""),
        ("inventory_month_201312", "", "([Dim Date].[Date Key].&[20131201])", "2013-12-01", ""),
        ("inventory_year_2012", "", "([Dim Date].[Calendar].[Year].&[2012])", "2012-12-01", ""),
        ("inventory_year_2013", "", "([Dim Date].[Calendar].[Year].&[2013])", "2013-12-01", ""),
        ("inventory_quarter_2013q2", "", "([Dim Date].[Calendar].[Quarter].&[2013]&[2])", "2013-06-01", ""),
        ("inventory_range_feb_may2013", "{[Dim Date].[Date Key].&[20130201]:[Dim Date].[Date Key].&[20130501]}", "", "2013-05-01", ""),
        ("inventory_noncontiguous_jan_aug2013", "{[Dim Date].[Date Key].&[20130101],[Dim Date].[Date Key].&[20130801]}", "", "2013-08-01", ""),
        ("inventory_where_set_jan_aug2013", "", "{[Dim Date].[Date Key].&[20130101],[Dim Date].[Date Key].&[20130801]}", "2013-08-01", ""),
        ("inventory_colombian_aug_nov2013", "{[Dim Date].[Date Key].&[20130801],[Dim Date].[Date Key].&[20131101]}", "([Dim Product].[Product Name].&[Colombian])", "2013-11-01", " AND ProductName='Colombian'"),
    ]
    for case_id, inner, where, date, product_filter in inventory_cases:
        cases.append({"id": case_id, "mdx": query_inventory(inner, where),
                      "sql": f"SELECT Market,SUM(Inventory) Inventory FROM mart.vw_Detail WHERE MonthStart='{date}'{product_filter} GROUP BY Market ORDER BY Market",
                      "expected_inventory_month": date, "inventory_policy": "maximum selected month, not sum across time or last nonempty fallback"})
    connection = pyodbc.connect(SQL_CONN, timeout=10)
    expected_files = []
    try:
        actual_catalog = connection.cursor().execute("SELECT DB_NAME()").fetchone()[0]
        if actual_catalog != "CoffeeDW_Trang_SSIS_TN03_20261120":
            raise RuntimeError("Independent expected values must come from the integrated SSIS catalog.")
        for case in cases:
            cursor = connection.cursor()
            cursor.execute(case["sql"])
            columns = [item[0] for item in cursor.description]
            records = cursor.fetchall()
            frame = pd.DataFrame.from_records(records, columns=columns)
            path = EVIDENCE / "sql_expected" / (case["id"] + ".csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            case["sql_expected_csv"] = str(path.relative_to(ROOT)).replace("\\", "/")
            case["expected_rows"] = len(frame)
            expected_files.append({"path": case["sql_expected_csv"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    finally:
        connection.close()
    script = "-- Read-only SSAS acceptance cases; connect to CoffeeCube_Trang_20261120.\n-- Each Inventory context must match SQL at MAX(selected MonthStart).\n\n"
    for case in cases:
        script += f"-- CASE {case['id']}\n{case['mdx']};\n\n"
    (TARGET / "acceptance_cases.mdx").write_text(script, encoding="utf-8")
    bundle = {"server": r"localhost\TRANGTRETRAU", "database": "CoffeeCube_Trang_20261120", "cube": "Coffee Performance",
              "case_count": len(cases), "cases": cases, "expected_source": "SQL Server relational source, read-only queries",
              "source_database": "CoffeeDW_Trang_SSIS_TN03_20261120", "ssas_execution_status": "not_executed_by_preparation", "expected_files": expected_files}
    (EVIDENCE / "acceptance_cases.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"prepared_cases": len(cases), "ssas_executed": False, "expected_sql_csvs": len(expected_files)}))


if __name__ == "__main__":
    main()
