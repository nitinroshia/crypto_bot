# S2 report: ETH_USDT and BTC_USDT (Work Order 1.6 step 3) -- PRE-TAX

Generated 2026-10-25 07:14:17Z by `s2_report.py` (read-only) at repo commit 294afb8. Registry records are from the S2 live run, commit 294afb8, written once per pair. Every figure below was recomputed from the discovery data and reproduces the registry's recorded figure (the generator refuses to run otherwise). Freeze and forward-test were not run; the holdout is untouched. This report states recorded outcomes and makes no recommendation. M2's rulings of 2026-10-23 (`docs/correspondence/answer-s2-rulings.md`) override Work Order 1.6 where they differ.

### Summary of recorded outcomes
| pair | origins | B | primary slope (72h) | 72h one-sided p | 72h Holm within 2 | 24h one-sided p | stability p_stab | p_stab Holm across candidates | stability passes | gate pooled net | gate non-negative full blocks | gate passes | buy-and-hold pooled | buy-and-hold non-negative blocks | any year-driven |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETH_USDT | 6031 | 22 | -0.000661852 | 0.4637 | 0.6101 | 0.305 | 0.3843 | 0.4608 | False | 0.4319 | 14 of 22 (needs 16) | False | 16.72 | 13 of 22 | True |
| BTC_USDT | 6265 | 23 | -0.00540211 | 0.158 | 0.158 | 0.03162 | 0.09945 | 0.1109 | False | 0.2623 | 11 of 23 (needs 17) | False | 13.56 | 16 of 23 | False |

### Persistent-null calibration (M2's ruling of 2026-10-23, item 1)
1000 paths; one-sided p < 0.05 in **0.078** of paths for the primary 72h cell with 36 lags (band <= 0.08; binomial se 0.008) and **0.067** for the 24h cell with 12 lags (no band); with the superseded lags 3 and 9 the rates read 0.085 and 0.105 (information only).

## ETH_USDT  (S2-ETHUSDT)  -- pre-tax

Data files: `ETH_USDT-1h.feather` sha256 `3bc4dbe586fb659e83c2085c57a8a4983d5b01970a7526ee0b38ed55b97e6f32`; `ETH_USDT-1d.feather` sha256 `00b5302c1d9b5edd931e8367fbc01acad5559537a44e63de841da1d4b8934c7f`; `ETH_USDT-funding.feather` sha256 `9c805bed37379907987ba3423e745c0e352e9ee7b84fcf0aeb58596ebecdc376`.

### 1. Origin facts
- First funding settlement **2019-11-27 08:00:00+00:00**, last 2025-08-31 16:00:00+00:00; 6314 native rows to the cutoff, settlement interval hours {'8.0': 6313}, interval changes 0; 8h observations 6314 (complete 6313, masked 1; the first settlement is masked by construction).
- **Tie share** at the modal value 0.0001 up to the cutoff: **0.3963** of 6313 observations (the order expected about 0.396 for ETH and 0.401 for BTC).
- First origin **2020-02-25T16:00:00Z** (= first settlement + 271 x 8h), last origin **2025-08-28T16:00:00Z** (last settlement with s+1h+72h <= the last 1h bar 2025-08-31T23:00:00Z); **6031 origins** (nominal 6034, excluded **3**).
- **B = 22 full 90-day blocks** (origins per full block min/median/max 267/270.0/270); **partial block: 94 origins**; span 2012 days. Stricter cross-check of the block count: 22.
- Economic-gate tiling over the 1h discovery rows from the same first origin has the same full blocks: True (its partial block runs 34 days).
- 1h file (discovery frame): 70356 rows, 2017-08-17 04:00:00+00:00 .. 2025-08-31 23:00:00+00:00, missing hours inside: **128**; daily file: 2937 rows, missing days inside: **0**. Rows after the cutoff: see section 7.

| reason (first reason wins) | origins | settlement times (UTC) |
|---|---|---|
| rank_invalid | 0 | - |
| entry_bar_missing | 1 | 2020-12-21T16:00:00Z |
| exit24_bar_missing | 1 | 2020-12-20T16:00:00Z |
| exit72_bar_missing | 1 | 2020-12-18T16:00:00Z |

### 2. Discovery table (2 cells, one common origin set, one-sided p in the NEGATIVE direction, Holm within the 2)
Primary cell H = 72h; the 24h cell is secondary. slope = OLS of the forward log return from the open of bar s+1h to the open of bar s+1h+H on the mid-rank; HAC = Newey-West (Bartlett) with 4 x H/8h lags (M2's ruling, replacing the order's 3 and 9); corr = Pearson correlation at the common origins; MDE = 2.486 x HAC SE in slope units. The last column is a labeled sensitivity with the superseded lags and is not used for any decision.

| H (h) | HAC lags | tag | slope | HAC SE | corr(x,y) | HAC t | one-sided p | Holm (within 2) | Bonferroni | MDE (2.486 x SE) | n | sensitivity: superseded lags (not used) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24 | 12 | secondary | -0.00150521 | 0.00295138 | -0.0102 | -0.510 | 0.305 | 0.6101 | 0.6101 | 0.00733712 | 6031 | 3 lags: t -0.552, p 0.2904 |
| 72 | 36 | primary | -0.000661852 | 0.00725403 | -0.0026 | -0.091 | 0.4637 | 0.6101 | 0.9273 | 0.0180335 | 6031 | 9 lags: t -0.097, p 0.4614 |

Robustness columns on the primary cell only (labeled, never the primary statistic):

| rank variant (primary cell) | slope | HAC SE | corr | HAC t | one-sided p |
|---|---|---|---|---|---|
| mid-rank (primary) | -0.000661852 | 0.00725403 | -0.0026 | -0.091 | 0.4637 |
| strict-below | -0.0015432 | 0.00704989 | -0.0065 | -0.219 | 0.4134 |
| at-or-below | 0.000361067 | 0.00618111 | 0.0016 | 0.058 | 0.5233 |

Descriptive, exploratory only: mean forward return and its excess over the unconditional mean at the same horizon:

| H (h) | group | n | mean forward return | unconditional mean | excess |
|---|---|---|---|---|---|
| 24 | rank <= 0.10 | 686 | 0.00389386 | 0.0014365 | 0.00245736 |
| 24 | rank >= 0.90 | 627 | 0.00313931 | 0.0014365 | 0.00170281 |
| 72 | rank <= 0.10 | 686 | 0.00954137 | 0.00442181 | 0.00511956 |
| 72 | rank >= 0.90 | 627 | 0.00749452 | 0.00442181 | 0.00307271 |

### 3. Stability (amended statistic, Work Order 1.5 section 3, S2 time-shift variant; primary 72h cell only)
**T = 0.2713, p_stab = 0.384308** (B = 22 full blocks, R = 2000 circular time-shifts, minimum shift 300 settlements, seed 12345); share of blocks with s_b > 0: **54.5%**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **False**. Origins in blocks 5937 of 6031; partial block origins 94 (never scored, counted in the centring).
- **Across-candidate Holm (R1, S1 and S2 are both candidates for this pair):** raw p_stab 0.384308, Holm-adjusted **0.46077**; S2's raw p_stab must be below 0.025 to survive the two-candidate Holm: **no**.
- Labeled variant, stability on the 24h target (not recorded): T = 0.6955, p_stab = 0.230385.

| block | start | origins | s_b | c_b (block score) |
|---|---|---|---|---|
| 0 | 2020-02-25 | 270 | 1.171 | 23.816 |
| 1 | 2020-05-25 | 270 | -1.758 | -42.4054 |
| 2 | 2020-08-23 | 270 | -0.311 | -8.02636 |
| 3 | 2020-11-21 | 267 | -0.361 | -6.78363 |
| 4 | 2021-02-19 | 270 | 1.270 | 26.1237 |
| 5 | 2021-05-20 | 270 | 0.053 | -0.806402 |
| 6 | 2021-08-18 | 270 | 0.154 | 3.651 |
| 7 | 2021-11-16 | 270 | -0.719 | -16.8298 |
| 8 | 2022-02-14 | 270 | 0.841 | 15.275 |
| 9 | 2022-05-15 | 270 | 0.005 | 0.490483 |
| 10 | 2022-08-13 | 270 | -0.256 | -5.10975 |
| 11 | 2022-11-11 | 270 | -0.391 | -10.6508 |
| 12 | 2023-02-09 | 270 | 1.534 | 34.713 |
| 13 | 2023-05-10 | 270 | 1.414 | 24.8327 |
| 14 | 2023-08-08 | 270 | 0.588 | 14.8098 |
| 15 | 2023-11-06 | 270 | -0.329 | -9.55401 |
| 16 | 2024-02-04 | 270 | 0.009 | 0.920488 |
| 17 | 2024-05-04 | 270 | 1.742 | 29.8331 |
| 18 | 2024-08-02 | 270 | 0.020 | 1.2612 |
| 19 | 2024-10-31 | 270 | -1.224 | -41.7718 |
| 20 | 2025-01-29 | 270 | -1.759 | -48.5992 |
| 21 | 2025-04-29 | 270 | -0.418 | -10.0413 |

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope -0.000661852. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = True**; every judged year's own sign agrees with the pooled sign: False.

| year | origins | days covered | slope (that year) | judged | slope without that year | year-driven? | year's sign vs pooled |
|---|---|---|---|---|---|---|---|
| 2020 | 928 | 311 | -0.018958 | yes | 0.00176032 | YEAR-DRIVEN | same sign |
| 2021 | 1095 | 365 | 0.00338192 | yes | -0.0011231 | no | opposite sign |
| 2022 | 1095 | 365 | -0.0140674 | yes | 0.000859782 | YEAR-DRIVEN | same sign |
| 2023 | 1095 | 365 | -0.00964202 | yes | 0.00122489 | YEAR-DRIVEN | same sign |
| 2024 | 1098 | 366 | 0.00129945 | yes | -0.00111439 | no | opposite sign |
| 2025 | 720 | 240 | 0.031634 | yes | -0.00567637 | no | opposite sign |

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4), pre-tax
- Strategy (primary rule, M2's ruling of 2026-10-23: long from the open of the 1h bar labeled s+1h while the latest valid rank <= 0.5, otherwise cash; cash exactly when rank_s is invalid), stress cost 0.1500% per side: pooled net return **0.431909** (gross 5.78134); non-negative full blocks **63.6%** (**14 of 22**; the 70% rule needs at least **16**); recorded verdict: passes_pooled=True, passes_block_rate=False, passes=False.
- Trades: 1036 position-change events (entries and exits, including the forced final exit); 518 complete round trips; hit rate (round trips with net return > 0): 49.4%; long on 55.5% of the 1h bars in the segment.
- Settlements in the segment: 6043 (from the first origin to the last discovery bar, including those after the last origin); long decisions 3357; **settlements held in cash because rank_s is invalid: 0**; signal changes 1035; **trades executed on a substituted bar: 0**.
- End-of-sample exit: the segment starts flat at the first origin and is forced to exit at the last discovery bar's close, charged as an exit cost (labeled end-of-sample exit; this run's: entered 2025-08-25 01:00:00+00:00, net -0.0686). The segment runs from the first origin 2020-02-25 16:00:00+00:00 to the last discovery bar 2025-08-31 23:00:00+00:00; no holdout bar is touched.
- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): pooled net return **16.7209** (price-only, before costs: 16.7742); non-negative full blocks **59.1%** (13 of 22).
- Labeled variant, the order's literal reading (a missing entry or exit bar also forces cash; never recorded): pooled net return 0.431909, non-negative full blocks 63.6%, passes=False, trades 1036; settlements where the two readings differ: 0.

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

| block | start | kind | strategy net | buy-and-hold net |
|---|---|---|---|---|
| 0 | 2020-02-25 | full | 0.7167 | -0.1826 |
| 1 | 2020-05-25 | full | 0.3894 | 0.9263 |
| 2 | 2020-08-23 | full | 0.0905 | 0.3682 |
| 3 | 2020-11-21 | full | 0.9169 | 2.5936 |
| 4 | 2021-02-19 | full | 0.4810 | 0.5108 |
| 5 | 2021-05-20 | full | -0.3537 | 0.0622 |
| 6 | 2021-08-18 | full | 0.1285 | 0.4028 |
| 7 | 2021-11-16 | full | -0.3972 | -0.3186 |
| 8 | 2022-02-14 | full | 0.0229 | -0.2963 |
| 9 | 2022-05-15 | full | -0.0705 | -0.0417 |
| 10 | 2022-08-13 | full | -0.2464 | -0.3632 |
| 11 | 2022-11-11 | full | -0.1802 | 0.2976 |
| 12 | 2023-02-09 | full | 0.1381 | 0.1425 |
| 13 | 2023-05-10 | full | 0.0422 | -0.0173 |
| 14 | 2023-08-08 | full | 0.0240 | 0.0405 |
| 15 | 2023-11-06 | full | 0.0289 | 0.2018 |
| 16 | 2024-02-04 | full | 0.3116 | 0.3616 |
| 17 | 2024-05-04 | full | 0.0847 | -0.0294 |
| 18 | 2024-08-02 | full | -0.2474 | -0.1588 |
| 19 | 2024-10-31 | full | -0.1901 | 0.2116 |
| 20 | 2025-01-29 | full | -0.3501 | -0.4111 |
| 21 | 2025-04-29 | full | 0.0216 | 1.0757 |
| 22 | 2025-07-28 | partial | 0.0438 | 0.1586 |

Trade lists (one row per round trip, pre-tax): `s2-trades-ETH_USDT-strategy-stress.csv` (518 rows) and `s2-trades-ETH_USDT-buy-and-hold-stress.csv` (1 row), columns pair, entry_time_utc, exit_time_utc, entry_price, exit_price, gross_log_return, net_return_stress, exit_reason.

### 6. Registry
Records written by the S2 live run (live registry):

| record (line in registry.jsonl) | status | timestamp (UTC) |
|---|---|---|
| 21 | discovery | 2026-10-25T06:44:52.223739+00:00 |
| 22 | stability | 2026-10-25T06:44:52.230124+00:00 |
| 23 | economic_gate | 2026-10-25T06:44:52.399426+00:00 |

`cumulative_count` for ETHUSDT: **2**; `cumulative_cells`: **12**. `holm_at_step` (across candidates; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined). This pair's S2 family and, below, the S1 family whose adjusted values changed by design once S2 existed:

| step | families at this step | which | S2-ETHUSDT p (raw) | S2-ETHUSDT Holm across candidates |
|---|---|---|---|---|
| discovery | 2 | S1-ETHUSDT, S2-ETHUSDT | 0.463651 | 0.463651 |
| stability | 2 | S1-ETHUSDT, S2-ETHUSDT | 0.384308 | 0.46077 |
| economic_gate | 2 | S1-ETHUSDT, S2-ETHUSDT | NaN | NaN |

| step | S1-ETHUSDT p (raw) | S1-ETHUSDT Holm across candidates |
|---|---|---|
| discovery | 0.128192 | 0.256384 |
| stability | 0.230385 | 0.46077 |
| economic_gate | NaN | NaN |

### 7. Cutoff
The discovery frames (each file truncated at the cutoff 2025-08-31 23:59:59+00:00 before any computation) hold **0** 1h rows, **0** daily rows and **0** funding settlements after the cutoff (rows dropped by the truncation: 1h 9216, 1d 384, funding 1157). Last funding settlement 2025-08-31 16:00:00+00:00; last 1h bar 2025-08-31 23:00:00+00:00; last daily bar 2025-08-31 00:00:00+00:00.

## BTC_USDT  (S2-BTCUSDT)  -- pre-tax

Data files: `BTC_USDT-1h.feather` sha256 `2d9a776949daf1f38050cb0399e9081569f8510258ace212897b5f9e65860607`; `BTC_USDT-1d.feather` sha256 `6d32f277e71aca5c2bba7cef56361ec45c8a52adc4d1ba662c1ee1346eb0a674`; `BTC_USDT-funding.feather` sha256 `4550437429ae38f2f55ea949264b8942720b240b947c4bdfd2ec96b8df0e4d18`.

### 1. Origin facts
- First funding settlement **2019-09-10 08:00:00+00:00**, last 2025-08-31 16:00:00+00:00; 6548 native rows to the cutoff, settlement interval hours {'8.0': 6547}, interval changes 0; 8h observations 6548 (complete 6547, masked 1; the first settlement is masked by construction).
- **Tie share** at the modal value 0.0001 up to the cutoff: **0.4005** of 6547 observations (the order expected about 0.396 for ETH and 0.401 for BTC).
- First origin **2019-12-09T16:00:00Z** (= first settlement + 271 x 8h), last origin **2025-08-28T16:00:00Z** (last settlement with s+1h+72h <= the last 1h bar 2025-08-31T23:00:00Z); **6265 origins** (nominal 6268, excluded **3**).
- **B = 23 full 90-day blocks** (origins per full block min/median/max 267/270.0/270); **partial block: 58 origins**; span 2090 days. Stricter cross-check of the block count: 23.
- Economic-gate tiling over the 1h discovery rows from the same first origin has the same full blocks: True (its partial block runs 22 days).
- 1h file (discovery frame): 70356 rows, 2017-08-17 04:00:00+00:00 .. 2025-08-31 23:00:00+00:00, missing hours inside: **128**; daily file: 2937 rows, missing days inside: **0**. Rows after the cutoff: see section 7.

| reason (first reason wins) | origins | settlement times (UTC) |
|---|---|---|
| rank_invalid | 0 | - |
| entry_bar_missing | 1 | 2020-12-21T16:00:00Z |
| exit24_bar_missing | 1 | 2020-12-20T16:00:00Z |
| exit72_bar_missing | 1 | 2020-12-18T16:00:00Z |

### 2. Discovery table (2 cells, one common origin set, one-sided p in the NEGATIVE direction, Holm within the 2)
Primary cell H = 72h; the 24h cell is secondary. slope = OLS of the forward log return from the open of bar s+1h to the open of bar s+1h+H on the mid-rank; HAC = Newey-West (Bartlett) with 4 x H/8h lags (M2's ruling, replacing the order's 3 and 9); corr = Pearson correlation at the common origins; MDE = 2.486 x HAC SE in slope units. The last column is a labeled sensitivity with the superseded lags and is not used for any decision.

| H (h) | HAC lags | tag | slope | HAC SE | corr(x,y) | HAC t | one-sided p | Holm (within 2) | Bonferroni | MDE (2.486 x SE) | n | sensitivity: superseded lags (not used) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24 | 12 | secondary | -0.00378806 | 0.0020394 | -0.0340 | -1.857 | 0.03162 | 0.06325 | 0.06325 | 0.00506995 | 6265 | 3 lags: t -1.932, p 0.0267 |
| 72 | 36 | primary | -0.00540211 | 0.00538861 | -0.0287 | -1.003 | 0.158 | 0.158 | 0.3161 | 0.0133961 | 6265 | 9 lags: t -1.093, p 0.1372 |

Robustness columns on the primary cell only (labeled, never the primary statistic):

| rank variant (primary cell) | slope | HAC SE | corr | HAC t | one-sided p |
|---|---|---|---|---|---|
| mid-rank (primary) | -0.00540211 | 0.00538861 | -0.0287 | -1.003 | 0.158 |
| strict-below | -0.00439798 | 0.00568498 | -0.0234 | -0.774 | 0.2196 |
| at-or-below | -0.00491332 | 0.0044732 | -0.0298 | -1.098 | 0.136 |

Descriptive, exploratory only: mean forward return and its excess over the unconditional mean at the same horizon:

| H (h) | group | n | mean forward return | unconditional mean | excess |
|---|---|---|---|---|---|
| 24 | rank <= 0.10 | 745 | 0.00637535 | 0.00128949 | 0.00508585 |
| 24 | rank >= 0.90 | 627 | 0.00235082 | 0.00128949 | 0.00106133 |
| 72 | rank <= 0.10 | 745 | 0.0131972 | 0.00389571 | 0.00930152 |
| 72 | rank >= 0.90 | 627 | 0.00942443 | 0.00389571 | 0.00552873 |

### 3. Stability (amended statistic, Work Order 1.5 section 3, S2 time-shift variant; primary 72h cell only)
**T = 1.1411, p_stab = 0.0994503** (B = 23 full blocks, R = 2000 circular time-shifts, minimum shift 300 settlements, seed 12345); share of blocks with s_b > 0: **60.9%**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **False**. Origins in blocks 6207 of 6265; partial block origins 58 (never scored, counted in the centring).
- **Across-candidate Holm (R1, S1 and S2 are both candidates for this pair):** raw p_stab 0.0994503, Holm-adjusted **0.110945**; S2's raw p_stab must be below 0.025 to survive the two-candidate Holm: **no**.
- Labeled variant, stability on the 24h target (not recorded): T = 1.6003, p_stab = 0.0389805.

| block | start | origins | s_b | c_b (block score) |
|---|---|---|---|---|
| 0 | 2019-12-09 | 270 | 0.551 | 17.264 |
| 1 | 2020-03-08 | 270 | 0.176 | 5.45486 |
| 2 | 2020-06-06 | 270 | -0.099 | -1.02332 |
| 3 | 2020-09-04 | 270 | 1.344 | 38.3647 |
| 4 | 2020-12-03 | 267 | -1.277 | -36.1175 |
| 5 | 2021-03-03 | 270 | 0.410 | 10.6402 |
| 6 | 2021-06-01 | 270 | 0.198 | 6.86526 |
| 7 | 2021-08-30 | 270 | 0.210 | 4.95059 |
| 8 | 2021-11-28 | 270 | -0.338 | -6.89598 |
| 9 | 2022-02-26 | 270 | 1.879 | 32.2346 |
| 10 | 2022-05-27 | 270 | -0.720 | -12.5025 |
| 11 | 2022-08-25 | 270 | 1.597 | 32.339 |
| 12 | 2022-11-23 | 270 | -0.379 | -9.80894 |
| 13 | 2023-02-21 | 270 | 0.834 | 17.0711 |
| 14 | 2023-05-22 | 270 | 2.264 | 46.2739 |
| 15 | 2023-08-20 | 270 | 0.229 | 7.35096 |
| 16 | 2023-11-18 | 270 | 0.230 | 8.20672 |
| 17 | 2024-02-16 | 270 | -0.985 | -36.6304 |
| 18 | 2024-05-16 | 270 | 0.935 | 19.5653 |
| 19 | 2024-08-14 | 270 | -0.847 | -31.3537 |
| 20 | 2024-11-12 | 270 | -0.346 | -12.0029 |
| 21 | 2025-02-10 | 270 | -1.070 | -29.7197 |
| 22 | 2025-05-11 | 270 | 0.677 | 18.2178 |

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope -0.00540211. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = False**; every judged year's own sign agrees with the pooled sign: False.

| year | origins | days covered | slope (that year) | judged | slope without that year | year-driven? | year's sign vs pooled |
|---|---|---|---|---|---|---|---|
| 2019 | 67 | 23 | -0.015581 | no (< 120 days) | - | - | - |
| 2020 | 1095 | 366 | -0.0238226 | yes | -0.00316939 | no | same sign |
| 2021 | 1095 | 365 | -0.000334448 | yes | -0.00646128 | no | same sign |
| 2022 | 1095 | 365 | -0.0261883 | yes | -0.00348789 | no | same sign |
| 2023 | 1095 | 365 | -0.00839436 | yes | -0.00545684 | no | same sign |
| 2024 | 1098 | 366 | 0.00692605 | yes | -0.00804406 | no | opposite sign |
| 2025 | 720 | 240 | 4.46393e-06 | yes | -0.00639517 | no | opposite sign |

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4), pre-tax
- Strategy (primary rule, M2's ruling of 2026-10-23: long from the open of the 1h bar labeled s+1h while the latest valid rank <= 0.5, otherwise cash; cash exactly when rank_s is invalid), stress cost 0.1500% per side: pooled net return **0.262307** (gross 4.83626); non-negative full blocks **47.8%** (**11 of 23**; the 70% rule needs at least **17**); recorded verdict: passes_pooled=True, passes_block_rate=False, passes=False.
- Trades: 1020 position-change events (entries and exits, including the forced final exit); 510 complete round trips; hit rate (round trips with net return > 0): 42.9%; long on 49.9% of the 1h bars in the segment.
- Settlements in the segment: 6277 (from the first origin to the last discovery bar, including those after the last origin); long decisions 3129; **settlements held in cash because rank_s is invalid: 0**; signal changes 1020; **trades executed on a substituted bar: 0**.
- End-of-sample exit: the segment starts flat at the first origin and is forced to exit at the last discovery bar's close, charged as an exit cost (this run was flat at the end, so no forced exit occurred). The segment runs from the first origin 2019-12-09 16:00:00+00:00 to the last discovery bar 2025-08-31 23:00:00+00:00; no holdout bar is touched.
- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): pooled net return **13.5584** (price-only, before costs: 13.6021); non-negative full blocks **69.6%** (16 of 23).
- Labeled variant, the order's literal reading (a missing entry or exit bar also forces cash; never recorded): pooled net return 0.262307, non-negative full blocks 47.8%, passes=False, trades 1020; settlements where the two readings differ: 0.

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

| block | start | kind | strategy net | buy-and-hold net |
|---|---|---|---|---|
| 0 | 2019-12-09 | full | 0.0107 | 0.1552 |
| 1 | 2020-03-08 | full | -0.0226 | 0.1252 |
| 2 | 2020-06-06 | full | -0.0075 | 0.0754 |
| 3 | 2020-09-04 | full | 0.3687 | 0.8646 |
| 4 | 2020-12-03 | full | 0.3859 | 1.6239 |
| 5 | 2021-03-03 | full | -0.2921 | -0.2785 |
| 6 | 2021-06-01 | full | 0.2403 | 0.3017 |
| 7 | 2021-08-30 | full | -0.0485 | 0.1401 |
| 8 | 2021-11-28 | full | -0.1905 | -0.2788 |
| 9 | 2022-02-26 | full | 0.1470 | -0.2658 |
| 10 | 2022-05-27 | full | -0.3477 | -0.2477 |
| 11 | 2022-08-25 | full | -0.0427 | -0.2398 |
| 12 | 2022-11-23 | full | 0.0034 | 0.4992 |
| 13 | 2023-02-21 | full | 0.2107 | 0.0921 |
| 14 | 2023-05-22 | full | -0.0475 | -0.0332 |
| 15 | 2023-08-20 | full | 0.1124 | 0.4007 |
| 16 | 2023-11-18 | full | 0.1852 | 0.4222 |
| 17 | 2024-02-16 | full | 0.0828 | 0.2634 |
| 18 | 2024-05-16 | full | 0.1604 | -0.0929 |
| 19 | 2024-08-14 | full | -0.0046 | 0.4621 |
| 20 | 2024-11-12 | full | -0.0856 | 0.1180 |
| 21 | 2025-02-10 | full | -0.0741 | 0.0708 |
| 22 | 2025-05-11 | full | -0.0976 | 0.1230 |
| 23 | 2025-08-09 | partial | -0.0387 | -0.0760 |

Trade lists (one row per round trip, pre-tax): `s2-trades-BTC_USDT-strategy-stress.csv` (510 rows) and `s2-trades-BTC_USDT-buy-and-hold-stress.csv` (1 row), columns pair, entry_time_utc, exit_time_utc, entry_price, exit_price, gross_log_return, net_return_stress, exit_reason.

### 6. Registry
Records written by the S2 live run (live registry):

| record (line in registry.jsonl) | status | timestamp (UTC) |
|---|---|---|
| 24 | discovery | 2026-10-25T06:44:54.117731+00:00 |
| 25 | stability | 2026-10-25T06:44:54.124698+00:00 |
| 26 | economic_gate | 2026-10-25T06:44:54.299211+00:00 |

`cumulative_count` for BTCUSDT: **2**; `cumulative_cells`: **12**. `holm_at_step` (across candidates; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined). This pair's S2 family and, below, the S1 family whose adjusted values changed by design once S2 existed:

| step | families at this step | which | S2-BTCUSDT p (raw) | S2-BTCUSDT Holm across candidates |
|---|---|---|---|---|
| discovery | 2 | S1-BTCUSDT, S2-BTCUSDT | 0.158049 | 0.158049 |
| stability | 2 | S1-BTCUSDT, S2-BTCUSDT | 0.0994503 | 0.110945 |
| economic_gate | 2 | S1-BTCUSDT, S2-BTCUSDT | NaN | NaN |

| step | S1-BTCUSDT p (raw) | S1-BTCUSDT Holm across candidates |
|---|---|---|
| discovery | 0.0145107 | 0.0290213 |
| stability | 0.0554723 | 0.110945 |
| economic_gate | NaN | NaN |

### 7. Cutoff
The discovery frames (each file truncated at the cutoff 2025-08-31 23:59:59+00:00 before any computation) hold **0** 1h rows, **0** daily rows and **0** funding settlements after the cutoff (rows dropped by the truncation: 1h 9246, 1d 385, funding 1157). Last funding settlement 2025-08-31 16:00:00+00:00; last 1h bar 2025-08-31 23:00:00+00:00; last daily bar 2025-08-31 00:00:00+00:00.


## 8. Interpretation choices (all of them)
1. Label: this report is PRE-TAX. The trade lists (CSV) exist so that a later after-tax layer can be computed from dated trades (M2's item 9).
2. Origins (Work Order 1.6 section 1, message-20): one common origin set per pair on the 8h settlement grid; first usable origin = first settlement + 271 x 8h (slot 272 counting the masked first settlement as slot 1); last origin = last settlement with s+1h+72h <= the last 1h bar of the discovery frame; an origin whose rank is invalid (R2), entry bar or either exit bar is missing is excluded and counted by reason (first reason in that order), never imputed. The first settlements are at 08:00 UTC (the order's example assumed 00:00), so the first origins are at 16:00 UTC.
3. Predictor: mid-rank over the 270 previous slots (R2: all 270 previous slots and the current observation valid); ties are exact after rounding to 12 decimals; strict-below and at-or-below ranks are labeled robustness columns on the primary cell only.
4. Target: ln(open[s+1h+H] / open[s+1h]) on the 1h file, H = 24h and 72h in clock time; the bar labeled s itself never enters.
5. HAC lags (M2, 2026-10-23, replacing the order's 3 and 9): Newey-West (Bartlett) with 4 x H/8h = 12 (24h) and 36 (72h); lags count observations, not hours, so the few excluded origins shift the lag spacing very slightly. The superseded lags appear only as a labeled sensitivity column. MDE = 2.486 x HAC SE (z 0.95 + z 0.80).
6. P-values are one-sided in the negative direction (pre-registered); Holm within the 2 cells is the family adjustment; across candidates (R1) S1 and S2 form the family per pair at the discovery and stability steps, using each family's raw primary-cell p as recorded in the registry; the economic gate has no p-value.
7. Stability: once per pair on the 72h cell only; blocks are 90 calendar days tiled from the first origin, the partial block is never scored but counted in the centring; y = 72h forward return / sigma30, sigma30 = sd (ddof 1) of the last 30 daily log returns using only daily closes at or before the origin (all three settlements of day D use the close of day D-1); d = -1; circular time-shift null, minimum shift 300, R = 2000, seed 12345 stored. The 24h version is a labeled variant, not recorded.
8. Economic gate (M2's ruling, replacing the order's gap-excluded clause): the position at settlement s is cash exactly when rank_s is not valid (R2), otherwise long if rank_s <= 0.5; whether the entry or exit bars of the targets exist decides only origin-set membership. A decision is placed on the last 1h row with label <= s, so it executes at the open of s+1h, or at the next available bar's open (counted); the segment starts flat at the first origin, acts on every settlement up to the last discovery bar (the nine after the last origin included) and is forced out at the last discovery bar's close (end-of-sample exit). The order's literal reading is the labeled variant above.
9. Buy-and-hold comparator (R4): the same evaluator, segment, blocks and stress cost with the signal fixed at 1 (it enters at the open after the first origin bar and pays one entry and one forced exit). 'Price-only' is the same trade before costs.
10. By-year: calendar years of the origin dates; the estimator is the primary cell's HAC regression slope on that year's origins, via the production hooks; the year-driven rule and the 120-day rule are as in Work Order 1.5.
11. Cutoff: the loader truncates the funding, 1h and 1d files at the cutoff before any computation (the item-2 pattern), so no post-cutoff row enters any figure; section 7 counts rows after the cutoff in the discovery frames.
12. Persistent-null calibration (M2's ruling): the self-test's 1,000-path persistent null (AR(1) phi 0.98 per settlement, 40% ties at the low end, production mid-rank, overlapping iid hourly shocks, fixed seed) gives the rejection rates reported above; they are a property of the test, not of the data.
13. Nothing in this report is a recommendation. Freeze and forward-test were not run and the holdout was not touched; the stability and economic-gate outcomes are as recorded (`passes`).
