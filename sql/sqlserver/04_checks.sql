USE CoffeeDW;
GO
-- TN01/TN02: actual results expected only for the supplied unmodified snapshot.
SELECT COUNT_BIG(*) Rows,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit
FROM dw.FactSalesPerformance; -- 4248,819811,746160,259543
SELECT COUNT(*) Dates,MIN(MonthStart) FirstMonth,MAX(MonthStart) LastMonth FROM dw.DimDate;
SELECT COUNT(*) Locations FROM dw.DimLocation; --156
SELECT COUNT(*) Products FROM dw.DimProduct; --13
-- Financial exceptions are warnings; preserve source measures.
SELECT SUM(CASE WHEN Profit<0 THEN 1 ELSE 0 END) NegativeProfit,
 SUM(CASE WHEN Inventory<0 THEN 1 ELSE 0 END) NegativeInventory,
 SUM(CASE WHEN Sales<>COGS+Margin THEN 1 ELSE 0 END) SalesMismatch,
 SUM(CASE WHEN Profit<>Margin-TotalExpenses THEN 1 ELSE 0 END) ProfitMismatch
FROM dw.FactSalesPerformance; --528,88,2088,2105
-- TN03: source=accepted+rejected, accepted=inserted+updated+unchanged.
SELECT *,SourceCount-AcceptedCount-RejectedCount SourceDelta,
 AcceptedCount-InsertedCount-UpdatedCount-UnchangedCount AcceptedDelta FROM audit.LoadBatch;
-- TN06/TN11: same-scope KPI answers.
SELECT * FROM mart.vw_MarketPeriod WHERE MonthStart='20120101' ORDER BY Market;
SELECT State,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales
FROM mart.vw_Detail WHERE MonthStart='20120101' AND Market=N'Central' GROUP BY State;
SELECT Market,SUM(Sales) Sales FROM mart.vw_Detail
WHERE MonthStart='20120101' AND Market IN (N'Central',N'East') AND ProductType=N'Coffee'
GROUP BY Market; --2663,2105
SELECT ProductName,Sales,BudgetSales,Gap FROM mart.vw_MarketProductPeriod
WHERE MonthStart='20130801' AND Market=N'South' ORDER BY Gap,ProductName;
-- No Inventory SUM across months: use latest selected period.
SELECT Market,SUM(Inventory) Inventory FROM mart.vw_Detail
WHERE MonthStart=(SELECT MAX(MonthStart) FROM mart.vw_Detail) GROUP BY Market;
GO
