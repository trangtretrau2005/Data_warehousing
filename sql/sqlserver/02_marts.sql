USE CoffeeDW;
GO
CREATE OR ALTER VIEW mart.vw_Detail AS
SELECT d.MonthStart,f.DateKey,l.AreaCode,l.State,l.Market,l.MarketSize,
 p.ProductName,p.ProductLine,p.ProductType,p.[Type],
 f.Sales,f.BudgetSales,f.Profit,f.BudgetProfit,f.COGS,f.BudgetCOGS,
 f.Margin,f.BudgetMargin,f.Marketing,f.Inventory,f.TotalExpenses,f.SourceRow,
 f.BatchID,l.LocationKey,p.ProductKey
FROM dw.FactSalesPerformance f
JOIN dw.DimDate d ON d.DateKey=f.DateKey
JOIN dw.DimLocation l ON l.LocationKey=f.LocationKey
JOIN dw.DimProduct p ON p.ProductKey=f.ProductKey;
GO
CREATE OR ALTER VIEW mart.vw_MarketPeriod AS
SELECT MonthStart,Market,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,
 SUM(Profit) Profit,SUM(Sales)-SUM(BudgetSales) Gap,
 SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement
FROM mart.vw_Detail GROUP BY MonthStart,Market;
GO
CREATE OR ALTER VIEW mart.vw_MarketProductPeriod AS
SELECT MonthStart,Market,ProductName,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,
 SUM(Profit) Profit,SUM(Sales)-SUM(BudgetSales) Gap
FROM mart.vw_Detail GROUP BY MonthStart,Market,ProductName;
GO
