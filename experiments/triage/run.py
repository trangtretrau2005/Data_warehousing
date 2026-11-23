"""Run from the repository root. Evaluate three reviews per month."""
from pathlib import Path
import json
import hashlib
import sklearn
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

root = Path(__file__).resolve().parents[2]
out = root / "results/triage_pilot"
out.mkdir(parents=True, exist_ok=True)
with sqlite3.connect("file:data/warehouse/coffee_dw.sqlite?mode=ro", uri=True) as db:
    df = pd.read_sql_query("""SELECT MonthStart,Market,ProductName,SUM(Sales) sales,
        SUM(BudgetSales) budget,SUM(Profit) profit FROM vw_Detail
        GROUP BY MonthStart, Market, ProductName ORDER BY MonthStart,Market,ProductName""", db)
source = root / "data/raw/Coffee.csv"
raw = pd.read_csv(source, dtype={"Area Code": str})
raw["MonthStart"] = pd.to_datetime(raw["Date"], unit="D", origin="1899-12-30").dt.strftime("%Y-%m-%d")
actual = raw.groupby(["MonthStart","Market","Product"])[["Sales","Budget Sales","Profit"]].sum()
actual.index.names = ["MonthStart","Market","ProductName"]
actual.columns = ["sales","budget","profit"]
pd.testing.assert_frame_equal(df.set_index(actual.index.names).sort_index(), actual.sort_index(), check_dtype=False)
keys = ["Market","ProductName"]
assert df.groupby(keys).size().eq(24).all() and df.MonthStart.nunique() == 24
df["loss"] = (df.budget - df.sales).clip(lower=0)
df["gap_rate"] = (df.budget-df.sales)/df.budget.replace(0,np.nan)
group = df.groupby(keys)
def previous_three(column):
    return group[column].transform(lambda s:s.shift().rolling(3).sum())
previous_sales = previous_three("sales").replace(0,np.nan)
df["sales_change"] = 3*df.sales/previous_sales-1
df["margin_change"] = df.profit/df.sales.replace(0,np.nan)-previous_three("profit")/previous_sales
df["next_loss"] = group.loss.shift(-1)
features = ["gap_rate","sales_change","margin_change"]
alerts = []
eligible = []
months = []
for month in sorted(df.MonthStart.unique())[12:-1]:
    train = df[df.MonthStart < month].dropna(subset=features)
    candidates = df[(df.MonthStart==month)&(df.loss>0)].dropna(subset=features).copy()
    model = IsolationForest(random_state=42).fit(train[features])
    candidates["AI"] = -model.score_samples(candidates[features])
    eligible.append(candidates)
    months.append(dict(month=month, train=len(train), candidates=len(candidates),
                       persistent=int(candidates.next_loss.gt(0).sum()), pool_loss=float(candidates.next_loss.sum())))
    for method in ["AI","loss"]:
        top = candidates.sort_values([method,*keys],ascending=[False,True,True]).head(3).copy()
        assert len(top)==3 and top.next_loss.notna().all()
        top["method"]=method
        alerts.append(top)
ranked = pd.concat(alerts)
ranked.to_csv(out/"alerts.csv",index=False)
print(ranked.groupby("method").next_loss.agg(["count",lambda x:(x>0).sum(),"sum"]))
pool=pd.concat(eligible)
print("eligible",len(pool),"persistent",(pool.next_loss>0).sum(),"next_loss",pool.next_loss.sum())
print(ranked[ranked.MonthStart.str.startswith("2013-08")][["method",*keys,"loss","next_loss"]].to_string(index=False))

pool.to_csv(out/"candidates.csv",index=False)
artifact = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), sklearn=sklearn.__version__,
                source_rows=len(raw), months=months, alerts=json.loads(ranked.to_json(orient="records")))
(root/"apps/cube_explorer/triage.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding="utf-8")
