-- Adapted from Chi's SCD_TN04 SQL simulation, kept separate from Chi's worktree.
-- Executed by native SSIS Execute SQL Task; no Data Flow/serving dimensions changed.
IF DB_NAME() NOT LIKE N'CoffeeDW[_]Trang[_]%' THROW 50201,'Use isolated CoffeeDW_Trang DB',1;
DECLARE @RunID uniqueidentifier=CONVERT(uniqueidentifier,?);
IF OBJECT_ID('audit.SCDNativeEvidence') IS NULL
 CREATE TABLE audit.SCDNativeEvidence(RunID uniqueidentifier NOT NULL PRIMARY KEY,
 CreatedAtUTC datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),ResultJson nvarchar(max) NOT NULL);


-- TN04: Synthetic SCD Type 1 / Type 2 / Type 3 experiment on SQL Server.
-- Isolated in #temp tables so serving dimensions (dw.DimProduct, dw.DimLocation)
-- and source data remain untouched.
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;

-------------------------------------------------------------------------------
-- PART 1: Product P01 (Report Section 4.3 & learning/experiments/scd.py)
-------------------------------------------------------------------------------
CREATE TABLE #Type1 (
    ProductKey int IDENTITY(1,1) PRIMARY KEY,
    Code varchar(10) NOT NULL UNIQUE,
    ProductName nvarchar(100) NOT NULL
);
INSERT INTO #Type1 (Code, ProductName) VALUES ('P01', N'Amareto');
-- Type 1: overwrite typo in place; surrogate key remains 1, row count remains 1.
UPDATE #Type1 SET ProductName = N'Amaretto' WHERE Code = 'P01';

CREATE TABLE #Type2 (
    ProductKey int IDENTITY(1,1) PRIMARY KEY,
    Code varchar(10) NOT NULL,
    ProductName nvarchar(100) NOT NULL,
    ProductType nvarchar(40) NOT NULL,
    ValidFrom date NOT NULL,
    ValidTo date NOT NULL,
    IsCurrent bit NOT NULL,
    CONSTRAINT CK_Type2_ValidRange CHECK (ValidFrom < ValidTo)
);
CREATE UNIQUE INDEX UX_Type2_OneCurrent ON #Type2(Code) WHERE IsCurrent = 1;

INSERT INTO #Type2 (Code, ProductName, ProductType, ValidFrom, ValidTo, IsCurrent)
VALUES ('P01', N'Amaretto', N'Coffee', '2012-01-01', '9999-12-31', 1);

-- Stored procedure logic in a transaction: close old version and open new version
-- at effective boundary T = 2013-01-01; replay of identical event is a no-op.
DECLARE @change_round int = 1;
WHILE @change_round <= 2 -- Round 1 applies change; Round 2 tests idempotent replay
BEGIN
    BEGIN TRANSACTION;
    DECLARE @curKey int, @curType nvarchar(40), @curStart date;
    SELECT @curKey = ProductKey, @curType = ProductType, @curStart = ValidFrom
    FROM #Type2 WITH (UPDLOCK, HOLDLOCK)
    WHERE Code = 'P01' AND IsCurrent = 1;

    IF @curType <> N'Specialty'
    BEGIN
        IF '2013-01-01' <= @curStart
            THROW 50010, 'Effective date must be strictly after current ValidFrom', 1;
        UPDATE #Type2
        SET ValidTo = '2013-01-01', IsCurrent = 0
        WHERE ProductKey = @curKey;

        INSERT INTO #Type2 (Code, ProductName, ProductType, ValidFrom, ValidTo, IsCurrent)
        VALUES ('P01', N'Amaretto', N'Specialty', '2013-01-01', '9999-12-31', 1);
    END
    COMMIT TRANSACTION;
    SET @change_round += 1;
END;

-- Type 3: retains only current and immediately previous attribute value
CREATE TABLE #Type3 (
    Code varchar(10) NOT NULL PRIMARY KEY,
    ProductName nvarchar(100) NOT NULL,
    CurrentType nvarchar(40) NOT NULL,
    PreviousType nvarchar(40) NULL
);
INSERT INTO #Type3 VALUES ('P01', N'Amaretto', N'Coffee', NULL);
UPDATE #Type3 SET PreviousType = CurrentType, CurrentType = N'Specialty' WHERE Code = 'P01';
UPDATE #Type3 SET PreviousType = CurrentType, CurrentType = N'Premium' WHERE Code = 'P01';

-- Verification outputs for Part 1
SELECT 'P01_Type1' AS TestSection, ProductKey, Code, ProductName FROM #Type1;
SELECT 'P01_Type2_Versions' AS TestSection, ProductKey, Code, ProductName, ProductType, ValidFrom, ValidTo, IsCurrent
FROM #Type2 ORDER BY ProductKey;

SELECT 'P01_Type2_Lookup' AS TestSection, q.OrderMonth, t.ProductKey, t.ProductType
FROM (VALUES (CAST('2012-12-01' AS date)), ('2013-01-01'), ('2013-02-01')) q(OrderMonth)
JOIN #Type2 t ON t.Code = 'P01' AND t.ValidFrom <= q.OrderMonth AND q.OrderMonth < t.ValidTo
ORDER BY q.OrderMonth;

SELECT 'P01_Type2_Invariants' AS TestSection,
    COUNT(*) AS TotalVersionsAfterReplay,
    SUM(CAST(IsCurrent AS int)) AS CurrentVersionCount,
    (SELECT COUNT(*) FROM #Type2 a JOIN #Type2 b
     ON a.Code = b.Code AND a.ProductKey < b.ProductKey
     AND a.ValidFrom < b.ValidTo AND b.ValidFrom < a.ValidTo) AS OverlappingIntervals
FROM #Type2 WHERE Code = 'P01';

SELECT 'P01_Type3_Limit' AS TestSection, Code, ProductName, CurrentType, PreviousType FROM #Type3;

-------------------------------------------------------------------------------
-- PART 2: Location A01 (Handbook TN04 worksheet: Minor -> Major -> Pilot)
-------------------------------------------------------------------------------
CREATE TABLE #L (
    SK int IDENTITY(1,1) PRIMARY KEY,
    BK varchar(8) NOT NULL,
    Label nvarchar(40) NOT NULL,
    Tier varchar(10) NOT NULL,
    PrevTier varchar(10) NULL,
    ValidFrom date NOT NULL,
    ValidTo date NOT NULL
);
INSERT INTO #L VALUES ('A01', N'Wset', 'Minor', NULL, '20120101', '99991231');
-- Type 1: fix label typo
UPDATE #L SET Label = N'West' WHERE BK = 'A01';
-- Type 2: close old version and insert new version in same transaction
BEGIN TRANSACTION;
UPDATE #L SET ValidTo = '20120701' WHERE BK = 'A01' AND ValidTo = '99991231';
INSERT INTO #L VALUES ('A01', N'West', 'Major', NULL, '20120701', '99991231');
COMMIT TRANSACTION;

SELECT 'A01_Type2_Versions' AS TestSection, SK, BK, Label, Tier, ValidFrom, ValidTo FROM #L ORDER BY SK;
SELECT 'A01_Type2_Lookup' AS TestSection, t.MonthStart, l.SK, l.Tier
FROM (VALUES (CAST('20120601' AS date)), ('20120701')) t(MonthStart)
JOIN #L l ON l.BK = 'A01' AND t.MonthStart >= l.ValidFrom AND t.MonthStart < l.ValidTo
ORDER BY t.MonthStart;

SELECT TOP (1) BK, Tier, PrevTier INTO #T3 FROM #L ORDER BY SK;
UPDATE #T3 SET PrevTier = Tier, Tier = 'Major';
UPDATE #T3 SET PrevTier = Tier, Tier = 'Pilot';
SELECT 'A01_Type3_After2Changes' AS TestSection, BK, Tier, PrevTier FROM #T3;


-- Assertions fail the native package if a required SCD invariant is wrong.
IF (SELECT COUNT(*) FROM #Type1 WHERE ProductKey=1 AND ProductName=N'Amaretto')<>1
 THROW 50210,'Type1 overwrite/key assertion failed',1;
IF (SELECT COUNT(*) FROM #Type2)<>2 OR (SELECT COUNT(*) FROM #Type2 WHERE IsCurrent=1)<>1
 THROW 50211,'Type2 replay/current assertion failed',1;
IF EXISTS(SELECT 1 FROM #Type2 a JOIN #Type2 b ON a.Code=b.Code AND a.ProductKey<b.ProductKey
 AND a.ValidFrom<b.ValidTo AND b.ValidFrom<a.ValidTo)
 THROW 50212,'Type2 overlapping intervals',1;
IF (SELECT ProductKey FROM #Type2 WHERE '20121201'>=ValidFrom AND '20121201'<ValidTo)<>1
 OR (SELECT ProductKey FROM #Type2 WHERE '20130101'>=ValidFrom AND '20130101'<ValidTo)<>2
 THROW 50213,'Type2 date boundary assertion failed',1;
IF NOT EXISTS(SELECT 1 FROM #Type3 WHERE CurrentType=N'Premium' AND PreviousType=N'Specialty')
 THROW 50214,'Type3 one-step-history assertion failed',1;
DECLARE @Result nvarchar(max)=(SELECT
 JSON_QUERY((SELECT * FROM #Type1 FOR JSON PATH)) ProductType1,
 JSON_QUERY((SELECT * FROM #Type2 ORDER BY ProductKey FOR JSON PATH)) ProductType2,
 JSON_QUERY((SELECT * FROM #Type3 FOR JSON PATH)) ProductType3,
 JSON_QUERY((SELECT * FROM #L ORDER BY SK FOR JSON PATH)) LocationType2,
 JSON_QUERY((SELECT * FROM #T3 FOR JSON PATH)) LocationType3,
 'PASS' Assertions,'Synthetic P01/A01; not evidence of a real source dimension change' Scope
 FOR JSON PATH,WITHOUT_ARRAY_WRAPPER);
INSERT audit.SCDNativeEvidence(RunID,ResultJson) VALUES(@RunID,@Result);

DROP TABLE #T3;
DROP TABLE #L;
DROP TABLE #Type3;
DROP TABLE #Type2;
DROP TABLE #Type1;
