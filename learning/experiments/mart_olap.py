"""TN05 & TN06: Mart cell-by-cell reconciliation, drill-across without fan-out, and OLAP slices."""

import json
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from coffee_dw.config import RESULTS_DIR, SOURCE_PATH
from coffee_dw.source import MEASURES, read_source
from coffee_dw.warehouse import connect, load


def run_tn05(connection, source_df: pd.DataFrame) -> dict:
    # 1. Cell-by-cell reconciliation of vw_MarketPeriod (96 groups) and vw_MarketProductPeriod (1008 groups)
    mart_mp = pd.read_sql_query(
        "SELECT MonthStart, Market, Sales, BudgetSales, Profit, Gap, BudgetAchievement "
        "FROM vw_MarketPeriod ORDER BY MonthStart, Market",
        connection,
    )
    src_mp = (
        source_df.assign(MonthStart=source_df.MonthStart.dt.strftime("%Y-%m-%d"))
        .groupby(["MonthStart", "Market"], as_index=False)[["Sales", "BudgetSales", "Profit"]]
        .sum()
        .sort_values(["MonthStart", "Market"])
        .reset_index(drop=True)
    )
    src_mp["Gap"] = src_mp["Sales"] - src_mp["BudgetSales"]
    src_mp["BudgetAchievement"] = src_mp["Sales"] / src_mp["BudgetSales"]

    assert len(mart_mp) == 96
    max_diff_mp = {
        col: float((mart_mp[col] - src_mp[col]).abs().max())
        for col in ["Sales", "BudgetSales", "Profit", "Gap", "BudgetAchievement"]
    }
    assert all(v < 1e-9 for v in max_diff_mp.values())

    mart_mpp = pd.read_sql_query(
        "SELECT MonthStart, Market, ProductName, Sales, BudgetSales, Profit, Gap "
        "FROM vw_MarketProductPeriod ORDER BY MonthStart, Market, ProductName",
        connection,
    )
    src_mpp = (
        source_df.assign(MonthStart=source_df.MonthStart.dt.strftime("%Y-%m-%d"))
        .groupby(["MonthStart", "Market", "ProductName"], as_index=False)[["Sales", "BudgetSales", "Profit"]]
        .sum()
        .sort_values(["MonthStart", "Market", "ProductName"])
        .reset_index(drop=True)
    )
    src_mpp["Gap"] = src_mpp["Sales"] - src_mpp["BudgetSales"]
    assert len(mart_mpp) == 1008
    max_diff_mpp = {
        col: float((mart_mpp[col] - src_mpp[col]).abs().max())
        for col in ["Sales", "BudgetSales", "Profit", "Gap"]
    }
    assert all(v < 1e-9 for v in max_diff_mpp.values())

    # 2. Drill-across: pre-aggregate Actual and Budget independently at MonthStart x Market, then FULL OUTER JOIN
    connection.executescript("""
        DROP TABLE IF EXISTS temp_Actual;
        DROP TABLE IF EXISTS temp_Budget;
        CREATE TEMP TABLE temp_Actual AS
            SELECT MonthStart, Market, SUM(Sales) AS Sales
            FROM vw_Detail GROUP BY MonthStart, Market;
        CREATE TEMP TABLE temp_Budget AS
            SELECT MonthStart, Market, SUM(BudgetSales) AS BudgetSales
            FROM vw_Detail GROUP BY MonthStart, Market;
    """)
    baseline_join = pd.read_sql_query("""
        SELECT COUNT(*) AS groups, SUM(a.Sales) AS sales, SUM(b.BudgetSales) AS budget_sales
        FROM temp_Actual a JOIN temp_Budget b
        ON a.MonthStart = b.MonthStart AND a.Market = b.Market
    """, connection).iloc[0].to_dict()
    assert (int(baseline_join["groups"]), float(baseline_join["sales"]), float(baseline_join["budget_sales"])) == (
        96, 819811.0, 746160.0
    )

    # 3. Fan-out anti-pattern demonstration: joining Market-Month budget directly to detail rows before SUM
    fanout = pd.read_sql_query("""
        SELECT SUM(d.Sales) AS sales, SUM(b.BudgetSales) AS inflated_budget_sales,
               SUM(CASE WHEN d.MonthStart='2012-01-01' AND d.Market='West' THEN 1 ELSE 0 END) AS west_jan2012_detail_rows,
               SUM(CASE WHEN d.MonthStart='2012-01-01' AND d.Market='West' THEN b.BudgetSales ELSE 0 END) AS west_jan2012_inflated_budget
        FROM vw_Detail d JOIN temp_Budget b
        ON d.MonthStart = b.MonthStart AND d.Market = b.Market
    """, connection).iloc[0].to_dict()
    assert float(fanout["inflated_budget_sales"]) > float(baseline_join["budget_sales"])
    assert int(fanout["west_jan2012_detail_rows"]) == 56
    assert float(fanout["west_jan2012_inflated_budget"]) == 9460.0 * 56

    # 4. Synthetic missing budget (delete 2012-01-01 West) and future plan-only (insert 2014-01-01 West = 1000)
    connection.executescript("""
        DELETE FROM temp_Budget WHERE MonthStart = '2012-01-01' AND Market = 'West';
        INSERT INTO temp_Budget VALUES ('2014-01-01', 'West', 1000.0);
    """)
    full_outer = pd.read_sql_query("""
        SELECT COALESCE(a.MonthStart, b.MonthStart) AS MonthStart,
               COALESCE(a.Market, b.Market) AS Market,
               a.Sales, b.BudgetSales, a.Sales - b.BudgetSales AS Gap,
               CASE WHEN a.MonthStart IS NULL THEN 1 ELSE 0 END AS MissingActual,
               CASE WHEN b.MonthStart IS NULL THEN 1 ELSE 0 END AS MissingBudget
        FROM temp_Actual a FULL OUTER JOIN temp_Budget b
        ON a.MonthStart = b.MonthStart AND a.Market = b.Market
        WHERE a.MonthStart IS NULL OR b.MonthStart IS NULL
        ORDER BY MonthStart, Market
    """, connection)
    anomalies = full_outer.to_dict("records")
    assert len(anomalies) == 2
    assert anomalies[0]["MonthStart"] == "2012-01-01" and anomalies[0]["Market"] == "West"
    assert anomalies[0]["Sales"] == 10453.0 and pd.isna(anomalies[0]["BudgetSales"]) and anomalies[0]["MissingBudget"] == 1
    assert anomalies[1]["MonthStart"] == "2014-01-01" and anomalies[1]["Market"] == "West"
    assert pd.isna(anomalies[1]["Sales"]) and anomalies[1]["BudgetSales"] == 1000.0 and anomalies[1]["MissingActual"] == 1

    return {
        "experiment": "TN05",
        "mart_market_period_groups": len(mart_mp),
        "mart_market_product_period_groups": len(mart_mpp),
        "max_abs_diff_market_period": max_diff_mp,
        "max_abs_diff_market_product_period": max_diff_mpp,
        "drill_across_baseline": baseline_join,
        "fanout_antipattern": fanout,
        "full_outer_join_missing_groups": [
            {k: (None if pd.isna(v) else v) for k, v in row.items()} for row in anomalies
        ],
    }


def run_tn06(connection) -> dict:
    # 1. All-period Market summary (Chapter 5.1)
    market_summary = pd.read_sql_query("""
        SELECT Market, SUM(Sales) AS Sales, SUM(BudgetSales) AS BudgetSales,
               SUM(Sales) - SUM(BudgetSales) AS Gap, SUM(Profit) AS Profit,
               ROUND(SUM(Sales) / NULLIF(SUM(BudgetSales), 0), 6) AS BudgetAchievement,
               ROUND(SUM(Profit) / NULLIF(SUM(Sales), 0), 6) AS ProfitMargin
        FROM vw_Detail GROUP BY Market ORDER BY Market
    """, connection).to_dict("records")

    # 2. Slice & Drill-down 2012-01-01 Central by State (Report 5.4: Total Sales 10346, Budget 9970)
    central_states = pd.read_sql_query("""
        SELECT State, SUM(Sales) AS Sales, SUM(BudgetSales) AS BudgetSales,
               SUM(Profit) AS Profit, SUM(Sales) - SUM(BudgetSales) AS Gap
        FROM vw_Detail
        WHERE MonthStart = '2012-01-01' AND Market = 'Central'
        GROUP BY State ORDER BY State
    """, connection)
    assert (float(central_states.Sales.sum()), float(central_states.BudgetSales.sum())) == (10346.0, 9970.0)

    # 3. Slice & Drill-down 2012-01-01 West by State (Handbook TN06: Total Sales 10453, Budget 9460, Profit 2356)
    west_states = pd.read_sql_query("""
        SELECT State, SUM(Sales) AS Sales, SUM(BudgetSales) AS BudgetSales,
               SUM(Profit) AS Profit, SUM(Sales) - SUM(BudgetSales) AS Gap
        FROM vw_Detail
        WHERE MonthStart = '2012-01-01' AND Market = 'West'
        GROUP BY State ORDER BY State
    """, connection)
    assert (float(west_states.Sales.sum()), float(west_states.BudgetSales.sum()), float(west_states.Profit.sum())) == (
        10453.0, 9460.0, 2356.0
    )

    # 4. Dice & Pivot 2012-01-01, Central + East, ProductType = Coffee (2663 + 2105 = 4768)
    dice_by_market = pd.read_sql_query("""
        SELECT Market, SUM(Sales) AS Sales, SUM(BudgetSales) AS BudgetSales, SUM(Profit) AS Profit
        FROM vw_Detail
        WHERE MonthStart = '2012-01-01' AND Market IN ('Central', 'East') AND ProductType = 'Coffee'
        GROUP BY Market ORDER BY Market
    """, connection)
    pivot_by_product = pd.read_sql_query("""
        SELECT ProductName,
               SUM(CASE WHEN Market = 'Central' THEN Sales ELSE 0 END) AS Central_Sales,
               SUM(CASE WHEN Market = 'East' THEN Sales ELSE 0 END) AS East_Sales,
               SUM(Sales) AS Total_Sales
        FROM vw_Detail
        WHERE MonthStart = '2012-01-01' AND Market IN ('Central', 'East') AND ProductType = 'Coffee'
        GROUP BY ProductName ORDER BY ProductName
    """, connection)
    assert dice_by_market.set_index("Market")["Sales"].to_dict() == {"Central": 2663.0, "East": 2105.0}
    assert float(dice_by_market.Sales.sum()) == 4768.0
    assert float(pivot_by_product.Total_Sales.sum()) == 4768.0

    # 5. Diagnostic slice South 2013-08-01 (Sales 4601, Budget 4610, Gap -9)
    south_aug2013 = pd.read_sql_query("""
        SELECT ProductName, Sales, BudgetSales, Gap, Profit
        FROM vw_MarketProductPeriod
        WHERE MonthStart = '2013-08-01' AND Market = 'South'
        ORDER BY Gap ASC, ProductName ASC
    """, connection)
    assert (float(south_aug2013.Sales.sum()), float(south_aug2013.BudgetSales.sum()), float(south_aug2013.Gap.sum())) == (
        4601.0, 4610.0, -9.0
    )
    assert south_aug2013.iloc[0]["ProductName"] == "Colombian" and float(south_aug2013.iloc[0]["Gap"]) == -268.0
    assert south_aug2013.iloc[1]["ProductName"] == "Decaf Irish Cream" and float(south_aug2013.iloc[1]["Gap"]) == -105.0

    # 6. Semi-additive Inventory snapshot at latest month (2013-12-01)
    ending_inventory = pd.read_sql_query("""
        SELECT MonthStart, Market, SUM(Inventory) AS EndingInventory
        FROM vw_Detail
        WHERE MonthStart = (SELECT MAX(MonthStart) FROM vw_Detail)
        GROUP BY MonthStart, Market ORDER BY Market
    """, connection).to_dict("records")

    return {
        "experiment": "TN06",
        "market_all_periods": market_summary,
        "slice_2012_01_central_states": central_states.to_dict("records"),
        "slice_2012_01_central_total": {
            "Sales": float(central_states.Sales.sum()),
            "BudgetSales": float(central_states.BudgetSales.sum()),
            "Profit": float(central_states.Profit.sum()),
        },
        "slice_2012_01_west_states": west_states.to_dict("records"),
        "slice_2012_01_west_total": {
            "Sales": float(west_states.Sales.sum()),
            "BudgetSales": float(west_states.BudgetSales.sum()),
            "Profit": float(west_states.Profit.sum()),
            "BudgetAchievement": round(float(west_states.Sales.sum() / west_states.BudgetSales.sum()), 6),
        },
        "dice_2012_01_central_east_coffee_by_market": dice_by_market.to_dict("records"),
        "pivot_2012_01_central_east_coffee_by_product": pivot_by_product.to_dict("records"),
        "dice_pivot_grand_total_sales": float(pivot_by_product.Total_Sales.sum()),
        "south_2013_08_products_by_gap": south_aug2013.to_dict("records"),
        "south_2013_08_total": {
            "Sales": float(south_aug2013.Sales.sum()),
            "BudgetSales": float(south_aug2013.BudgetSales.sum()),
            "Gap": float(south_aug2013.Gap.sum()),
        },
        "ending_inventory_2013_12": ending_inventory,
    }


def run() -> dict:
    source_df, _ = read_source(SOURCE_PATH)
    with TemporaryDirectory(prefix="coffee-mart-olap-") as temp:
        db_path = Path(temp) / "mart_olap.sqlite"
        load(SOURCE_PATH, db_path)
        connection = connect(db_path)
        try:
            tn05 = run_tn05(connection, source_df)
            tn06 = run_tn06(connection)
            return {"engine": "SQLite & pandas cross-check", "source_modified": False, "TN05": tn05, "TN06": tn06}
        finally:
            connection.close()


if __name__ == "__main__":
    result = run()
    for code in ("TN05", "TN06"):
        out = RESULTS_DIR / code / f"{code.lower()}_summary.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result[code], indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
