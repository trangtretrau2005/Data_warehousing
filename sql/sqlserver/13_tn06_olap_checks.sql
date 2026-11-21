USE CoffeeDW;
GO
-- TN06 & Chapter 5: Multi-dimensional OLAP equivalence checks on SQL Server.
-- Used to cross-validate SSAS Cube / MDX queries (ssas/queries.mdx) cell-by-cell.
SET NOCOUNT ON;

-- 1. Chapter 5.1 Table: All-period performance by Market + Grand Total (ROLLUP)
SELECT
    ISNULL(Market, N'Toàn chuỗi') AS Market,
    SUM(Sales) AS Sales,
    SUM(BudgetSales) AS BudgetSales,
    SUM(Sales) - SUM(BudgetSales) AS Gap,
    SUM(Profit) AS Profit,
    CAST(SUM(Sales) / NULLIF(SUM(BudgetSales), 0) AS decimal(10,4)) AS BudgetAchievement,
    CAST(SUM(Profit) / NULLIF(SUM(Sales), 0) AS decimal(10,4)) AS ProfitMargin
FROM mart.vw_Detail
GROUP BY ROLLUP(Market)
ORDER BY CASE WHEN Market IS NULL THEN 1 ELSE 0 END, Market;

-- 2. TN06 Slice & Drill-down (Report 5.4): 2012-01-01 Central by State + Roll-up Total
SELECT
    ISNULL(State, N'Tổng Central') AS State,
    SUM(Sales) AS Sales,
    SUM(BudgetSales) AS BudgetSales,
    SUM(Profit) AS Profit,
    SUM(Sales) - SUM(BudgetSales) AS Gap,
    CAST(SUM(Sales) / NULLIF(SUM(BudgetSales), 0) AS decimal(10,4)) AS BudgetAchievement
FROM mart.vw_Detail
WHERE DateKey = 20120101 AND Market = N'Central'
GROUP BY ROLLUP(State)
ORDER BY CASE WHEN State IS NULL THEN 1 ELSE 0 END, State;

-- 3. TN06 Slice & Drill-down (Handbook TN06): 2012-01-01 West by State + GROUPING SETS Roll-up
SELECT
    MonthStart,
    Market,
    ISNULL(State, N'Tổng West') AS State,
    SUM(Sales) AS Sales,
    SUM(BudgetSales) AS BudgetSales,
    SUM(Profit) AS Profit,
    CAST(SUM(Sales) / NULLIF(SUM(BudgetSales), 0) AS decimal(10,4)) AS BudgetAchievement
FROM mart.vw_Detail
WHERE DateKey = 20120101 AND Market = N'West'
GROUP BY GROUPING SETS ((MonthStart, Market, State), (MonthStart, Market))
ORDER BY CASE WHEN State IS NULL THEN 1 ELSE 0 END, State;

-- 4. TN06 Dice (Report 5.5): 2012-01-01, Markets Central + East, ProductType = Coffee
-- By Market (2663 + 2105 = 4768)
SELECT
    ISNULL(Market, N'Tổng lát cắt') AS Market,
    SUM(Sales) AS Sales,
    SUM(BudgetSales) AS BudgetSales,
    SUM(Profit) AS Profit
FROM mart.vw_Detail
WHERE DateKey = 20120101
  AND Market IN (N'Central', N'East')
  AND ProductType = N'Coffee'
GROUP BY ROLLUP(Market)
ORDER BY CASE WHEN Market IS NULL THEN 1 ELSE 0 END, Market;

-- 5. TN06 Pivot (Report 5.5): Same filter (2012-01-01, Central + East, Coffee),
-- pivoted with ProductName on rows and Market on columns; grand total remains 4768.
SELECT
    ISNULL(ProductName, N'Tổng lát cắt') AS ProductName,
    SUM(CASE WHEN Market = N'Central' THEN Sales ELSE 0 END) AS Central_Sales,
    SUM(CASE WHEN Market = N'East' THEN Sales ELSE 0 END) AS East_Sales,
    SUM(Sales) AS Total_Sales
FROM mart.vw_Detail
WHERE DateKey = 20120101
  AND Market IN (N'Central', N'East')
  AND ProductType = N'Coffee'
GROUP BY ROLLUP(ProductName)
ORDER BY CASE WHEN ProductName IS NULL THEN 1 ELSE 0 END, ProductName;

-- 6. Chapter 5.6 Diagnostic Drill-down: South 2013-08-01 (Sales 4601, Budget 4610, Gap -9)
-- Ranked by signed Gap ascending (Colombian -268, Decaf Irish Cream -105, Chamomile +22)
SELECT
    ISNULL(ProductName, N'Tổng South 08/2013') AS ProductName,
    SUM(Sales) AS Sales,
    SUM(BudgetSales) AS BudgetSales,
    SUM(Sales) - SUM(BudgetSales) AS Gap,
    SUM(Profit) AS Profit
FROM mart.vw_MarketProductPeriod
WHERE MonthStart = '2013-08-01' AND Market = N'South'
GROUP BY ROLLUP(ProductName)
ORDER BY CASE WHEN ProductName IS NULL THEN 1 ELSE 0 END,
         SUM(Sales) - SUM(BudgetSales) ASC,
         ProductName ASC;

-- 7. Semi-additive Inventory policy check: latest selected period (2013-12-01) by Market
SELECT
    MonthStart,
    ISNULL(Market, N'Toàn chuỗi (kỳ cuối)') AS Market,
    SUM(Inventory) AS EndingInventory
FROM mart.vw_Detail
WHERE MonthStart = (SELECT MAX(MonthStart) FROM mart.vw_Detail)
GROUP BY MonthStart, ROLLUP(Market)
ORDER BY CASE WHEN Market IS NULL THEN 1 ELSE 0 END, Market;

-- 8. Cube Browser MDX Slice Check (DateKey = 20131101 / 2013-11-01 by Market)
SELECT
    Market,
    CAST(SUM(Sales) AS int) AS Sales,
    CAST(SUM(BudgetSales) AS int) AS [Budget Sales],
    CAST(SUM(Sales) - SUM(BudgetSales) AS int) AS Gap,
    CAST(SUM(Profit) AS int) AS Profit
FROM mart.vw_Detail
WHERE DateKey = 20131101
GROUP BY Market
ORDER BY Market;
GO
