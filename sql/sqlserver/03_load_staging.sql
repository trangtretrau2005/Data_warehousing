USE CoffeeDW;
GO
-- Staging is populated by scripts/load_sqlserver.py or the equivalent SSIS flow.
CREATE OR ALTER PROCEDURE dw.usp_LoadCoffee @BatchID uniqueidentifier AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRY
  BEGIN TRANSACTION;
  DECLARE @lock int;
  EXEC @lock=sys.sp_getapplock @Resource=N'CoffeeDW.Load',@LockMode='Exclusive',
       @LockOwner='Transaction',@LockTimeout=10000;
  IF @lock<0 THROW 50000,'Could not lock CoffeeDW loader',1;
  IF NOT EXISTS(SELECT 1 FROM audit.LoadBatch WHERE BatchID=@BatchID AND Status='STAGED')
   THROW 50001,'Batch does not exist or was already processed',1;
  INSERT audit.RejectedRow(BatchID,SourceRow,Reason,RawJson)
   SELECT BatchID,SourceRow,RejectReason,RawJson FROM stg.CoffeeRaw
   WHERE BatchID=@BatchID AND RejectReason IS NOT NULL;
  SELECT * INTO #v FROM stg.CoffeeRaw WHERE BatchID=@BatchID AND RejectReason IS NULL;
  IF EXISTS(SELECT 1 FROM #v WHERE DateKey IS NULL OR MonthStart IS NULL OR DAY(MonthStart)<>1
   OR DateKey<>CONVERT(int,CONVERT(char(8),MonthStart,112))
   OR NULLIF(AreaCode,'') IS NULL OR NULLIF(ProductName,'') IS NULL
   OR State IS NULL OR Market IS NULL OR MarketSize IS NULL
   OR ProductLine IS NULL OR ProductType IS NULL OR [Type] IS NULL
   OR Sales IS NULL OR BudgetSales IS NULL OR Profit IS NULL OR BudgetProfit IS NULL OR COGS IS NULL OR BudgetCOGS IS NULL OR Margin IS NULL OR BudgetMargin IS NULL OR Marketing IS NULL OR Inventory IS NULL OR TotalExpenses IS NULL)
   THROW 50002,'Unvalidated row in staging; use the shared source rules',1;
  IF EXISTS(SELECT 1 FROM #v GROUP BY DateKey,AreaCode,ProductName HAVING COUNT(*)>1)
   THROW 50003,'Duplicate source grain',1;
  IF EXISTS(SELECT AreaCode FROM #v GROUP BY AreaCode HAVING COUNT(DISTINCT State)>1
     OR COUNT(DISTINCT Market)>1 OR COUNT(DISTINCT MarketSize)>1)
   OR EXISTS(SELECT ProductName FROM #v GROUP BY ProductName HAVING COUNT(DISTINCT ProductLine)>1
     OR COUNT(DISTINCT ProductType)>1 OR COUNT(DISTINCT [Type])>1)
   THROW 50004,'Conflicting dimension attributes',1;
  INSERT dw.DimDate(DateKey,MonthStart,[Year],[Quarter],[Month])
   SELECT DISTINCT DateKey,MonthStart,YEAR(MonthStart),DATEPART(quarter,MonthStart),MONTH(MonthStart)
   FROM #v v WHERE NOT EXISTS(SELECT 1 FROM dw.DimDate d WHERE d.DateKey=v.DateKey);
  -- Type 1 only in serving dimensions. Synthetic SCD2 is isolated in TN04.
  UPDATE l SET State=v.State,Market=v.Market,MarketSize=v.MarketSize
   FROM dw.DimLocation l JOIN (SELECT DISTINCT AreaCode,State,Market,MarketSize FROM #v) v
   ON l.AreaCode=v.AreaCode;
  INSERT dw.DimLocation(AreaCode,State,Market,MarketSize)
   SELECT DISTINCT AreaCode,State,Market,MarketSize FROM #v v
   WHERE NOT EXISTS(SELECT 1 FROM dw.DimLocation l WHERE l.AreaCode=v.AreaCode);
  UPDATE p SET ProductLine=v.ProductLine,ProductType=v.ProductType,[Type]=v.[Type]
   FROM dw.DimProduct p JOIN (SELECT DISTINCT ProductName,ProductLine,ProductType,[Type] FROM #v) v
   ON p.ProductName=v.ProductName;
  INSERT dw.DimProduct(ProductName,ProductLine,ProductType,[Type])
   SELECT DISTINCT ProductName,ProductLine,ProductType,[Type] FROM #v v
   WHERE NOT EXISTS(SELECT 1 FROM dw.DimProduct p WHERE p.ProductName=v.ProductName);
  SELECT v.*,l.LocationKey,p.ProductKey INTO #mapped
   FROM #v v JOIN dw.DimLocation l ON l.AreaCode=v.AreaCode
   JOIN dw.DimProduct p ON p.ProductName=v.ProductName;
  DECLARE @accepted int=(SELECT COUNT(*) FROM #mapped),@updated int,@inserted int;
  UPDATE f SET Sales=v.Sales,BudgetSales=v.BudgetSales,Profit=v.Profit,BudgetProfit=v.BudgetProfit,COGS=v.COGS,BudgetCOGS=v.BudgetCOGS,Margin=v.Margin,BudgetMargin=v.BudgetMargin,Marketing=v.Marketing,Inventory=v.Inventory,TotalExpenses=v.TotalExpenses,
   BatchID=@BatchID,SourceRow=v.SourceRow
   FROM dw.FactSalesPerformance f JOIN #mapped v ON f.DateKey=v.DateKey
   AND f.LocationKey=v.LocationKey AND f.ProductKey=v.ProductKey
   WHERE EXISTS(SELECT v.Sales,v.BudgetSales,v.Profit,v.BudgetProfit,v.COGS,v.BudgetCOGS,v.Margin,v.BudgetMargin,v.Marketing,v.Inventory,v.TotalExpenses EXCEPT SELECT f.Sales,f.BudgetSales,f.Profit,f.BudgetProfit,f.COGS,f.BudgetCOGS,f.Margin,f.BudgetMargin,f.Marketing,f.Inventory,f.TotalExpenses);
  SET @updated=@@ROWCOUNT;
  INSERT dw.FactSalesPerformance(DateKey,LocationKey,ProductKey,Sales,BudgetSales,Profit,BudgetProfit,COGS,BudgetCOGS,Margin,BudgetMargin,Marketing,Inventory,TotalExpenses,BatchID,SourceRow)
   SELECT DateKey,LocationKey,ProductKey,Sales,BudgetSales,Profit,BudgetProfit,COGS,BudgetCOGS,Margin,BudgetMargin,Marketing,Inventory,TotalExpenses,@BatchID,SourceRow
   FROM #mapped v WHERE NOT EXISTS(SELECT 1 FROM dw.FactSalesPerformance f
    WHERE f.DateKey=v.DateKey AND f.LocationKey=v.LocationKey AND f.ProductKey=v.ProductKey);
  SET @inserted=@@ROWCOUNT;
  IF EXISTS(
   SELECT v.DateKey,v.LocationKey,v.ProductKey,v.Sales,v.BudgetSales,v.Profit,v.BudgetProfit,v.COGS,v.BudgetCOGS,v.Margin,v.BudgetMargin,v.Marketing,v.Inventory,v.TotalExpenses FROM #mapped v
    JOIN dw.FactSalesPerformance f ON f.DateKey=v.DateKey AND f.LocationKey=v.LocationKey
    AND f.ProductKey=v.ProductKey
   EXCEPT SELECT f.DateKey,f.LocationKey,f.ProductKey,f.Sales,f.BudgetSales,f.Profit,f.BudgetProfit,f.COGS,f.BudgetCOGS,f.Margin,f.BudgetMargin,f.Marketing,f.Inventory,f.TotalExpenses FROM #mapped v
    JOIN dw.FactSalesPerformance f ON f.DateKey=v.DateKey AND f.LocationKey=v.LocationKey
    AND f.ProductKey=v.ProductKey)
   THROW 50005,'Reconciliation failed',1;
  IF (SELECT SourceCount FROM audit.LoadBatch WHERE BatchID=@BatchID)
   <> @accepted+(SELECT COUNT(*) FROM audit.RejectedRow WHERE BatchID=@BatchID)
   THROW 50006,'Source row accounting failed',1;
  UPDATE audit.LoadBatch SET Status='COMPLETED',FinishedAt=SYSUTCDATETIME(),
   AcceptedCount=@accepted,RejectedCount=(SELECT COUNT(*) FROM audit.RejectedRow WHERE BatchID=@BatchID),
   InsertedCount=@inserted,UpdatedCount=@updated,UnchangedCount=@accepted-@inserted-@updated
   WHERE BatchID=@BatchID;
  COMMIT TRANSACTION;
  SELECT * FROM audit.LoadBatch WHERE BatchID=@BatchID;
 END TRY
 BEGIN CATCH
  IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
  THROW;
 END CATCH
END;
GO
