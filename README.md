# QQQ 20/10 Donchian Breakout Backtest

A long/flat trend-following backtest on QQQ, written as an explicit Python loop with no backtesting library, plus self-contained HTML reports.

**Headline result: the strategy lost to doing nothing.** Over 27.5 years it turned $100,000 into $115,749. Buying the same 10% position on day one and never trading ended at $223,013.

## The strategy

- **Entry:** buy when the daily close is above the highest high of the previous 20 trading days.
- **Exit:** sell when the daily close is below the lowest low of the previous 10 trading days.
- **Long or flat only.** No shorting, no leverage, one position at a time.
- **Position size:** 10% of current equity per trade.
- **Data:** QQQ daily bars from Yahoo Finance, 1999-03-10 to 2026-09-14 (6,921 bars).

Two variants are run, and they trade on identical dates:

- **A: Frictionless.** No costs.
- **B: Friction-adjusted.** 0.05% commission plus one $0.01 tick of slippage on both the buy and the sell.

The full rules, and every assumption the original strategy description left open, are in [Strategy_Spec.md](Strategy_Spec.md).

## Results

| | Net return | CAGR | Max drawdown | Longest underwater |
|---|---|---|---|---|
| Buy & hold QQQ (100%) | +1230.13% | +9.86% | −82.96% | 15.3 yrs |
| Static 10% QQQ / 90% cash (control) | +123.01% | +2.96% | −15.83% | 15.3 yrs |
| Strategy A: frictionless | +15.75% | +0.53% | −6.77% | 14.0 yrs |
| Strategy B: with costs | +13.97% | +0.48% | −7.07% | 14.9 yrs |

Strategy A made 120 trades with a 51.67% win rate. The average win was $583.91 and the average loss was −$369.66.

What the numbers mean:

- **The control is the fair comparison.** Buy & hold is fully invested every day. The strategy averages under 5% net exposure (a 10% position, held about half the time). The static 10% control has the same exposure and never trades, so it isolates whether the timing rule adds anything. The strategy lost to it by about 107 percentage points.
- **The small drawdown comes from position size, not skill.** At least 90% of the account is always idle cash.
- **The profit hangs on a few trades.** The top 5 of 120 trades produce 68.2% of net profit. Without them, 27 years of trading made $4,695.
- **Its one real strength is falling markets.** In the six years QQQ fell, it beat the control in five. In 2022 it lost 1.29% while buy & hold lost 31.35%. Over all 28 years, it beat the control in only 8.

## Reports

View the reports online:

- **[Backtest report](https://jazzthedog.github.io/Backtest-Strategy1/01_backtest.html)**: both variants, trade statistics, drawdown, and how concentrated the profits are.
- **[Benchmark report](https://jazzthedog.github.io/Backtest-Strategy1/02_benchmark.html)**: side-by-side comparison with buy & hold, including a year-by-year breakdown.

Both are designed for a 1920×1080 screen. Each report is one self-contained file with its data built in, so you can also download it and open it locally. Styling loads Tailwind from a CDN, so the page needs an internet connection to look right; the data and charts work without one.

## Running it

Requires Python 3.8 or newer.

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install yfinance pandas
```

```bash
.venv/Scripts/python.exe backtest.py
```

```bash
.venv/Scripts/python.exe build_report.py
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`.

**Python 3.8 only:** the latest `multitasking` package (a yfinance dependency) crashes on 3.8. If yfinance fails to import, pin the older version:

```bash
.venv/Scripts/python.exe -m pip install "multitasking==0.0.11"
```

`backtest.py` downloads the data, runs both variants and the benchmarks, and writes `results.json`. `build_report.py` inserts that data into the two HTML templates.

## Reproducibility

The raw price snapshot (`qqq_raw.csv`) is not in this repo because Yahoo's terms restrict redistributing its data. Running `backtest.py` creates it again from a fresh download.

Yahoo sometimes revises historical data, especially dividends, so a fresh run may not match these numbers exactly. During development, one re-run moved the buy & hold figure by about 0.8 percentage points while every strategy figure stayed the same.

## Files

| File | Purpose |
|---|---|
| `Strategy_Spec.md` | Plain-English rules and the full list of assumptions |
| `backtest.py` | Data download, backtest loop, benchmarks, and metrics |
| `build_report.py` | Builds the HTML reports from `results.json` |
| `report_template.html`, `report2_template.html` | Report templates |
| `01_backtest.html`, `02_benchmark.html` | Finished reports |
| `results.json` | All computed results |
| `probe.py` | One-off data check that confirmed Yahoo's prices are already split-adjusted |

## Limitations

- It tests one instrument, one pair of settings, and one stretch of history. There is no out-of-sample or parameter-sensitivity testing.
- Idle cash earns 0%. That understates returns for the strategy and the control far more than for buy & hold.
- Trades are filled at the closing price that triggers them, with no taxes and a fixed one-tick slippage. Before 2001, QQQ traded in sixteenths of a dollar, so real slippage then was higher than modelled.
- Yahoo Finance data is free retail data, not audit-grade.

Both reports list their limitations in full.

This is a research exercise, not investment advice.
