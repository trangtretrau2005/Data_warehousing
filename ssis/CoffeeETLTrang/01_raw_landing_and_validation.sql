-- Apply only after SQL01--03, inside an isolated experiment database.
-- This file is staged for review; generating the SSIS package does not run it.
IF DB_NAME() NOT LIKE N'CoffeeDW[_]Trang[_]%'
 THROW 50201,'Use an isolated CoffeeDW_Trang_<run> database',1;
GO
IF OBJECT_ID(N'stg.CoffeeCsvLanding') IS NULL
CREATE TABLE stg.CoffeeCsvLanding (
 LandingID bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
 BatchID nvarchar(36) NOT NULL,
 [Area Code] nvarchar(1024) NULL,[Date] nvarchar(1024) NULL,
 [Market] nvarchar(1024) NULL,[Market Size] nvarchar(1024) NULL,
 [Product] nvarchar(1024) NULL,[Product Line] nvarchar(1024) NULL,
 [Product Type] nvarchar(1024) NULL,[State] nvarchar(1024) NULL,[Type] nvarchar(1024) NULL,
 [Budget COGS] nvarchar(1024) NULL,[Budget Margin] nvarchar(1024) NULL,
 [Budget Profit] nvarchar(1024) NULL,[Budget Sales] nvarchar(1024) NULL,
 [COGS] nvarchar(1024) NULL,[Inventory] nvarchar(1024) NULL,[Margin] nvarchar(1024) NULL,
 [Marketing] nvarchar(1024) NULL,[Profit] nvarchar(1024) NULL,
 [Sales] nvarchar(1024) NULL,[Total Expenses] nvarchar(1024) NULL,
 CONSTRAINT CK_CoffeeCsvLanding_Batch CHECK(TRY_CONVERT(uniqueidentifier,BatchID) IS NOT NULL)
);
GO
CREATE OR ALTER FUNCTION stg.fn_CoffeeTrim(@raw nvarchar(4000)) RETURNS nvarchar(4000) AS
BEGIN
 DECLARE @s nvarchar(4000)=ISNULL(@raw,N'');
 -- Same Unicode whitespace family as Python str.strip(), including NBSP/tabs.
 WHILE LEN(@s+N'#')>1 AND UNICODE(LEFT(@s,1)) IN
 (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
  SET @s=SUBSTRING(@s,2,4000);
 WHILE LEN(@s+N'#')>1 AND UNICODE(RIGHT(@s,1)) IN
 (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
  SET @s=LEFT(@s,LEN(@s+N'#')-2);
 RETURN @s;
END;
GO
CREATE OR ALTER FUNCTION stg.fn_CoffeeNumber(@raw nvarchar(4000),@kind char(1))
RETURNS decimal(19,4) AS
BEGIN
 -- Parse decimal text without float conversion or silent rounding. Kind D is
 -- an integral Excel serial; M follows source._scaled's at-most-four scale.
 DECLARE @s nvarchar(4000)=REPLACE(UPPER(stg.fn_CoffeeTrim(@raw)),N'_',N''),@negative bit=0,
  @e int=0,@point int,@fraction int=0,@digits nvarchar(4000),@canonical nvarchar(4000),
  @epos int,@exptext nvarchar(4000),@expdigits nvarchar(4000),@n decimal(19,4);
 IF @s=N'' RETURN NULL;
 IF LEFT(@s,1) COLLATE Latin1_General_100_BIN2 IN (N'+',N'-')
 BEGIN SET @negative=CASE WHEN LEFT(@s,1)=N'-' THEN 1 ELSE 0 END; SET @s=SUBSTRING(@s,2,4000); END;
 SET @epos=CHARINDEX(N'E',@s COLLATE Latin1_General_100_BIN2);
 IF @epos>0
 BEGIN
  SET @exptext=SUBSTRING(@s,@epos+1,4000);
  SET @expdigits=CASE WHEN LEFT(@exptext,1) COLLATE Latin1_General_100_BIN2 IN (N'+',N'-') THEN SUBSTRING(@exptext,2,4000) ELSE @exptext END;
  IF @expdigits=N'' OR @expdigits COLLATE Latin1_General_100_BIN2 LIKE N'%[^0-9]%' RETURN NULL;
  SET @e=TRY_CONVERT(int,@exptext);
  IF @e IS NULL OR @exptext=N'' RETURN NULL;
  SET @s=LEFT(@s,@epos-1);
 END;
 SET @point=CHARINDEX(N'.',@s COLLATE Latin1_General_100_BIN2);
 IF @point>0
 BEGIN
  SET @fraction=LEN(@s)-@point;
  SET @digits=LEFT(@s,@point-1)+SUBSTRING(@s,@point+1,4000);
 END ELSE SET @digits=@s;
 IF @digits=N'' OR @digits COLLATE Latin1_General_100_BIN2 LIKE N'%[^0-9]%' RETURN NULL;
 IF @e < -100000 OR @e > 100000 RETURN NULL;
 SET @e=@e-@fraction;
 WHILE LEN(@digits)>1 AND LEFT(@digits,1)=N'0' SET @digits=SUBSTRING(@digits,2,4000);
 IF @kind='D'
 BEGIN
  WHILE @e<0 AND LEN(@digits)>1 AND RIGHT(@digits,1)=N'0'
   BEGIN SET @digits=LEFT(@digits,LEN(@digits)-1); SET @e=@e+1; END;
  IF @digits=N'0' SET @e=0;
  IF @e<0 RETURN NULL;
 END
 ELSE IF @e < -4 RETURN NULL;
 IF @digits=N'0' RETURN CONVERT(decimal(19,4),0);
 IF @e>=0
 BEGIN
  IF @e>19 OR LEN(@digits)+@e>19 RETURN NULL;
  SET @canonical=@digits+REPLICATE(N'0',@e);
 END
 ELSE
 BEGIN
  IF LEN(@digits)<=-@e SET @canonical=N'0.'+REPLICATE(N'0',-@e-LEN(@digits))+@digits;
  ELSE SET @canonical=LEFT(@digits,LEN(@digits)+@e)+N'.'+RIGHT(@digits,-@e);
 END;
 IF @negative=1 SET @canonical=N'-'+@canonical;
 SET @n=TRY_CONVERT(decimal(19,4),@canonical);
 IF @n IS NULL OR ABS(@n)>CONVERT(decimal(19,4),922337203685477.5807) RETURN NULL;
 RETURN @n;
END;
GO
CREATE OR ALTER PROCEDURE stg.usp_ValidateCoffeeLanding @BatchID uniqueidentifier AS
BEGIN
 SET NOCOUNT ON; SET XACT_ABORT ON;
 IF NOT EXISTS(SELECT 1 FROM audit.LoadBatch WHERE BatchID=@BatchID AND Status='STAGED')
  THROW 50202,'Unregistered or non-staged batch',1;
 IF EXISTS(SELECT 1 FROM stg.CoffeeRaw WHERE BatchID=@BatchID)
  THROW 50203,'Normalized staging already exists for this batch',1;
 IF (SELECT COUNT_BIG(*) FROM stg.CoffeeCsvLanding WHERE BatchID=CONVERT(nvarchar(36),@BatchID))
   <>(SELECT SourceCount FROM audit.LoadBatch WHERE BatchID=@BatchID)
  THROW 50204,'Flat File source count and landed count disagree',1;
 SELECT CONVERT(int,ROW_NUMBER() OVER(ORDER BY LandingID)+1) SourceRow,
  (SELECT ISNULL(l.[Area Code],N'') [Area Code],ISNULL(l.[Date],N'') [Date],
   ISNULL(l.Market,N'') Market,ISNULL(l.[Market Size],N'') [Market Size],
   ISNULL(l.Product,N'') Product,ISNULL(l.[Product Line],N'') [Product Line],
   ISNULL(l.[Product Type],N'') [Product Type],ISNULL(l.State,N'') State,ISNULL(l.Type,N'') Type,
   ISNULL(l.[Budget COGS],N'') [Budget COGS],ISNULL(l.[Budget Margin],N'') [Budget Margin],
   ISNULL(l.[Budget Profit],N'') [Budget Profit],ISNULL(l.[Budget Sales],N'') [Budget Sales],
   ISNULL(l.COGS,N'') COGS,ISNULL(l.Inventory,N'') Inventory,ISNULL(l.Margin,N'') Margin,
   ISNULL(l.Marketing,N'') Marketing,ISNULL(l.Profit,N'') Profit,ISNULL(l.Sales,N'') Sales,
   ISNULL(l.[Total Expenses],N'') [Total Expenses] FOR JSON PATH,WITHOUT_ARRAY_WRAPPER) RawJson,
  stg.fn_CoffeeTrim(l.[Area Code]) AreaCode,stg.fn_CoffeeTrim(l.[State]) State,
  stg.fn_CoffeeTrim(l.Market) Market,stg.fn_CoffeeTrim(l.[Market Size]) MarketSize,
  stg.fn_CoffeeTrim(l.Product) ProductName,stg.fn_CoffeeTrim(l.[Product Line]) ProductLine,
  stg.fn_CoffeeTrim(l.[Product Type]) ProductType,stg.fn_CoffeeTrim(l.[Type]) Type,
  stg.fn_CoffeeNumber(l.[Date],'D') DateSerial,
  stg.fn_CoffeeNumber(l.[Sales],'M') Sales,stg.fn_CoffeeNumber(l.[Budget Sales],'M') BudgetSales,
  stg.fn_CoffeeNumber(l.[Profit],'M') Profit,stg.fn_CoffeeNumber(l.[Budget Profit],'M') BudgetProfit,
  stg.fn_CoffeeNumber(l.[COGS],'M') COGS,stg.fn_CoffeeNumber(l.[Budget COGS],'M') BudgetCOGS,
  stg.fn_CoffeeNumber(l.[Margin],'M') Margin,stg.fn_CoffeeNumber(l.[Budget Margin],'M') BudgetMargin,
  stg.fn_CoffeeNumber(l.[Marketing],'M') Marketing,stg.fn_CoffeeNumber(l.[Inventory],'M') Inventory,
  stg.fn_CoffeeNumber(l.[Total Expenses],'M') TotalExpenses
 INTO #p FROM stg.CoffeeCsvLanding l WHERE BatchID=CONVERT(nvarchar(36),@BatchID);
 -- Match pandas.Timestamp/coffee_dw.source's representable day bounds before
 -- requiring month-start. SQL Server date supports a much wider range.
 SELECT *,DATEADD(day,CONVERT(int,CASE WHEN DateSerial BETWEEN -81182 AND 132320 THEN DateSerial END),
    CONVERT(date,'18991230')) MonthStart INTO #d FROM #p;
 SELECT *,CASE WHEN DAY(MonthStart)=1 THEN CONVERT(int,CONVERT(char(8),MonthStart,112)) END DateKey,
  CONVERT(nvarchar(max),NULLIF(STUFF(CONCAT(
   CASE WHEN AreaCode=N'' THEN N'; AreaCode: required' ELSE N'' END,
   CASE WHEN State=N'' THEN N'; State: required' ELSE N'' END,
   CASE WHEN Market=N'' THEN N'; Market: required' ELSE N'' END,
   CASE WHEN MarketSize=N'' THEN N'; MarketSize: required' ELSE N'' END,
   CASE WHEN ProductName=N'' THEN N'; ProductName: required' ELSE N'' END,
   CASE WHEN ProductLine=N'' THEN N'; ProductLine: required' ELSE N'' END,
   CASE WHEN ProductType=N'' THEN N'; ProductType: required' ELSE N'' END,
   CASE WHEN Type=N'' THEN N'; Type: required' ELSE N'' END,
   CASE WHEN MonthStart IS NULL OR DAY(MonthStart)<>1 THEN N'; Date: invalid Excel month-start serial' ELSE N'' END,
   CASE WHEN Sales IS NULL THEN N'; Sales: invalid numeric value' ELSE N'' END,
   CASE WHEN BudgetSales IS NULL THEN N'; BudgetSales: invalid numeric value' ELSE N'' END,
   CASE WHEN Profit IS NULL THEN N'; Profit: invalid numeric value' ELSE N'' END,
   CASE WHEN BudgetProfit IS NULL THEN N'; BudgetProfit: invalid numeric value' ELSE N'' END,
   CASE WHEN COGS IS NULL THEN N'; COGS: invalid numeric value' ELSE N'' END,
   CASE WHEN BudgetCOGS IS NULL THEN N'; BudgetCOGS: invalid numeric value' ELSE N'' END,
   CASE WHEN Margin IS NULL THEN N'; Margin: invalid numeric value' ELSE N'' END,
   CASE WHEN BudgetMargin IS NULL THEN N'; BudgetMargin: invalid numeric value' ELSE N'' END,
   CASE WHEN Marketing IS NULL THEN N'; Marketing: invalid numeric value' ELSE N'' END,
   CASE WHEN Inventory IS NULL THEN N'; Inventory: invalid numeric value' ELSE N'' END,
   CASE WHEN TotalExpenses IS NULL THEN N'; TotalExpenses: invalid numeric value' ELSE N'' END
  ),1,2,N''),N'')) RejectReason INTO #s FROM #d;
 SELECT DateKey,AreaCode,ProductName INTO #dup FROM #s WHERE RejectReason IS NULL
  GROUP BY DateKey,AreaCode,ProductName HAVING COUNT(*)>1;
 SELECT AreaCode INTO #badArea FROM #s WHERE RejectReason IS NULL GROUP BY AreaCode
  HAVING COUNT(DISTINCT State)>1 OR COUNT(DISTINCT Market)>1 OR COUNT(DISTINCT MarketSize)>1;
 SELECT ProductName INTO #badProduct FROM #s WHERE RejectReason IS NULL GROUP BY ProductName
  HAVING COUNT(DISTINCT ProductLine)>1 OR COUNT(DISTINCT ProductType)>1 OR COUNT(DISTINCT Type)>1;
 UPDATE s SET RejectReason=NULLIF(STUFF(CONCAT(
   CASE WHEN EXISTS(SELECT 1 FROM #dup d WHERE d.DateKey=s.DateKey AND d.AreaCode=s.AreaCode AND d.ProductName=s.ProductName)
    THEN N'; duplicate candidate grain' ELSE N'' END,
   CASE WHEN EXISTS(SELECT 1 FROM #badArea a WHERE a.AreaCode=s.AreaCode)
    THEN N'; conflicting attributes for AreaCode' ELSE N'' END,
   CASE WHEN EXISTS(SELECT 1 FROM #badProduct p WHERE p.ProductName=s.ProductName)
    THEN N'; conflicting attributes for ProductName' ELSE N'' END),1,2,N''),N'')
 FROM #s s WHERE RejectReason IS NULL;
 INSERT stg.CoffeeRaw(BatchID,SourceRow,RawJson,RejectReason,MonthStart,DateKey,
  AreaCode,State,Market,MarketSize,ProductName,ProductLine,ProductType,Type,
  Sales,BudgetSales,Profit,BudgetProfit,COGS,BudgetCOGS,Margin,BudgetMargin,Marketing,Inventory,TotalExpenses)
 SELECT @BatchID,SourceRow,RawJson,RejectReason,
  CASE WHEN RejectReason IS NULL THEN MonthStart END,CASE WHEN RejectReason IS NULL THEN DateKey END,
  CASE WHEN RejectReason IS NULL THEN AreaCode END,CASE WHEN RejectReason IS NULL THEN State END,
  CASE WHEN RejectReason IS NULL THEN Market END,CASE WHEN RejectReason IS NULL THEN MarketSize END,
  CASE WHEN RejectReason IS NULL THEN ProductName END,CASE WHEN RejectReason IS NULL THEN ProductLine END,
  CASE WHEN RejectReason IS NULL THEN ProductType END,CASE WHEN RejectReason IS NULL THEN Type END,
  CASE WHEN RejectReason IS NULL THEN Sales END,CASE WHEN RejectReason IS NULL THEN BudgetSales END,
  CASE WHEN RejectReason IS NULL THEN Profit END,CASE WHEN RejectReason IS NULL THEN BudgetProfit END,
  CASE WHEN RejectReason IS NULL THEN COGS END,CASE WHEN RejectReason IS NULL THEN BudgetCOGS END,
  CASE WHEN RejectReason IS NULL THEN Margin END,CASE WHEN RejectReason IS NULL THEN BudgetMargin END,
  CASE WHEN RejectReason IS NULL THEN Marketing END,CASE WHEN RejectReason IS NULL THEN Inventory END,
  CASE WHEN RejectReason IS NULL THEN TotalExpenses END FROM #s;
END;
GO
