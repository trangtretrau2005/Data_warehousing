USE CoffeeDW;
GO
-- TN05 teaching split. Actual and budget originate from the SAME CSV snapshot;
-- temporary copies simulate independent upstream facts and missing groups.
-- All changes below affect #temp tables only, never source or serving fact.
SELECT MonthStart,Market,SUM(Sales) Sales INTO #Actual
FROM mart.vw_Detail GROUP BY MonthStart,Market;
SELECT MonthStart,Market,SUM(BudgetSales) BudgetSales INTO #Budget
FROM mart.vw_Detail GROUP BY MonthStart,Market;
CREATE UNIQUE CLUSTERED INDEX CX_Actual ON #Actual(MonthStart,Market);
CREATE UNIQUE CLUSTERED INDEX CX_Budget ON #Budget(MonthStart,Market);
-- Correct: aggregate independently, then join 1:1 at month-Market.
SELECT COALESCE(a.MonthStart,b.MonthStart) MonthStart,COALESCE(a.Market,b.Market) Market,
 a.Sales,b.BudgetSales,a.Sales-b.BudgetSales Gap,
 CASE WHEN a.MonthStart IS NULL THEN 1 ELSE 0 END MissingActual,
 CASE WHEN b.MonthStart IS NULL THEN 1 ELSE 0 END MissingBudget
FROM #Actual a FULL OUTER JOIN #Budget b ON a.MonthStart=b.MonthStart AND a.Market=b.Market;
-- 96 groups and source totals before introducing synthetic missing groups.
SELECT COUNT(*) Groups,SUM(a.Sales) Sales,SUM(b.BudgetSales) BudgetSales
FROM #Actual a JOIN #Budget b ON a.MonthStart=b.MonthStart AND a.Market=b.Market;
-- Intentionally wrong: repeated aggregate budget is joined to detail rows.
SELECT SUM(d.Sales) Sales,SUM(b.BudgetSales) IncorrectRepeatedBudget
FROM mart.vw_Detail d JOIN #Budget b ON d.MonthStart=b.MonthStart AND d.Market=b.Market;
-- Synthetic missing-budget and future-plan-only cases in isolated temp copies.
DELETE FROM #Budget WHERE MonthStart='20120101' AND Market=N'West';
INSERT #Budget VALUES('20140101',N'West',1000);
SELECT COALESCE(a.MonthStart,b.MonthStart) MonthStart,COALESCE(a.Market,b.Market) Market,
 a.Sales,b.BudgetSales,a.Sales-b.BudgetSales Gap,
 CASE WHEN a.MonthStart IS NULL THEN 1 ELSE 0 END MissingActual,
 CASE WHEN b.MonthStart IS NULL THEN 1 ELSE 0 END MissingBudget
FROM #Actual a FULL OUTER JOIN #Budget b ON a.MonthStart=b.MonthStart AND a.Market=b.Market
WHERE a.MonthStart IS NULL OR b.MonthStart IS NULL;
-- Missing means unknown. Do not silently replace these NULL measures with zero.
DROP TABLE #Actual;
DROP TABLE #Budget;
GO
