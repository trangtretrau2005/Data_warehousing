USE CoffeeDW;
GO
SET NOCOUNT ON;
-- Dedicated synthetic workload, never added to serving fact or forecast input.
IF OBJECT_ID('bench.SalesPlain') IS NOT NULL
 THROW 50100,'Benchmark already exists. Reuse it, or create a separate experiment database.',1;
DECLARE @Copies int=500; -- 4248*500 = 2124000; record this parameter with every run.
IF NOT EXISTS(SELECT 1 FROM dw.FactSalesPerformance) THROW 50101,'Load the warehouse first',1;
CREATE TABLE bench.SalesPlain (
 MonthStart date NOT NULL,Market nvarchar(40) NOT NULL,
 LocationKey int NOT NULL,ProductKey int NOT NULL,SalesAmount decimal(19,4) NOT NULL
);
;WITH n AS (SELECT 1 i UNION ALL SELECT i+1 FROM n WHERE i<@Copies)
INSERT bench.SalesPlain
SELECT d.MonthStart,l.Market,f.LocationKey,f.ProductKey,f.Sales
FROM dw.FactSalesPerformance f JOIN dw.DimDate d ON f.DateKey=d.DateKey
JOIN dw.DimLocation l ON f.LocationKey=l.LocationKey CROSS JOIN n
OPTION(MAXRECURSION 0);
SELECT @@VERSION EngineVersion;
SELECT @Copies Copies,COUNT_BIG(*) Rows,SUM(SalesAmount) Sales FROM bench.SalesPlain;
SELECT MonthStart,COUNT_BIG(*) Rows,SUM(SalesAmount) Sales
FROM bench.SalesPlain GROUP BY MonthStart ORDER BY MonthStart;
GO
