USE CoffeeDW;
GO
IF OBJECT_ID('bench.IdxA') IS NOT NULL OR OBJECT_ID('bench.IdxB') IS NOT NULL
 THROW 50103,'Index benchmark already exists; reuse the controlled A/B tables.',1;
SELECT * INTO bench.IdxA FROM bench.SalesPlain;
SELECT * INTO bench.IdxB FROM bench.SalesPlain;
CREATE NONCLUSTERED INDEX IX_AreaProductMonth ON bench.IdxB
 (LocationKey,ProductKey,MonthStart) INCLUDE(SalesAmount);
DECLARE @location int=(SELECT LocationKey FROM dw.DimLocation WHERE AreaCode=N'719'),
 @product int=(SELECT ProductKey FROM dw.DimProduct WHERE ProductName=N'Amaretto'),
 @lo date='20120101',@hi date='20120401';
SELECT @location LocationKey,@product ProductKey,@lo Lo,@hi Hi;
SELECT COUNT_BIG(*) MatchedRows,1.0*COUNT_BIG(*)/(SELECT COUNT_BIG(*) FROM bench.IdxA) Selectivity
FROM bench.IdxA WHERE LocationKey=@location AND ProductKey=@product AND MonthStart>=@lo AND MonthStart<@hi;
SELECT * FROM bench.IdxA EXCEPT SELECT * FROM bench.IdxB;
SELECT * FROM bench.IdxB EXCEPT SELECT * FROM bench.IdxA;
SELECT 'A' Variant,COUNT_BIG(*) Rows,SUM(SalesAmount) Sales FROM bench.IdxA
UNION ALL SELECT 'B',COUNT_BIG(*),SUM(SalesAmount) FROM bench.IdxB;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SELECT MonthStart,SUM(SalesAmount) Sales FROM bench.IdxA
WHERE LocationKey=@location AND ProductKey=@product AND MonthStart>=@lo AND MonthStart<@hi
GROUP BY MonthStart OPTION(RECOMPILE);
SELECT MonthStart,SUM(SalesAmount) Sales FROM bench.IdxB
WHERE LocationKey=@location AND ProductKey=@product AND MonthStart>=@lo AND MonthStart<@hi
GROUP BY MonthStart OPTION(RECOMPILE);
-- Broad control: preserve both plans even if the optimizer chooses scans.
SELECT SUM(SalesAmount) Sales FROM bench.IdxA;
SELECT SUM(SalesAmount) Sales FROM bench.IdxB;
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
