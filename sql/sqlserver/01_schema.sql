USE CoffeeDW;
GO
IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg AUTHORIZATION dbo');
IF SCHEMA_ID('dw') IS NULL EXEC('CREATE SCHEMA dw AUTHORIZATION dbo');
IF SCHEMA_ID('mart') IS NULL EXEC('CREATE SCHEMA mart AUTHORIZATION dbo');
IF SCHEMA_ID('audit') IS NULL EXEC('CREATE SCHEMA audit AUTHORIZATION dbo');
IF SCHEMA_ID('bench') IS NULL EXEC('CREATE SCHEMA bench AUTHORIZATION dbo');
IF SCHEMA_ID('ml') IS NULL EXEC('CREATE SCHEMA ml AUTHORIZATION dbo');
GO
IF OBJECT_ID('audit.LoadBatch') IS NULL
CREATE TABLE audit.LoadBatch (
 BatchID uniqueidentifier NOT NULL PRIMARY KEY,
 SourceFile nvarchar(500) NOT NULL, SourceChecksum char(64) NOT NULL,
 StartedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(), FinishedAt datetime2 NULL,
 Status varchar(20) NOT NULL DEFAULT 'STAGED', SourceCount int NOT NULL,
 AcceptedCount int NULL, RejectedCount int NULL, InsertedCount int NULL,
 UpdatedCount int NULL, UnchangedCount int NULL
);
IF OBJECT_ID('stg.CoffeeRaw') IS NULL
CREATE TABLE stg.CoffeeRaw (
 BatchID uniqueidentifier NOT NULL REFERENCES audit.LoadBatch(BatchID),
 SourceRow int NOT NULL, RawJson nvarchar(max) NOT NULL, RejectReason nvarchar(max) NULL,
 MonthStart date NULL, DateKey int NULL, AreaCode nvarchar(20) NULL,
 State nvarchar(100) NULL, Market nvarchar(40) NULL, MarketSize nvarchar(40) NULL,
 ProductName nvarchar(100) NULL, ProductLine nvarchar(40) NULL,
 ProductType nvarchar(40) NULL, [Type] nvarchar(40) NULL,
 Sales decimal(19,4) NULL, BudgetSales decimal(19,4) NULL,
 Profit decimal(19,4) NULL, BudgetProfit decimal(19,4) NULL,
 COGS decimal(19,4) NULL, BudgetCOGS decimal(19,4) NULL,
 Margin decimal(19,4) NULL, BudgetMargin decimal(19,4) NULL,
 Marketing decimal(19,4) NULL, Inventory decimal(19,4) NULL,
 TotalExpenses decimal(19,4) NULL,
 PRIMARY KEY(BatchID,SourceRow)
);
IF OBJECT_ID('audit.RejectedRow') IS NULL
CREATE TABLE audit.RejectedRow (
 BatchID uniqueidentifier NOT NULL REFERENCES audit.LoadBatch(BatchID),
 SourceRow int NOT NULL, Reason nvarchar(max) NOT NULL, RawJson nvarchar(max) NOT NULL,
 PRIMARY KEY(BatchID,SourceRow)
);
IF OBJECT_ID('dw.DimDate') IS NULL
CREATE TABLE dw.DimDate (
 DateKey int NOT NULL PRIMARY KEY, MonthStart date NOT NULL UNIQUE,
 [Year] smallint NOT NULL, [Quarter] tinyint NOT NULL, [Month] tinyint NOT NULL
);
IF OBJECT_ID('dw.DimLocation') IS NULL
CREATE TABLE dw.DimLocation (
 LocationKey int IDENTITY PRIMARY KEY, AreaCode nvarchar(20) NOT NULL UNIQUE,
 State nvarchar(100) NOT NULL, Market nvarchar(40) NOT NULL, MarketSize nvarchar(40) NOT NULL
);
IF OBJECT_ID('dw.DimProduct') IS NULL
CREATE TABLE dw.DimProduct (
 ProductKey int IDENTITY PRIMARY KEY, ProductName nvarchar(100) NOT NULL UNIQUE,
 ProductLine nvarchar(40) NOT NULL, ProductType nvarchar(40) NOT NULL, [Type] nvarchar(40) NOT NULL
);
IF OBJECT_ID('dw.FactSalesPerformance') IS NULL
CREATE TABLE dw.FactSalesPerformance (
 DateKey int NOT NULL REFERENCES dw.DimDate(DateKey),
 LocationKey int NOT NULL REFERENCES dw.DimLocation(LocationKey),
 ProductKey int NOT NULL REFERENCES dw.DimProduct(ProductKey),
 Sales decimal(19,4) NOT NULL, BudgetSales decimal(19,4) NOT NULL,
 Profit decimal(19,4) NOT NULL, BudgetProfit decimal(19,4) NOT NULL,
 COGS decimal(19,4) NOT NULL, BudgetCOGS decimal(19,4) NOT NULL,
 Margin decimal(19,4) NOT NULL, BudgetMargin decimal(19,4) NOT NULL,
 Marketing decimal(19,4) NOT NULL, Inventory decimal(19,4) NOT NULL,
 TotalExpenses decimal(19,4) NOT NULL,
 BatchID uniqueidentifier NOT NULL REFERENCES audit.LoadBatch(BatchID), SourceRow int NOT NULL,
 CONSTRAINT PK_FactSalesPerformance PRIMARY KEY(DateKey,LocationKey,ProductKey)
);
IF OBJECT_ID('ml.ForecastSales') IS NULL
CREATE TABLE ml.ForecastSales (
 Market nvarchar(40) NOT NULL, ForecastMonth date NOT NULL, IssueMonth date NOT NULL,
 TrainEnd date NOT NULL, ModelName nvarchar(60) NOT NULL, ModelVersion nvarchar(80) NOT NULL,
 Prediction decimal(19,4) NOT NULL, Actual decimal(19,4) NULL, Split varchar(20) NOT NULL,
 PRIMARY KEY(Market,ForecastMonth,IssueMonth,ModelName,ModelVersion)
);
GO
