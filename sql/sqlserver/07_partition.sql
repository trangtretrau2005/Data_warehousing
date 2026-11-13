USE CoffeeDW;
GO
IF OBJECT_ID('bench.SalesPart') IS NOT NULL
 THROW 50102,'Partition benchmark already exists; reuse it for measurements.',1;
DECLARE @d date='20120201',@bounds nvarchar(max)=N'';
WHILE @d<='20131201'
BEGIN
 SET @bounds+=CASE WHEN @bounds=N'' THEN N'' ELSE N',' END+QUOTENAME(CONVERT(char(8),@d,112),'''');
 SET @d=DATEADD(month,1,@d);
END;
IF NOT EXISTS(SELECT 1 FROM sys.partition_functions WHERE name='pfCoffee')
 EXEC(N'CREATE PARTITION FUNCTION pfCoffee(date) AS RANGE RIGHT FOR VALUES ('+@bounds+N')');
IF NOT EXISTS(SELECT 1 FROM sys.partition_schemes WHERE name='psCoffee')
 EXEC(N'CREATE PARTITION SCHEME psCoffee AS PARTITION pfCoffee ALL TO ([PRIMARY])');
CREATE TABLE bench.SalesPart (
 MonthStart date NOT NULL,Market nvarchar(40) NOT NULL,
 LocationKey int NOT NULL,ProductKey int NOT NULL,SalesAmount decimal(19,4) NOT NULL
) ON psCoffee(MonthStart);
INSERT bench.SalesPart SELECT * FROM bench.SalesPlain;
-- 23 boundaries -> 24 partitions for this historical dataset.
SELECT $PARTITION.pfCoffee(MonthStart) Part,COUNT_BIG(*) Rows,SUM(SalesAmount) Sales
FROM bench.SalesPart GROUP BY $PARTITION.pfCoffee(MonthStart) ORDER BY Part;
SELECT MonthStart,Market,LocationKey,ProductKey,COUNT_BIG(*) N,SUM(SalesAmount) Sales
FROM bench.SalesPlain GROUP BY MonthStart,Market,LocationKey,ProductKey
EXCEPT SELECT MonthStart,Market,LocationKey,ProductKey,COUNT_BIG(*),SUM(SalesAmount)
FROM bench.SalesPart GROUP BY MonthStart,Market,LocationKey,ProductKey OPTION(EXPAND VIEWS);
SELECT MonthStart,Market,LocationKey,ProductKey,COUNT_BIG(*) N,SUM(SalesAmount) Sales
FROM bench.SalesPart GROUP BY MonthStart,Market,LocationKey,ProductKey
EXCEPT SELECT MonthStart,Market,LocationKey,ProductKey,COUNT_BIG(*),SUM(SalesAmount)
FROM bench.SalesPlain GROUP BY MonthStart,Market,LocationKey,ProductKey OPTION(EXPAND VIEWS);
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
DECLARE @lo date='20121001',@hi date='20121101';
SELECT Market,SUM(SalesAmount) Sales FROM bench.SalesPlain
WHERE MonthStart>=@lo AND MonthStart<@hi GROUP BY Market OPTION(RECOMPILE,EXPAND VIEWS);
SELECT Market,SUM(SalesAmount) Sales FROM bench.SalesPart
WHERE MonthStart>=@lo AND MonthStart<@hi GROUP BY Market OPTION(RECOMPILE,EXPAND VIEWS);
-- Save Actual Partition Count/Partitions Accessed; then repeat for all 24 months.
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
