import yfinance as yf, pandas as pd
t = yf.Ticker("QQQ")
df = t.history(period="max", auto_adjust=False)
print("rows:", len(df))
print("first:", df.index[0].date(), " last:", df.index[-1].date())
print(df[["Open","High","Low","Close","Adj Close"]].head(3))
print("--- around Mar 2000 split ---")
print(df.loc["2000-03-16":"2000-03-24", ["Close","Adj Close"]])
print("--- max 1-day raw close ratio (split check) ---")
r = (df["Close"]/df["Close"].shift(1)).dropna()
print("min ratio", round(r.min(),4), "on", r.idxmin().date())
print("max ratio", round(r.max(),4), "on", r.idxmax().date())
print("--- dividends ---")
d = t.dividends
print("count:", len(d), "first:", d.index[0].date() if len(d) else None, "last:", d.index[-1].date() if len(d) else None)
print("--- OHLC sanity violations ---")
bad = df[(df.Low > df[["Open","Close"]].min(axis=1)+1e-9) | (df.High < df[["Open","Close"]].max(axis=1)-1e-9)]
print("violations:", len(bad))
print("nulls:", int(df[["Open","High","Low","Close"]].isna().any(axis=1).sum()))
