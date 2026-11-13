USE CoffeeDW;
GO
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;
GO
CREATE OR ALTER VIEW bench.vSalesAgg WITH SCHEMABINDING AS
SELECT MonthStart,Market,ProductKey,COUNT_BIG(*) N,SUM(SalesAmount) Sales
FROM bench.SalesPlain GROUP BY MonthStart,Market,ProductKey;
GO
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('bench.vSalesAgg') AND name='CX_vSalesAgg')
 CREATE UNIQUE CLUSTERED INDEX CX_vSalesAgg ON bench.vSalesAgg(MonthStart,Market,ProductKey);
GO
-- Both EXCEPT result sets must be empty BEFORE measuring. Unique group keys.
SELECT MonthStart,Market,ProductKey,SUM(SalesAmount) Sales FROM bench.SalesPlain
GROUP BY MonthStart,Market,ProductKey
EXCEPT SELECT MonthStart,Market,ProductKey,Sales FROM bench.vSalesAgg WITH(NOEXPAND)
OPTION(EXPAND VIEWS);
SELECT MonthStart,Market,ProductKey,Sales FROM bench.vSalesAgg WITH(NOEXPAND)
EXCEPT SELECT MonthStart,Market,ProductKey,SUM(SalesAmount) FROM bench.SalesPlain
GROUP BY MonthStart,Market,ProductKey OPTION(EXPAND VIEWS);
-- A / B: save separate actual plans and Messages; see 09_benchmark_protocol.sql.
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SELECT MonthStart,Market,ProductKey,SUM(SalesAmount) Sales FROM bench.SalesPlain
GROUP BY MonthStart,Market,ProductKey OPTION(EXPAND VIEWS);
SELECT MonthStart,Market,ProductKey,Sales FROM bench.vSalesAgg WITH(NOEXPAND);
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
-- Indexed-view write maintenance: compare two fresh copies of SalesPlain, add
-- the same batch to each in a transaction, ROLLBACK both. One copy has a matching
-- indexed view. Record elapsed, reads and storage separately from read workload.
-- Sources: https://learn.microsoft.com/en-us/sql/relational-databases/views/create-indexed-views
GO
