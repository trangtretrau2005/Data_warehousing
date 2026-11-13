USE CoffeeDW;
GO
-- TN05: demonstrate independent preaggregation and retain missing groups.
-- Actual/budget in Coffee.csv are measures on the same fact, so comparing them
-- is not itself drill-across. ForecastSales is the independent second fact.
DECLARE @model nvarchar(60)=N'moving_average_3',@version nvarchar(80)=N'v1-lag123-alpha1';
WITH Actual AS (
 SELECT MonthStart,Market,SUM(Sales) Actual FROM mart.vw_Detail GROUP BY MonthStart,Market
), ChosenForecast AS (
 SELECT ForecastMonth,Market,Prediction,IssueMonth FROM ml.ForecastSales
 WHERE ModelName=@model AND ModelVersion=@version
 AND IssueMonth=DATEADD(month,-1,ForecastMonth)
)
SELECT COALESCE(a.MonthStart,p.ForecastMonth) MonthStart,COALESCE(a.Market,p.Market) Market,
 a.Actual,p.Prediction,p.IssueMonth,a.Actual-p.Prediction Error
FROM Actual a FULL OUTER JOIN ChosenForecast p ON a.MonthStart=p.ForecastMonth AND a.Market=p.Market;
-- The SQL Server forecast table must be populated explicitly when integrating
-- the Python serving layer. SQLite output is not automatically copied here.
GO
