"""
QQQ 20/10 Donchian Breakout - long/flat, 10% position sizing.
Implements Strategy_Spec.md v3. No backtesting library: the loop is explicit.

Run:  .venv/Scripts/python.exe backtest.py
Out:  qqq_raw.csv (data snapshot), results.json (everything the report needs)
"""

import json
import math
from datetime import datetime

import pandas as pd
import yfinance as yf

# ----------------------------------------------------------------------------
# Parameters (Strategy_Spec.md v3)
# ----------------------------------------------------------------------------
SYMBOL          = "QQQ"
ENTRY_LOOKBACK  = 20       # bars for the upper (entry) Donchian channel
EXIT_LOOKBACK   = 10       # bars for the lower (exit) Donchian channel
POSITION_PCT    = 0.10     # 10% of current equity per trade   (spec S6.1)
START_EQUITY    = 100_000.0
CASH_YIELD      = 0.0      # 0% on idle cash                   (spec A14)

VARIANTS = {
    "A": {"label": "Frictionless",      "commission": 0.0,    "tick": 0.00},
    "B": {"label": "Friction-adjusted", "commission": 0.0005, "tick": 0.01},
}


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_data():
    """
    auto_adjust=False gives raw OHLC that Yahoo has already SPLIT-adjusted but
    NOT dividend-adjusted -- exactly the internally consistent series spec A1
    requires. 'Adj Close' is dividend-adjusted too and is deliberately unused
    for signals: mixing it with raw highs/lows compares two different scales.
    """
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period="max", auto_adjust=False)
    df = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()

    # Spec A4: report data problems, never silently repair them.
    n_start = len(df)
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    bad_hl = df[(df["Low"] > df[["Open", "Close"]].min(axis=1) + 1e-9) |
                (df["High"] < df[["Open", "Close"]].max(axis=1) - 1e-9)]

    # Spec A1 verification: a split left unadjusted in the raw close would show
    # up as a ~2x single-bar jump. Record the extremes so the report can prove it.
    ratio = (df["Close"] / df["Close"].shift(1)).dropna()

    quality = {
        "rows_downloaded": int(n_start),
        "rows_used": int(len(df)),
        "rows_dropped_null": int(n_start - len(df)),
        "ohlc_violations": int(len(bad_hl)),
        "max_1day_ratio": round(float(ratio.max()), 4),
        "max_1day_ratio_date": str(ratio.idxmax().date()),
        "min_1day_ratio": round(float(ratio.min()), 4),
        "min_1day_ratio_date": str(ratio.idxmin().date()),
    }

    dividends = ticker.dividends
    dividends.index = pd.to_datetime(dividends.index).tz_localize(None).normalize()
    div_map = {d: float(v) for d, v in dividends.items() if v > 0}

    df.to_csv("qqq_raw.csv")  # spec A3: snapshot so the run is reproducible
    return df, div_map, quality


# ----------------------------------------------------------------------------
# The backtest loop
# ----------------------------------------------------------------------------
def run_backtest(df, div_map, commission_rate, tick):
    """
    One pass over the bars. State machine per spec S4.3:
        FLAT  -> evaluate ENTRY only
        LONG  -> evaluate EXIT only
    Exactly one rule per bar, so entry and exit can never both fire.
    """
    dates  = df.index
    high   = df["High"].values
    low    = df["Low"].values
    close  = df["Close"].values
    n      = len(df)

    cash        = START_EQUITY
    shares      = 0.0
    state       = "FLAT"
    entry       = None            # details of the open trade
    trades      = []
    equity_curve = []
    total_commission = 0.0
    total_slippage   = 0.0
    first_bar   = None            # first bar on which a signal could be evaluated

    for t in range(n):
        today = dates[t]

        # --- dividends: credited only if we were ALREADY long entering this bar.
        # Buying at today's close is too late to collect today's ex-date payment.
        if state == "LONG" and today in div_map:
            cash += shares * div_map[today]

        # --- warm-up: need ENTRY_LOOKBACK completed bars before any signal.
        if t < ENTRY_LOOKBACK:
            equity_curve.append(cash + shares * close[t])
            continue
        if first_bar is None:
            first_bar = t

        # --- channels from strictly prior bars. Excluding the current bar is
        # forced, not stylistic: close > max(high) including today's own high is
        # unsatisfiable, so including it would produce a strategy that never trades.
        upper_channel = high[t - ENTRY_LOOKBACK:t].max()
        lower_channel = low[t - EXIT_LOOKBACK:t].min()
        c = close[t]

        if state == "FLAT":
            # ENTRY: strict inequality -- a close equal to the channel is not a breakout.
            if c > upper_channel:
                fill      = c + tick                      # slippage is always adverse
                notional  = POSITION_PCT * (cash + shares * c)
                shares    = notional / fill
                comm      = commission_rate * shares * fill
                cash     -= (shares * fill + comm)

                total_commission += comm
                total_slippage   += shares * tick
                entry = {"date": str(today.date()), "price": float(fill),
                         "shares": float(shares), "commission": float(comm),
                         "bar": t, "channel": float(upper_channel)}
                state = "LONG"

        else:  # state == "LONG"
            # EXIT: strict inequality. Note this is never reached on the entry
            # bar itself, so every position lives at least one bar.
            if c < lower_channel:
                fill   = c - tick                         # adverse again
                comm   = commission_rate * shares * fill
                cash  += (shares * fill - comm)

                total_commission += comm
                total_slippage   += shares * tick
                gross = shares * (fill - entry["price"])
                net   = gross - comm - entry["commission"]
                trades.append({
                    "entry_date": entry["date"], "entry_price": round(entry["price"], 4),
                    "exit_date": str(today.date()), "exit_price": round(fill, 4),
                    "shares": round(entry["shares"], 4),
                    "bars_held": t - entry["bar"],
                    "gross": round(gross, 2),
                    "costs": round(comm + entry["commission"], 2),
                    "net": round(net, 2),
                    "pct": round((fill / entry["price"] - 1.0) * 100, 4),
                })
                shares = 0.0
                entry  = None
                state  = "FLAT"

        equity_curve.append(cash + shares * close[t])

    open_trade = None
    if state == "LONG":
        mark = close[n - 1]
        open_trade = {
            "entry_date": entry["date"], "entry_price": round(entry["price"], 4),
            "mark_price": round(float(mark), 4), "shares": round(entry["shares"], 4),
            "bars_held": (n - 1) - entry["bar"],
            "unrealised": round(float(shares * (mark - entry["price"])), 2),
        }

    return {
        "equity": equity_curve,
        "trades": trades,
        "open_trade": open_trade,
        "total_commission": round(total_commission, 2),
        "total_slippage": round(total_slippage, 2),
        "first_bar": first_bar,
    }


# ----------------------------------------------------------------------------
# Benchmarks (spec A15)
# ----------------------------------------------------------------------------
def run_benchmark(df, div_map, weight, first_bar):
    """Buy `weight` of equity at the first tradeable bar and hold. Rest is cash
    at CASH_YIELD. Dividends paid as cash, matching the strategy's treatment."""
    close = df["Close"].values
    dates = df.index
    curve, cash, shares = [], START_EQUITY, 0.0
    for t in range(len(df)):
        if t == first_bar:
            shares = (weight * START_EQUITY) / close[t]
            cash  -= shares * close[t]
        if shares > 0 and dates[t] in div_map and t > first_bar:
            cash += shares * div_map[dates[t]]
        curve.append(cash + shares * close[t])
    return curve


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------
def max_drawdown(curve):
    peak, worst, worst_i = curve[0], 0.0, 0
    for i, v in enumerate(curve):
        peak = max(peak, v)
        dd = (v / peak) - 1.0
        if dd < worst:
            worst, worst_i = dd, i
    return worst, worst_i


def drawdown_series(curve):
    out, peak = [], curve[0]
    for v in curve:
        peak = max(peak, v)
        out.append((v / peak) - 1.0)
    return out


def longest_underwater(curve, dates):
    """Longest stretch from an equity peak until equity first regains that peak.
    Returned in both calendar days and trading bars."""
    peak, peak_i = curve[0], 0
    best_bars, best_start, best_end, best_recovered = 0, 0, 0, True
    for i, v in enumerate(curve):
        if v >= peak:
            span = i - peak_i
            if span > best_bars:
                best_bars, best_start, best_end, best_recovered = span, peak_i, i, True
            peak, peak_i = v, i
    tail = (len(curve) - 1) - peak_i          # still underwater at end of data?
    if tail > best_bars:
        best_bars, best_start, best_end, best_recovered = tail, peak_i, len(curve) - 1, False
    return {
        "bars": int(best_bars),
        "calendar_days": int((dates[best_end] - dates[best_start]).days),
        "start": str(dates[best_start].date()),
        "end": str(dates[best_end].date()),
        "recovered": bool(best_recovered),
    }


def yearly_table(curves, dates):
    """Calendar-year return for each curve, measured off the prior year-end value
    (the first year is measured off starting equity). Used to show *when* the
    strategy helped and when it gave ground away."""
    out = {}
    for name, curve in curves.items():
        s = pd.Series(curve, index=dates)
        ends = s.groupby(s.index.year).last()
        base = ends.shift(1)
        base.iloc[0] = START_EQUITY
        out[name] = {int(y): round(float(v), 2) for y, v in ((ends / base - 1) * 100).items()}
    out["years"] = sorted(out["A"].keys())
    return out


def summarise(curve, trades, dates, label):
    final   = curve[-1]
    net_ret = (final / START_EQUITY) - 1.0
    years   = (dates[-1] - dates[0]).days / 365.25
    cagr    = (final / START_EQUITY) ** (1 / years) - 1.0 if final > 0 else float("nan")
    mdd, mdd_i = max_drawdown(curve)

    wins   = [t["net"] for t in trades if t["net"] > 0]
    losses = [t["net"] for t in trades if t["net"] <= 0]
    net_profits = sorted((t["net"] for t in trades), reverse=True)
    total_net   = sum(net_profits)
    top5        = sum(net_profits[:5])

    return {
        "label": label,
        "final_equity": round(final, 2),
        "net_return_pct": round(net_ret * 100, 3),
        "cagr_pct": round(cagr * 100, 3),
        "years": round(years, 2),
        "max_drawdown_pct": round(mdd * 100, 3),
        "max_drawdown_date": str(dates[mdd_i].date()),
        "underwater": longest_underwater(curve, dates),
        "n_trades": len(trades),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(trades), 2) if trades else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "avg_win_pct": round(sum(t["pct"] for t in trades if t["net"] > 0) / len(wins), 3) if wins else None,
        "avg_loss_pct": round(sum(t["pct"] for t in trades if t["net"] <= 0) / len(losses), 3) if losses else None,
        "gross_profit": round(sum(wins), 2),
        "gross_loss": round(sum(losses), 2),
        "total_net_profit": round(total_net, 2),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 3) if losses and sum(losses) != 0 else None,
        "top5_sum": round(top5, 2),
        "top5_pct_of_net": round(100 * top5 / total_net, 2) if total_net > 0 else None,
        "top5_pct_of_gross": round(100 * top5 / sum(wins), 2) if wins else None,
        "top5_trades": net_profits[:5],
        "avg_bars_held": round(sum(t["bars_held"] for t in trades) / len(trades), 1) if trades else None,
    }


# ----------------------------------------------------------------------------
def main():
    df, div_map, quality = load_data()
    dates = df.index

    results = {}
    for key, cfg in VARIANTS.items():
        r = run_backtest(df, div_map, cfg["commission"], cfg["tick"])
        s = summarise(r["equity"], r["trades"], dates, cfg["label"])
        s["total_commission"] = r["total_commission"]
        s["total_slippage"]   = r["total_slippage"]
        s["total_friction"]   = round(r["total_commission"] + r["total_slippage"], 2)
        results[key] = {"summary": s, "trades": r["trades"], "open_trade": r["open_trade"],
                        "equity": r["equity"], "first_bar": r["first_bar"]}

    first_bar = results["A"]["first_bar"]
    bh100 = run_benchmark(df, div_map, 1.0, first_bar)
    bh10  = run_benchmark(df, div_map, POSITION_PCT, first_bar)

    def bench_summary(curve, label):
        final = curve[-1]
        years = (dates[-1] - dates[0]).days / 365.25
        mdd, mdd_i = max_drawdown(curve)
        return {
            "label": label,
            "final_equity": round(final, 2),
            "net_return_pct": round((final / START_EQUITY - 1) * 100, 3),
            "cagr_pct": round(((final / START_EQUITY) ** (1 / years) - 1) * 100, 3),
            "max_drawdown_pct": round(mdd * 100, 3),
            "max_drawdown_date": str(dates[mdd_i].date()),
            "underwater": longest_underwater(curve, dates),
        }

    # Exposure: share of tradeable bars spent LONG (identical in both variants).
    long_bars = sum(t["bars_held"] for t in results["A"]["trades"])
    if results["A"]["open_trade"]:
        long_bars += results["A"]["open_trade"]["bars_held"]
    tradeable = len(df) - first_bar

    # Downsample curves for the SVG charts only; every statistic above uses full daily data.
    step = 5
    idx = list(range(0, len(df), step))
    if idx[-1] != len(df) - 1:
        idx.append(len(df) - 1)

    payload = {
        "meta": {
            "symbol": SYMBOL,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "yfinance_version": yf.__version__,
            "pandas_version": pd.__version__,
            "start_date": str(dates[0].date()),
            "end_date": str(dates[-1].date()),
            "first_signal_date": str(dates[first_bar].date()),
            "n_bars": len(df),
            "tradeable_bars": tradeable,
            "start_equity": START_EQUITY,
            "position_pct": POSITION_PCT * 100,
            "entry_lookback": ENTRY_LOOKBACK,
            "exit_lookback": EXIT_LOOKBACK,
            "cash_yield_pct": CASH_YIELD * 100,
            "exposure_pct": round(100 * long_bars / tradeable, 2),
            "n_dividends": len(div_map),
            "first_dividend": str(min(div_map).date()) if div_map else None,
            "chart_step": step,
        },
        "quality": quality,
        "A": results["A"]["summary"],
        "B": results["B"]["summary"],
        "trades_A": results["A"]["trades"],
        "trades_B": results["B"]["trades"],
        "open_trade": results["A"]["open_trade"],
        "open_trade_B": results["B"]["open_trade"],
        "bench_100": bench_summary(bh100, "Buy & hold QQQ (100%)"),
        "bench_10": bench_summary(bh10, "Static 10% QQQ / 90% cash"),
        # Alignment sensitivity: buy-and-hold started on the very first bar of
        # history instead of the strategy's first tradeable bar. Proves the
        # comparison is not an artifact of where the benchmark was started.
        "bench_100_day1": bench_summary(
            run_benchmark(df, div_map, 1.0, 0), "Buy & hold from first bar of history"),
        "yearly": yearly_table(
            {"A": results["A"]["equity"], "B": results["B"]["equity"],
             "bench_10": bh10, "bench_100": bh100}, dates),
        "chart": {
            "dates": [str(dates[i].date()) for i in idx],
            "equity_A": [round(results["A"]["equity"][i], 2) for i in idx],
            "equity_B": [round(results["B"]["equity"][i], 2) for i in idx],
            "bench_10": [round(bh10[i], 2) for i in idx],
            "bench_100": [round(bh100[i], 2) for i in idx],
            "dd_A": [round(drawdown_series(results["A"]["equity"])[i] * 100, 3) for i in idx],
            "dd_bench_10": [round(drawdown_series(bh10)[i] * 100, 3) for i in idx],
            "dd_bench_100": [round(drawdown_series(bh100)[i] * 100, 3) for i in idx],
        },
    }

    with open("results.json", "w") as f:
        json.dump(payload, f)

    a, b = payload["A"], payload["B"]
    print("bars {}  {} -> {}".format(payload["meta"]["n_bars"],
                                     payload["meta"]["start_date"], payload["meta"]["end_date"]))
    print("exposure {}% of tradeable bars".format(payload["meta"]["exposure_pct"]))
    for s in (a, b):
        print("\n--- {} ---".format(s["label"]))
        print("  trades {}   win rate {}%   avg win {}   avg loss {}"
              .format(s["n_trades"], s["win_rate_pct"], s["avg_win"], s["avg_loss"]))
        print("  net return {}%   CAGR {}%   maxDD {}%"
              .format(s["net_return_pct"], s["cagr_pct"], s["max_drawdown_pct"]))
        print("  underwater {} days (recovered={})"
              .format(s["underwater"]["calendar_days"], s["underwater"]["recovered"]))
        print("  top5 = {}% of net profit   friction ${}"
              .format(s["top5_pct_of_net"], s.get("total_friction")))
    print("\nbench 100%: {}%   bench 10%: {}%".format(
        payload["bench_100"]["net_return_pct"], payload["bench_10"]["net_return_pct"]))


if __name__ == "__main__":
    main()
