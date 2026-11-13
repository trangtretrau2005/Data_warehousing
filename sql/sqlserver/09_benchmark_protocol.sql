USE CoffeeDW;
GO
-- Edit A/B together for TN09/TN10. Keep same scope, types, parameters and output.
-- Record row counts, two-way EXCEPT, versions, storage and actual plans FIRST.
SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON; SET QUOTED_IDENTIFIER ON; SET NUMERIC_ROUNDABORT OFF;
DECLARE @A nvarchar(max)=N'SELECT MonthStart,Market,ProductKey,SUM(SalesAmount) Sales
 FROM bench.SalesPlain GROUP BY MonthStart,Market,ProductKey OPTION(EXPAND VIEWS)',
 @B nvarchar(max)=N'SELECT MonthStart,Market,ProductKey,Sales FROM bench.vSalesAgg WITH(NOEXPAND)',
 @i int=1;
-- Three warm-up executions per variant, under the same cache policy.
WHILE @i<=3
BEGIN
 EXEC sys.sp_executesql @A;
 EXEC sys.sp_executesql @B;
 SET @i+=1;
END;
SET STATISTICS IO ON; SET STATISTICS TIME ON;
SET @i=1;
WHILE @i<=15
BEGIN
 -- Odd runs AB, even runs BA. Copy exact Messages to benchmark_runs.csv.
 IF @i%2=1
 BEGIN
  PRINT CONCAT('run=',@i,',variant=A'); EXEC sys.sp_executesql @A;
  PRINT CONCAT('run=',@i,',variant=B'); EXEC sys.sp_executesql @B;
 END
 ELSE
 BEGIN
  PRINT CONCAT('run=',@i,',variant=B'); EXEC sys.sp_executesql @B;
  PRINT CONCAT('run=',@i,',variant=A'); EXEC sys.sp_executesql @A;
 END;
 SET @i+=1;
END;
SET STATISTICS IO OFF; SET STATISTICS TIME OFF;
-- Do not use DBCC DROPCLEANBUFFERS on a shared server. No invented speedups.
SELECT OBJECT_SCHEMA_NAME(object_id) SchemaName,OBJECT_NAME(object_id) ObjectName,
 SUM(reserved_page_count)*8 ReservedKB
FROM sys.dm_db_partition_stats WHERE OBJECT_SCHEMA_NAME(object_id)='bench'
GROUP BY object_id;
GO
