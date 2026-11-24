# Analytics upgrade working notes (task chat-01M87MWFBNX46YPZ55XF8WBXEE)

## Parent rulings 23:10
- Candidates (resistance rule, overlap, universe) = reversible research: evaluate myself vs approved objective; clearly distinguish candidate choices from approved final implementation. No user question needed yet.
- Thndr X fees: verified official source below; report gross + fee sensitivity; never portray a placeholder as his actual fees.
- Approval authorizes separate implementation/testing only, NOT deployment. Main stays untouched.
- User asked to do dashboard Reboot himself; await; display NOT fully fixed until live re-verify.

## Thndr EGX fees (official: https://support.thndr.app/en/articles/638558-thndr-order-fees, updated 2026-08-18)
Per side: Thndr brokerage 2 EGP fixed + 0.1%; EGX 0.01%; MCDR 0.01%; FRA 0.005% (min 1 EGP); risk insurance 0.005%; stamp duty 0.05%.
=> per side ~0.18% + 2 EGP; round trip ~0.36% + 4 EGP (+ FRA minimums).
Thndr Trader (required for Thndr X) waives Thndr's 0.1% on first 50 orders/month => round trip then ~0.16% + fixed.
Backtest: fee_model = 0.0018 per side default; sensitivity 0.0008 (Trader-waived third-party only) and 0.0018. Fixed 2 EGP negligible at his typical sizes; note as omitted.

## Data loader check (scanner.py)
- get_stock_data(symbol) -> fetch_yahoo_history, yfinance-style params interval=1d (scanner.py:142-149). Need to confirm auto_adjust setting and whether raw Close used. Check fetch_yahoo_history body next run.
- Current stop rule (risk.py): stop = min(support20 - 0.5*ATR, close - 2*ATR) (wider/lower one). Keep as baseline, recomputed at execution price.

## Open candidate evaluations (backtest both, report comparison)
a. Resistance room rule: candidate A = Resistance_20 (indicators.py, prior-20-session high excl. signal day) vs candidate B = nearest swing high (local peaks). Default A.
b. Overlap: one open trade per stock; new signal ignored until prior outcome resolves (not-executed closes after 3-session window).
c. Universe: all 224 config.EGX_STOCKS with rolling per-date liquidity gate (20-session avg price*volume, threshold per config).
d. EMA20 distance: unify to 5% (approved first candidate).

## Repo state
- Clone: /tmp/Legend_Mo on main @ 4b20d9c. Branch analytics-dev @ 6ae6e38 exists locally + remotely. Token: vault write-file "GitHub Legend_Mo repair API token" (delete file after use). No empty commits.

## State at 2026-11-24 23:36 EET (findings v1 delivered)
- analytics-dev @ e749c3b pushed. main @ cdf2278 (display completeness fix live; deployed strategy module still stale until user's Reboot).
- Full-universe backtest DONE: raw + adjusted variants, v1_baseline/v1_advertised/v2, CA detection, portfolio sim, reconciliation. Results in .cache/{half1,half2,ed25,adj_a,audited_results}.json.
- Headline (adjusted research): v1_advertised hit 24.3% [20.5-28.5], +26.8% portfolio; v2(5%) hit 41.5% [30.4-53.7], +37.8% portfolio. Sensitivity 25%: hit 32%, +52.5%. ~13-month effective window, in-sample, no future-probability claims.
- Findings note (Arabic) delivered to parent 23:36. Awaiting steer. No user-facing composition yet.
- Display: fake-50 root cause fixed (COMI real = 35/80 locally); live shows honest "غير متاح" until Reboot (old strategy module live-proven via TypeError path). Market-context warning = scanner never saves context; feature NOT approved.
- 28 tickers lack usable Yahoo data (QNBE, TAQA, VALU, BONY...) — uninvestigated.
- GitHub token expires Nov 25: re-mint via vault write-file when needed.

## State at 23:38 EET (final artifact delivered, parameters FROZEN)
- analytics-dev @ ff64722 (verified via GitHub API). Automated tests in analytics/test_engine.py ALL PASS (causality, day-order, fees).
- Corrected same-data (adjusted) sensitivity: ema5 hit 41.5% [30.4-53.7] port +37.8% vs ema25 hit 30.2% [24.3-36.9] port +50.9%.
- Parent delivered limited preliminary finding to user (42%, median 16 sessions, caveats). Do NOT expand beyond it; no portfolio returns relayed to user.
- Parameters frozen for out-of-sample evaluation on future sessions.
- Remaining validation: out-of-sample run; 28 no-data tickers cause; MCDR custody fee; collision-assumption stress.
- Parent instructed: no display-complete claims pending Reboot; no guarantee COMI 35 appears post-reboot.

## Synthetic walk-forward fixture (23:43 EET)
analytics/test_walkforward.py: end-to-end fixture, one synthetic symbol per scenario.
Base series: 250 mild-uptrend bars + 10 flat bars + breakout bar (config found by grid
search: seed=11 drift=0.0004 vol=0.004 flat_drift=-0.002, +0.5% above 20d high @2x vol
-> BUY score 60, RSI 65.8). Scenarios, all PASS:
- SYN_TP1.CA -> tp1_first; SYN_STOP.CA -> stop_first; SYN_NOTEXEC.CA -> not_executed;
  SYN_EXPIRED.CA -> expired; SYN_UNRES.CA -> unresolved (data ends before 42-session horizon).
- WAIT: no natural synthetic config passed gates with RSI<=72 + EMA dist>5% (3 grid
  searches, honest limitation); tested via injected SignalV2(status=WAIT) patched into
  backtest loop -> recorded wait_filtered, never executed. Gate physics for WAIT already
  proven on real data (full-universe run has real wait_filtered records).
- Overlap: second breakout-looking day during open trade -> exactly one executed trade.
- Ledger reconciliation: all records classified, zero unknown outcomes.
- Deterministic cash: two same-day trades totaling 180k vs 100k cash -> second capped to
  remaining cash; identical results under reversed record order.
First fixture run exposed short continuations (engine correctly returned unresolved for
<42 post-signal bars) -> padded executed scenarios to 55 bars.
