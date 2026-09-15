# Strategy Spec — QQQ 20/10 Donchian Breakout (Long/Flat)

**Version:** 3
**Status:** Approved with modifications. Regenerated per instruction; **awaiting final go-ahead before any code is written.**
**Instrument:** QQQ (Invesco QQQ Trust, Series 1), US listed
**Bar interval:** Daily
**Data source:** Yahoo Finance
**History:** Full available history from inception to most recent completed bar
**Exposure:** Long or flat only. Never short. Never leveraged.
**Position size:** 10% of current equity per trade
**Deliverable:** Two variants — frictionless and friction-adjusted

### Changes in v3

1. Position sizing changed from 100% of equity to **10% of equity per trade** (§6).
2. The backtest now produces **two variants**: **A — Frictionless** and **B — Friction-adjusted** (0.05% commission + 1 tick slippage, per side) (§7).
3. Assumption **A7** (commissions) is superseded by the two-variant design.
4. Assumption **A14** (return on idle cash) is **escalated to the single most consequential assumption in this spec** as a direct consequence of change 1. See §8.4 and §10.
5. Benchmark specification revised, because 100% buy-and-hold is no longer comparable to a 10%-sized strategy (**A15**).

---

## 1. What this strategy is

A long-only Donchian channel breakout with an asymmetric window: a **20-day** entry channel and a **10-day** exit channel. Entry requires a close above the upper channel; exit requires a close below the lower channel.

Because the exit window (10) is shorter than the entry window (20), the exit reacts roughly twice as fast as the entry. Functionally the 10-day low acts as a **trailing stop that ratchets upward** as the trade works, while the 20-day high acts as a **confirmation filter** that keeps the system out of chop. This is the standard "slow in, fast out" trend-following shape.

At 10% position sizing the system is a **low-exposure overlay**, not a core allocation. Maximum exposure to QQQ at any instant is 10% of equity; the remaining 90%+ is cash at all times. Time-in-market is an output of the backtest, not a parameter.

---

## 2. Data specification

| Field | Value |
| --- | --- |
| Symbol | `QQQ` |
| Interval | `1d` |
| Range | Maximum available (`period=max`) |
| Fields required | Date, Open, High, Low, Close, Adjusted Close, Volume |
| Session | US regular trading session, consolidated tape, Eastern Time |
| Calendar | Implied by the returned rows — no synthetic calendar is constructed |

**Notes on this specific symbol's history**, each of which must be **verified from the downloaded data rather than assumed**:

- QQQ began trading in **March 1999**. The exact first bar date should be read from the data, not hardcoded.
- The fund traded under the ticker **QQQQ** on Nasdaq for part of its life (approximately 2004–2011) before reverting to QQQ. Yahoo Finance is expected to serve a continuous series under `QQQ`, but the series should be checked for a gap or a level discontinuity across that period.
- At least one **stock split** (believed 2:1, around March 2000) occurred. The raw `Close` column must be checked for an unadjusted split discontinuity. See Assumption **A1**.

---

## 3. Notation

Let bars be indexed `t = 1 … N` in chronological order.

- `H[t]`, `L[t]`, `C[t]`, `O[t]` — the high, low, close and open of bar `t`
- `UpperChannel[t] = max( H[t-20], H[t-19], … , H[t-1] )` — highest high over the 20 bars **strictly preceding** bar `t`
- `LowerChannel[t] = min( L[t-10], L[t-9], … , L[t-1] )` — lowest low over the 10 bars **strictly preceding** bar `t`
- `State[t] ∈ { FLAT, LONG }` — position state **entering** bar `t`, i.e. before bar `t`'s signal is evaluated

Both channels are computed from **completed prior bars only**. Bar `t`'s own high and low are excluded.

> This exclusion is not a stylistic choice — it is forced by logic. If bar `t`'s own high were included in the upper channel, the entry condition `C[t] > max(H)` could never fire, because a bar's close can never exceed its own high. The same argument applies to the exit. Any implementation that includes the current bar produces a strategy that never trades.

---

## 4. Trading rules

### 4.1 Initial state

`State[1] = FLAT`. The system begins with no position.

### 4.2 Warm-up

No signal may be evaluated on bar `t` unless `t > 20`, so that a full 20-bar upper channel exists. Bars `1 … 20` are skipped; the system is FLAT across them and they contribute no trades and no returns.

The 10-bar exit channel needs only 10 prior bars, which is always satisfied by the time any position exists, so the 20-bar warm-up governs.

### 4.3 The rules

Exactly one rule is evaluated per bar, selected by the current state.

**If `State[t] = FLAT` — evaluate entry only:**

> **ENTRY:** If `C[t] > UpperChannel[t]`, buy. `State[t+1] = LONG`.
> Otherwise remain flat. `State[t+1] = FLAT`.

**If `State[t] = LONG` — evaluate exit only:**

> **EXIT:** If `C[t] < LowerChannel[t]`, sell to flat. `State[t+1] = FLAT`.
> Otherwise remain long. `State[t+1] = LONG`.

### 4.4 Consequences of the state machine

These follow from §4.3 and are stated explicitly because they are common implementation forks:

- **At most one action per bar.** No same-bar exit-then-reenter, and no same-bar entry-then-exit.
- **No exit check on the entry bar.** If entry occurs on bar `t`, the first exit evaluation is bar `t+1`. A position therefore has a minimum holding period of one bar.
- **The exit channel is not reset at entry.** On the first bar after entry, `LowerChannel` is computed entirely from bars that occurred *before* the position existed. The channel is a pure rolling function of price and is indifferent to position state. See **A9**.
- **Entry and exit conditions are never both evaluated**, so no precedence rule between them is needed.
- **Signals are independent of equity, position size and friction.** The rules read price only. This is what makes the two variants in §7 directly comparable — see **A25**.

### 4.5 Boundary condition

Both comparisons are **strict inequalities**.

- `C[t]` exactly equal to `UpperChannel[t]` → **no entry**
- `C[t]` exactly equal to `LowerChannel[t]` → **no exit**

Exact equality is uncommon but does occur in real price data, particularly in the pre-decimalization era before April 2001 when US equities traded in fractions and repeated price levels were far more frequent. See **A10**.

---

## 5. Worked example

Illustrative numbers only — **not real QQQ data**. Purpose is to disambiguate the rules, not to demonstrate performance.

Assume on bar `t` the system is FLAT, and the 20 bars before `t` had a highest high of `100.00`.

| Case | `C[t]` | Condition | Result |
| --- | --- | --- | --- |
| a | 100.01 | `100.01 > 100.00` → true | **Enter long** at bar `t` |
| b | 100.00 | `100.00 > 100.00` → false | Stay flat (tie is not a breakout) |
| c | 99.98 | false | Stay flat |
| d | `H[t]`=101.50, `C[t]`=99.50 | false | Stay flat — an intraday breakout that fails to hold into the close is **not** a signal |

Now assume the system is LONG on some later bar `u`, and the 10 bars before `u` had a lowest low of `94.00`.

| Case | `C[u]` | Condition | Result |
| --- | --- | --- | --- |
| e | 93.99 | `93.99 < 94.00` → true | **Exit to flat** at bar `u` |
| f | 94.00 | false | Stay long |
| g | `L[u]`=92.00, `C[u]`=95.00 | false | Stay long — an intraday break of the channel that recovers by the close is **not** an exit |

Cases **d** and **g** are the defining behaviour of a close-based system: intraday penetration of either channel is ignored entirely. Only the settled closing price matters.

---

## 6. Position sizing and accounting model

### 6.1 Sizing rule — **CHANGED IN V3**

On each entry, deploy **10% of total current equity** (cash + any marked-to-market position value, which is zero at the moment of entry since the system is flat).

```
TargetNotional = 0.10 × Equity[at entry bar]
Shares         = TargetNotional ÷ EntryFillPrice
```

- **Compounding:** the 10% is recomputed from *current* equity at every entry, so position sizes grow and shrink with the account.
- **Single position:** unchanged from v2. One position at a time, entered whole and exited whole.
- **No pyramiding, no scaling, no partial exits.**
- **Maximum instantaneous exposure: 10% of equity.** The remaining ≥90% is cash.
- **No leverage.** The 90% cash is never used to amplify the position.

### 6.2 Consequence to be aware of

At 10% sizing, the strategy's contribution to total return is roughly **one-tenth of the underlying price move**, while **90%+ of equity sits in cash at all times, including while "fully invested."** Two things follow:

1. The assumed yield on idle cash (**A14**) is no longer a refinement — it is the **dominant term** in the equity curve over a 26-year history. Assuming 0% will make the strategy look close to flat regardless of how well the signals perform.
2. Comparing this against 100% buy-and-hold QQQ is not a like-for-like comparison. See **A15** for the revised benchmark set.

### 6.3 Accounting

- **Equity curve:** marked to market daily at the close, whether long or flat.
- **Cash balance:** tracked explicitly bar by bar. Cash decreases by notional + commission on entry, increases by notional − commission on exit.
- **Open position at end of data:** if the system is LONG on the final bar, the position is **not** force-closed. It is marked to market at the final close and reported as an open trade, excluded from closed-trade statistics but included in the equity curve.

---

## 7. The two variants — **NEW IN V3**

The backtest produces two complete, independently-reported result sets over the identical history.

### Variant A — Frictionless

| Component | Value |
| --- | --- |
| Commission | 0 |
| Slippage | 0 |
| Fill price | Signal bar's closing price, exactly |

Idealised upper bound. Isolates the raw edge of the signal logic.

### Variant B — Friction-adjusted

| Component | Value |
| --- | --- |
| Commission | **0.05% of traded notional, per side** |
| Slippage | **1 tick ($0.01) adverse, per side** |
| Fill price | Close ± 1 tick, in the adverse direction |

Fill prices:

```
Entry fill = C[t] + 0.01      (buy one tick worse — higher)
Exit  fill = C[t] − 0.01      (sell one tick worse — lower)
```

Commission on each side:

```
Commission = 0.0005 × Shares × FillPrice
```

A full round trip therefore costs **0.10% in commission plus 2 ticks of slippage.**

### 7.1 Both variants trade identically

Because signals depend only on price (§4.4), **Variants A and B enter and exit on exactly the same dates.** They differ only in fill price, commission drag, resulting share counts and P&L. No trade appears in one variant and not the other. This makes the difference between them a clean, isolated measurement of friction cost.

### 7.2 Expected magnitude of the friction gap

Illustrative arithmetic, not a result — recorded so the variants can be sanity-checked against expectation once they run:

| QQQ price | Slippage as % (1 tick) | Commission | Total per side | Round trip |
| --- | --- | --- | --- | --- |
| $25 | 0.040% | 0.050% | 0.090% | 0.180% |
| $100 | 0.010% | 0.050% | 0.060% | 0.120% |
| $300 | 0.003% | 0.050% | 0.053% | 0.107% |
| $600 | 0.002% | 0.050% | 0.052% | 0.103% |

Two observations:

- **Slippage is regressive across this history.** A fixed $0.01 tick was ~0.04% of price in the early-2000s and is ~0.002% today — a 20× difference in relative cost, concentrated in the earliest and longest-compounding years.
- **Scaled by 10% sizing**, a round trip costs roughly **0.010%–0.018% of total equity.** The gap between the two variants will therefore be **small in absolute terms** — likely a fraction of a percent per year — and will scale linearly with trade count. If Variant B comes out dramatically below Variant A, that is a bug, not a finding.

### 7.3 Reporting

Full metric set (§8.4 / **A13**) for each variant, plus a difference column isolating total friction cost in dollars, in CAGR, and as a percentage of Variant A's gross profit.

---

## 8. ASSUMPTIONS

Every rule below was a decision I had to make because the strategy description did not specify it. Each shows the **default** I will implement, the **alternative**, and the **impact** if the choice is wrong.

**⚠ CRITICAL** marks items that will materially distort or invalidate results if decided incorrectly.

### 8.1 Price series and adjustment

**A1 — Which price series feeds the signals. ⚠ CRITICAL**
Yahoo returns raw `Open/High/Low/Close` alongside a separate `Adj Close` scaled down for both splits and dividends. **These are not on the same scale and must never be mixed.** Comparing an adjusted close against raw highs compares a discounted number to an undiscounted one — across a 2:1 split and 26 years of distributions, that produces false signals wholesale, not a subtle bias.

- **Default:** a **single internally consistent OHLC series** for all signal generation — **split-adjusted but not dividend-adjusted**, by applying the split factor uniformly to O, H, L and C. This approximates what a trader actually saw on the chart in real time and keeps every comparison on one scale.
- **Alternative:** fully adjusted OHLC, scaling all four fields by the same total factor. Also internally consistent, but historical channel levels then correspond to prices that were never observable, and the series is retroactively restated (**A3**).
- **Impact:** catastrophic if mixed. Minor as between the two consistent options — QQQ's ~0.5%/yr yield shifts channel levels only slightly.

**A2 — Dividend treatment in returns.**
If signals use non-dividend-adjusted prices, dividends must still be credited or the strategy is unfairly penalised versus the benchmark.

- **Default:** credit dividends as **cash received on the ex-date while LONG**; nothing while FLAT. Economically correct, and cleanly separates signal logic from return accounting.
- **Note under 10% sizing:** dividends are received on only ~10% of equity, and only while in a position. The dividend contribution is therefore roughly **1/10th of what it would be at full size** — small in absolute terms.
- **Impact:** low at this position size.

**A3 — Reproducibility of the data.**
Yahoo restates its adjusted series on every distribution, so a backtest built on `Adj Close` yields slightly different numbers on each run. Raw OHLC is stable apart from splits.

- **Default:** snapshot the download to a local file (CSV/Parquet), record the download timestamp in the output, and run against the snapshot. Re-downloading becomes an explicit action, not a silent side effect.
- **Impact:** low on a single run; high for reproducing a result later.

**A4 — Data quality handling.**
Yahoo occasionally serves null rows, zero-volume placeholder bars, or bad ticks where High/Low are inconsistent with Close.

- **Default:** drop rows with any null in OHLC; assert `Low ≤ min(Open, Close)` and `High ≥ max(Open, Close)` on every bar and **report** violations rather than silently repairing them; no forward-fill. Log every removed row.
- **Impact:** usually negligible, occasionally decisive — one bad tick inside a rolling max contaminates 20 consecutive bars of signals.

### 8.2 Execution

**A5 — Execution price and timing. ⚠ CRITICAL**
The signal is only knowable *at* the close, so filling at that close assumes a zero-latency fill at the official settlement price.

- **Default:** fill at **the same bar's close** (± slippage in Variant B). Matches the literal reading of "buy when the candle closes above…", and market-on-close orders genuinely do fill at the official close.
- **Alternative:** fill at the **next bar's open**. More conservative; standard in most published trend-following work.
- **Impact:** material and systematic. Breakout entries frequently gap in the signal's favour overnight, so next-open fills typically *reduce* returns noticeably. Second most consequential decision after A1.

**A6 — Market impact.**
- **Default:** zero market impact beyond the modelled slippage. QQQ is among the most liquid instruments in existence and 10% of a retail account is negligible size.
- **Impact:** low.

**A7 — ~~Commissions~~ — SUPERSEDED IN V3.**
Replaced by the two-variant design in §7. No single commission assumption is made; both the zero-cost and 0.05%-per-side cases are reported.

**A8 — Share granularity.**
- **Default:** **fractional shares** permitted, so exactly 10.00% of equity is deployed on every entry.
- **Alternative:** whole shares only, leaving a residual and causing realised position size to drift slightly from 10%.
- **Impact:** negligible at realistic account sizes; fractional keeps sizing exact and the two variants cleanly comparable.

**A20 — Tick size definition. (NEW)**
"One tick" is taken as **$0.01** throughout.

- **Concern:** QQQ traded in **fractions** before decimalization (completed April 2001) — sixteenths ($0.0625) or coarser. A true tick in 1999–2001 was therefore **over 6× larger** than $0.01, and Variant B understates early-era slippage by that factor.
- **Default:** flat $0.01 for the entire history, for simplicity and transparency.
- **Alternative:** $0.0625 before April 2001, $0.01 thereafter.
- **Impact:** low in equity terms at 10% sizing, but it makes the earliest years of Variant B optimistic. Flagging rather than assuming it away — say the word and I will use the era-varying tick.

**A21 — Slippage direction. (NEW)**
Slippage is always **adverse**: buys fill one tick above the close, sells one tick below. Never favourable, never randomised.

- **Impact:** none if implemented as stated. A symmetric or random-sign slippage model would net toward zero and defeat the purpose of Variant B.

**A22 — Commission basis and interpretation of "per side". (NEW)**
- **Default:** 0.05% is charged **on traded notional** (`shares × fill price`), **not** on equity, and is applied **once per side** — so entry and exit are each charged, totalling 0.10% per round trip. The one-tick slippage is likewise applied per side.
- **This is my reading of "0.05% commission and one tick of slippage per side."** If you intended 0.05% as the *round-trip* total, say so — it halves the commission component.
- **Impact:** a 2× difference on the commission term, which is itself small at this position size.

**A23 — No commission minimum or maximum. (NEW)**
- **Default:** pure percentage, no floor and no cap. Real brokers often impose a $1 minimum, which at 10% sizing on a small account could exceed the percentage charge.
- **Impact:** low at $100,000 starting equity (10% = $10,000 notional, 0.05% = $5.00, comfortably above any typical minimum). Would matter on a small account.

**A24 — Friction does not apply to marking. (NEW)**
- **Default:** the daily mark-to-market of an open position uses the **unadjusted close**, with no slippage haircut. Friction is realised only at actual transactions.
- **Impact:** none on realised P&L; avoids double-counting cost in the equity curve.

**A25 — Friction does not affect signal generation. (NEW)**
- **Default:** channels and comparisons use unadjusted closes in **both** variants. Slippage changes fill prices only, never the price series the rules read.
- **Consequence:** both variants take identical trades on identical dates (§7.1). If they ever diverge in trade count, there is a bug.
- **Impact:** essential to the validity of the A-versus-B comparison.

### 8.3 Signal semantics

**A9 — The exit channel is a pure rolling window, not an entry-anchored stop.**
As noted in §4.4, `LowerChannel` looks back 10 bars regardless of when the position opened, so immediately after entry it references pre-entry price action.

- **Default:** pure rolling 10-bar low, unanchored — the standard Donchian construction and the literal reading of the request.
- **Alternative:** a trailing low measured only since entry. That is a genuinely different strategy, not an implementation detail.
- **Impact:** meaningful in the first ~10 bars of every trade; identical thereafter.

**A10 — Floating-point comparison at the boundary.**
- **Default:** direct comparison, no epsilon tolerance, after rounding both operands to 4 decimal places. A channel level is by construction copied from an actual historical high or low, so exact equality is representable and compares correctly.
- **Impact:** negligible in effect, but pins down the §4.5 tie rule so it is enforced rather than decided by float noise.

**A11 — Window measured in bars, not calendar days.**
"Previous 20 days" means 20 **rows of data** — 20 trading sessions. Weekends and exchange holidays do not exist in the series and are not counted. A 20-bar window spans about four calendar weeks, longer across holiday periods.

- **Impact:** none if implemented as stated; large if implemented as a calendar-day window.

**A12 — Market halts and limit days.**
No special handling. The 2020 circuit-breaker days and similar events are treated as ordinary bars.

### 8.4 Capital, benchmark and reporting

**A13 — Starting capital.**
- **Default:** **$100,000.** With fractional shares (A8), this affects only the scale of the equity curve, not returns or ratios. It does interact with commission minimums (**A23**), which is why it is worth stating.

**A14 — Return on idle cash. ⚠ CRITICAL — ESCALATED IN V3**
This was already the most under-appreciated assumption at 100% sizing. **At 10% sizing it becomes the dominant driver of the entire result.**

The portfolio now holds **at least 90% cash at every instant**, and 100% cash whenever flat. Across a history spanning ~6% short rates in 2000, ~0% for most of 2009–2021, and ~4–5% again in 2023–2026, the assumed cash yield is a larger contributor to the 26-year equity curve than the trading signal itself.

- **Default:** **0% on idle cash**, as approved in v2.
- **What this means in practice:** the reported equity curve will be, in effect, *the isolated P&L of the trading signal on a 10% sleeve*, with the other 90% of the portfolio deliberately modelled as dead money. That is a legitimate and clean way to measure the signal — but it is **not** a realistic portfolio return, and the headline CAGR will look poor for reasons that have nothing to do with signal quality.
- **Alternative:** credit a short-term risk-free rate on idle balances (3-month T-bill, `^IRX`), requiring a second data series.
- **Impact:** **large — now the single biggest term in the result.** I am implementing the 0% default as approved and will label the output clearly as signal-sleeve P&L rather than portfolio return. If you would rather see a realistic portfolio curve, this is the switch to flip.

**A15 — Benchmark. — REVISED IN V3**
100% buy-and-hold is no longer a like-for-like comparison against a 10%-sized strategy, so a single benchmark would mislead. Report three, all starting from the same capital on the same first tradeable bar (after the 20-bar warm-up, so all series start together):

1. **Buy-and-hold QQQ at 100%** — the "what if I just owned it" reference. Will almost certainly dominate on absolute return; that is expected and not a criticism of the strategy.
2. **Static 10% QQQ / 90% cash, never traded** — the true like-for-like control. **This is the benchmark that answers whether the timing signal adds anything**, since it holds exposure constant and removes only the timing decision.
3. **Strategy, Variants A and B.**

Benchmark 2 is the comparison that matters. Cash in the benchmarks earns the same rate as the strategy's cash (0% per A14), so the comparison stays internally consistent.

- **Impact:** none on the strategy; the conclusion is meaningless without benchmark 2.

**A16 — Taxes.**
- **Default:** **none modelled.** This system generates predominantly **short-term** gains, taxed as ordinary income in a US taxable account — a real and substantial drag a pre-tax backtest does not show.
- **Impact:** zero on the backtest as specified; potentially decisive in reality.

**A17 — Risk-free rate for Sharpe/Sortino.**
- **Default:** 0%, i.e. Sharpe on raw returns. Stated on the output so the figure is not misread. Consistent with A14.

**A18 — Annualisation convention.**
- **Default:** 252 trading days per year for annualising volatility; CAGR from actual elapsed calendar time between first and last bar.

**A19 — Timezone and session.**
- **Default:** Yahoo daily bars represent the US regular session in Eastern Time. No extended-hours data; no intraday data is required.

---

## 9. Reporting

Produced for **each variant**, side by side, plus the three benchmarks from **A15**:

- CAGR, total return, final equity
- Maximum drawdown (depth and duration), Calmar
- Volatility, Sharpe, Sortino *(at 10% sizing these will be low by construction — exposure is capped at 10%)*
- Trade count, win rate, average win, average loss, profit factor, expectancy
- Average holding period, longest and shortest trade
- **Time in market (% of bars LONG)** — essential context for every risk-adjusted figure above
- **Friction cost isolation:** total dollars paid in commission and slippage; CAGR difference A − B; friction as a percentage of Variant A gross profit
- Equity curve and drawdown chart, all series overlaid
- Full trade list (entry date, entry fill, exit date, exit fill, shares, gross P&L, costs, net P&L) for both variants

---

## 10. Items flagged for your attention — no response required, but worth a look

The spec is approved and I will implement exactly as written above. Three notes I would be doing you a disservice not to raise:

1. **A14 (0% cash yield) now dominates the result.** At 10% sizing the portfolio is ≥90% cash permanently, so the headline return figure will be poor for reasons unrelated to whether the signal works. Benchmark 2 in **A15** is designed to make the signal's contribution visible regardless — but if you want a realistic *portfolio* curve rather than an isolated signal-sleeve P&L, crediting a T-bill rate is the one change that gets you there.
2. **A22 — "per side" interpretation.** I read your instruction as 0.05% *and* one tick *each* on entry and exit (0.10% + 2 ticks per round trip). Straightforward to halve if you meant 0.05% round-trip.
3. **A20 — tick size pre-2001.** A flat $0.01 tick understates real slippage in 1999–2001, when QQQ traded in sixteenths. Small effect at 10% sizing, but it makes Variant B's earliest years optimistic.

**Standing by — no code will be written until you say go.**
