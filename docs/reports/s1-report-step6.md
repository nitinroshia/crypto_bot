# S1 report: ETH_USDT and BTC_USDT (Work Order 1.5 step 6)

Generated 2026-10-19 04:28:56Z by `s1_report.py` (read-only) at repo commit 4487f1e. Registry records are from the step-5 live run, commit 4487f1e; the pre-fix S1 records were voided by commit ac63ff2. Every figure below was recomputed from the discovery data and reproduces the registry's recorded figure (the generator refuses to run otherwise). Freeze and forward-test were not run; the holdout is untouched. This report states recorded outcomes and makes no recommendation.

### Summary of recorded outcomes
| pair | origins | primary slope | primary one-sided p | Holm within 10 | stability p_stab | stability passes | gate pooled net | gate non-negative blocks | gate passes | buy-and-hold pooled | buy-and-hold non-negative blocks | any year-driven |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETH_USDT | 2772 | 0.000715415 | 0.1282 | 0.7692 | 0.2304 | False | 4.923 | 40.0% | False | 3.129 | 60.0% | False |
| BTC_USDT | 2772 | 0.0010087 | 0.01451 | 0.1451 | 0.05547 | False | 34.55 | 50.0% | False | 8.509 | 43.3% | False |

## ETH_USDT  (S1-ETHUSDT)

Data file `ETH_USDT-1d.feather`: 212730 bytes, sha256 `00b5302c1d9b5edd931e8367fbc01acad5559537a44e63de841da1d4b8934c7f`.

### 1. Origin facts
- First origin 2018-01-24, last origin 2025-08-26; **2772 origins** (nominal 2772, excluded for gaps **0**, missing calendar days 0).
- **30 full 90-day blocks** (origins per full block min/median/max 90/90.0/90); partial block: **72 origins** (centred on, never scored).
- Economic-gate tiling over the discovery rows from the same first origin has the same full blocks: True.

### 2. Discovery table (10 cells, one common origin set, one-sided p, Holm within the 10)
Primary cell L=40, h=5; the other nine are exploratory. slope = OLS of the forward log return on x (x in trailing-30-day-sigma units); HAC = Newey-West (5 lags h=1, 10 lags h=5); corr = Pearson correlation of x and y at the common origins; MDE = 2.486 x HAC SE (one-sided 5% test, 80% power; computed from the SE, never post-hoc power).

| L | h | tag | slope | HAC SE | corr(x,y) | HAC t | one-sided p | Holm (within 10) | Bonferroni | MDE (80% power) | n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 1 | exploratory | 0.000494149 | 0.000263847 | 0.0365 | 1.873 | 0.03054 | 0.2749 | 0.3054 | 0.000656049 | 2772 |
| 20 | 1 | exploratory | 0.000314601 | 0.00017335 | 0.0340 | 1.815 | 0.03477 | 0.2749 | 0.3477 | 0.00043103 | 2772 |
| 40 | 1 | exploratory | 0.000148925 | 0.000134797 | 0.0232 | 1.105 | 0.1346 | 0.7692 | 1 | 0.00033517 | 2772 |
| 80 | 1 | exploratory | 5.39825e-05 | 0.000103523 | 0.0115 | 0.521 | 0.301 | 0.7692 | 1 | 0.000257408 | 2772 |
| 160 | 1 | exploratory | 6.92293e-05 | 6.83044e-05 | 0.0222 | 1.014 | 0.1554 | 0.7692 | 1 | 0.000169837 | 2772 |
| 10 | 5 | exploratory | 0.00252044 | 0.00104322 | 0.0841 | 2.416 | 0.007846 | 0.07846 | 0.07846 | 0.00259394 | 2772 |
| 20 | 5 | exploratory | 0.00142293 | 0.000777881 | 0.0695 | 1.829 | 0.03368 | 0.2749 | 0.3368 | 0.00193418 | 2772 |
| 40 | 5 | primary | 0.000715415 | 0.000630333 | 0.0504 | 1.135 | 0.1282 | 0.7692 | 1 | 0.00156731 | 2772 |
| 80 | 5 | exploratory | 0.000278633 | 0.000484188 | 0.0269 | 0.575 | 0.2825 | 0.7692 | 1 | 0.00120392 | 2772 |
| 160 | 5 | exploratory | 0.000342019 | 0.000341432 | 0.0495 | 1.002 | 0.1582 | 0.7692 | 1 | 0.000848962 | 2772 |

### 3. Stability (amended statistic, Work Order 1.5 section 3)
**T = 0.7082, p_stab = 0.230385** (B = 30 full blocks, R = 2000 bootstrap replicates, mean block length 20 days, seed 12345); share of blocks with s_b > 0: **56.7%**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **False**.

| block | start | origins | s_b | c_b (block score) |
|---|---|---|---|---|
| 0 | 2018-01-24 | 90 | 0.614 | 304.243 |
| 1 | 2018-04-24 | 90 | -0.597 | -192.133 |
| 2 | 2018-07-23 | 90 | 1.585 | 724.774 |
| 3 | 2018-10-21 | 90 | 0.926 | 444.563 |
| 4 | 2019-01-19 | 90 | -0.972 | -331.473 |
| 5 | 2019-04-19 | 90 | 1.112 | 483.098 |
| 6 | 2019-07-18 | 90 | -0.366 | -88.1567 |
| 7 | 2019-10-16 | 90 | 0.075 | 85.3234 |
| 8 | 2020-01-14 | 90 | 0.117 | 103.877 |
| 9 | 2020-04-13 | 90 | -0.020 | 52.753 |
| 10 | 2020-07-12 | 90 | 0.323 | 201.123 |
| 11 | 2020-10-10 | 90 | 1.705 | 768.79 |
| 12 | 2021-01-08 | 90 | -0.097 | 18.5511 |
| 13 | 2021-04-08 | 90 | 0.273 | 155.49 |
| 14 | 2021-07-07 | 90 | 0.110 | 107.613 |
| 15 | 2021-10-05 | 90 | -0.102 | 20.0314 |
| 16 | 2022-01-03 | 90 | 0.152 | 111.977 |
| 17 | 2022-04-03 | 90 | 2.027 | 927.781 |
| 18 | 2022-07-02 | 90 | -0.980 | -338.076 |
| 19 | 2022-09-30 | 90 | -1.904 | -720.122 |
| 20 | 2022-12-29 | 90 | -0.038 | 42.1751 |
| 21 | 2023-03-29 | 90 | -0.937 | -313.795 |
| 22 | 2023-06-27 | 90 | 0.699 | 334.088 |
| 23 | 2023-09-25 | 90 | 0.377 | 207.355 |
| 24 | 2023-12-24 | 90 | 0.954 | 452.961 |
| 25 | 2024-03-23 | 90 | -1.085 | -359.803 |
| 26 | 2024-06-21 | 90 | 0.111 | 88.555 |
| 27 | 2024-09-19 | 90 | -0.931 | -314.652 |
| 28 | 2024-12-18 | 90 | 0.915 | 428.382 |
| 29 | 2025-03-18 | 90 | -0.167 | -7.97212 |

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope 0.000715415. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = False**; every judged year's own sign agrees with the pooled sign: False.

| year | origins | days covered | slope (that year) | judged | slope without that year | year-driven? | year's sign vs pooled |
|---|---|---|---|---|---|---|---|
| 2018 | 342 | 342 | -0.00239291 | yes | 0.000554314 | no | opposite sign |
| 2019 | 365 | 365 | 0.00014479 | yes | 0.000764123 | no | same sign |
| 2020 | 366 | 366 | -0.00108555 | yes | 0.000622132 | no | opposite sign |
| 2021 | 365 | 365 | 0.000142032 | yes | 0.000612378 | no | same sign |
| 2022 | 365 | 365 | -0.00116839 | yes | 0.000743886 | no | opposite sign |
| 2023 | 365 | 365 | -0.000211677 | yes | 0.000776158 | no | opposite sign |
| 2024 | 366 | 366 | -0.000517856 | yes | 0.000884064 | no | opposite sign |
| 2025 | 238 | 238 | 0.00161901 | yes | 0.000596375 | no | same sign |

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4)
- Strategy (pre-registered rule: long from the next open if x > 0 at the close, else cash), stress cost 0.1500% per side: pooled net return **4.92255** (gross 6.39596); non-negative full blocks **40.0%** (12 of 30); recorded verdict: passes_pooled=True, passes_block_rate=False, passes=False.
- Trades: 148 position-change events (entries and exits, including the forced final exit); 74 complete round trips; hit rate (round trips with net return > 0): 36.5%; long on 52.6% of the days.
- End-of-sample exit: every evaluation segment starts flat and is forced to exit at its last close, charged as an exit cost (labeled forced exit; this run's forced exit: entered 2025-07-10, net 0.5815). The segment runs from the first origin 2018-01-24 to the last discovery bar 2025-08-31; no holdout bar is touched.
- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): pooled net return **3.12949** (price-only, before costs: 3.14191); non-negative full blocks **60.0%** (18 of 30).

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

| block | start | kind | strategy net | buy-and-hold net |
|---|---|---|---|---|
| 0 | 2018-01-24 | full | -0.3217 | -0.4155 |
| 1 | 2018-04-24 | full | -0.2088 | -0.2585 |
| 2 | 2018-07-23 | full | -0.0071 | -0.5544 |
| 3 | 2018-10-21 | full | -0.1687 | -0.4073 |
| 4 | 2019-01-19 | full | -0.1972 | 0.3635 |
| 5 | 2019-04-19 | full | 0.3604 | 0.2002 |
| 6 | 2019-07-18 | full | -0.2226 | -0.0615 |
| 7 | 2019-10-16 | full | -0.0726 | -0.2150 |
| 8 | 2020-01-14 | full | -0.3518 | 0.0803 |
| 9 | 2020-04-13 | full | 0.4130 | 0.5238 |
| 10 | 2020-07-12 | full | 0.4203 | 0.4546 |
| 11 | 2020-10-10 | full | 2.1961 | 2.4443 |
| 12 | 2021-01-08 | full | 0.4882 | 0.7474 |
| 13 | 2021-04-08 | full | -0.0029 | 0.0401 |
| 14 | 2021-07-07 | full | 0.2678 | 0.5557 |
| 15 | 2021-10-05 | full | 0.0382 | 0.1018 |
| 16 | 2022-01-03 | full | -0.0171 | -0.0824 |
| 17 | 2022-04-03 | full | -0.1880 | -0.6900 |
| 18 | 2022-07-02 | full | -0.1163 | 0.2485 |
| 19 | 2022-09-30 | full | -0.1546 | -0.0940 |
| 20 | 2022-12-29 | full | 0.2837 | 0.4157 |
| 21 | 2023-03-29 | full | -0.0264 | 0.1070 |
| 22 | 2023-06-27 | full | -0.1074 | -0.1606 |
| 23 | 2023-09-25 | full | 0.4134 | 0.4584 |
| 24 | 2023-12-24 | full | 0.3981 | 0.5026 |
| 25 | 2024-03-23 | full | -0.1170 | 0.0194 |
| 26 | 2024-06-21 | full | -0.1224 | -0.3423 |
| 27 | 2024-09-19 | full | 0.4627 | 0.7022 |
| 28 | 2024-12-18 | full | -0.1989 | -0.5266 |
| 29 | 2025-03-18 | full | 0.1448 | 0.3412 |
| 30 | 2025-06-16 | partial | 0.5303 | 0.7328 |

### 6. Registry
Records written by step 5 (live, after the void markers of commit ac63ff2):

| record (line in registry.jsonl) | status | timestamp (UTC) |
|---|---|---|
| 15 | discovery | 2026-10-18T22:58:38.292483+00:00 |
| 16 | stability | 2026-10-18T22:58:38.507963+00:00 |
| 17 | economic_gate | 2026-10-18T22:58:38.516601+00:00 |

`cumulative_count` for ETHUSDT: **1**; `cumulative_cells`: **10**. `holm_at_step` (across candidates; a family of one is unadjusted; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined):

| step | families at this step | p (raw) | Holm across candidates |
|---|---|---|---|
| discovery | 1 | 0.128192 | 0.128192 |
| stability | 1 | 0.230385 | 0.230385 |
| economic_gate | 1 | NaN | NaN |

### 7. Cutoff
The discovery frame (the file truncated at the cutoff 2025-08-31 23:59:59+00:00 before any computation) ends at 2025-08-31 and holds **0** rows after the cutoff (file: 3321 rows, 2017-08-17 to 2026-09-19; 2937 discovery rows).

## BTC_USDT  (S1-BTCUSDT)

Data file `BTC_USDT-1d.feather`: 222146 bytes, sha256 `6d32f277e71aca5c2bba7cef56361ec45c8a52adc4d1ba662c1ee1346eb0a674`.

### 1. Origin facts
- First origin 2018-01-24, last origin 2025-08-26; **2772 origins** (nominal 2772, excluded for gaps **0**, missing calendar days 0).
- **30 full 90-day blocks** (origins per full block min/median/max 90/90.0/90); partial block: **72 origins** (centred on, never scored).
- Economic-gate tiling over the discovery rows from the same first origin has the same full blocks: True.

### 2. Discovery table (10 cells, one common origin set, one-sided p, Holm within the 10)
Primary cell L=40, h=5; the other nine are exploratory. slope = OLS of the forward log return on x (x in trailing-30-day-sigma units); HAC = Newey-West (5 lags h=1, 10 lags h=5); corr = Pearson correlation of x and y at the common origins; MDE = 2.486 x HAC SE (one-sided 5% test, 80% power; computed from the SE, never post-hoc power).

| L | h | tag | slope | HAC SE | corr(x,y) | HAC t | one-sided p | Holm (within 10) | Bonferroni | MDE (80% power) | n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 1 | exploratory | 0.000339027 | 0.000212367 | 0.0321 | 1.596 | 0.0552 | 0.2569 | 0.552 | 0.000528044 | 2772 |
| 20 | 1 | exploratory | 0.00026537 | 0.000145373 | 0.0363 | 1.825 | 0.03397 | 0.2569 | 0.3397 | 0.000361465 | 2772 |
| 40 | 1 | exploratory | 0.000195948 | 0.000105882 | 0.0388 | 1.851 | 0.03211 | 0.2569 | 0.3211 | 0.000263272 | 2772 |
| 80 | 1 | exploratory | 0.000105136 | 7.27714e-05 | 0.0306 | 1.445 | 0.07427 | 0.2569 | 0.7427 | 0.000180944 | 2772 |
| 160 | 1 | exploratory | 5.31729e-06 | 4.3362e-05 | 0.0025 | 0.123 | 0.4512 | 0.9024 | 1 | 0.000107819 | 2772 |
| 10 | 5 | exploratory | 0.00170849 | 0.000822392 | 0.0731 | 2.077 | 0.01888 | 0.1699 | 0.1888 | 0.00204486 | 2772 |
| 20 | 5 | exploratory | 0.00110688 | 0.000629865 | 0.0685 | 1.757 | 0.03943 | 0.2569 | 0.3943 | 0.00156614 | 2772 |
| 40 | 5 | primary | 0.0010087 | 0.00046203 | 0.0905 | 2.183 | 0.01451 | 0.1451 | 0.1451 | 0.00114883 | 2772 |
| 80 | 5 | exploratory | 0.000538224 | 0.000328715 | 0.0710 | 1.637 | 0.05078 | 0.2569 | 0.5078 | 0.000817342 | 2772 |
| 160 | 5 | exploratory | 1.08293e-05 | 0.000202876 | 0.0023 | 0.053 | 0.4787 | 0.9024 | 1 | 0.000504447 | 2772 |

### 3. Stability (amended statistic, Work Order 1.5 section 3)
**T = 1.6966, p_stab = 0.0554723** (B = 30 full blocks, R = 2000 bootstrap replicates, mean block length 20 days, seed 12345); share of blocks with s_b > 0: **50.0%**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **False**.

| block | start | origins | s_b | c_b (block score) |
|---|---|---|---|---|
| 0 | 2018-01-24 | 90 | -0.286 | -51.9462 |
| 1 | 2018-04-24 | 90 | -0.197 | -8.33618 |
| 2 | 2018-07-23 | 90 | -0.515 | -144.437 |
| 3 | 2018-10-21 | 90 | 2.360 | 1054.62 |
| 4 | 2019-01-19 | 90 | 0.281 | 198.367 |
| 5 | 2019-04-19 | 90 | 3.308 | 1483.47 |
| 6 | 2019-07-18 | 90 | 0.573 | 326.333 |
| 7 | 2019-10-16 | 90 | -0.651 | -202.999 |
| 8 | 2020-01-14 | 90 | 0.397 | 223.589 |
| 9 | 2020-04-13 | 90 | 0.224 | 156.762 |
| 10 | 2020-07-12 | 90 | -1.078 | -380.818 |
| 11 | 2020-10-10 | 90 | 4.169 | 1899.02 |
| 12 | 2021-01-08 | 90 | -0.432 | -135.299 |
| 13 | 2021-04-08 | 90 | 0.188 | 149.571 |
| 14 | 2021-07-07 | 90 | -0.656 | -212.167 |
| 15 | 2021-10-05 | 90 | 0.148 | 147.884 |
| 16 | 2022-01-03 | 90 | -0.378 | -101.96 |
| 17 | 2022-04-03 | 90 | 2.052 | 960.762 |
| 18 | 2022-07-02 | 90 | -0.852 | -282.016 |
| 19 | 2022-09-30 | 90 | -0.663 | -222.556 |
| 20 | 2022-12-29 | 90 | 0.130 | 127.962 |
| 21 | 2023-03-29 | 90 | -0.972 | -335.772 |
| 22 | 2023-06-27 | 90 | 0.487 | 265.069 |
| 23 | 2023-09-25 | 90 | 1.566 | 705.602 |
| 24 | 2023-12-24 | 90 | 1.481 | 712.335 |
| 25 | 2024-03-23 | 90 | -0.588 | -165.835 |
| 26 | 2024-06-21 | 90 | -0.542 | -162.473 |
| 27 | 2024-09-19 | 90 | 0.330 | 209.747 |
| 28 | 2024-12-18 | 90 | -0.414 | -98.1178 |
| 29 | 2025-03-18 | 90 | -0.179 | -8.07156 |

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope 0.0010087. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = False**; every judged year's own sign agrees with the pooled sign: False.

| year | origins | days covered | slope (that year) | judged | slope without that year | year-driven? | year's sign vs pooled |
|---|---|---|---|---|---|---|---|
| 2018 | 342 | 342 | -0.00261138 | yes | 0.00104761 | no | opposite sign |
| 2019 | 365 | 365 | 0.0022649 | yes | 0.000822578 | no | same sign |
| 2020 | 366 | 366 | 0.00168543 | yes | 0.000768494 | no | same sign |
| 2021 | 365 | 365 | 0.000722013 | yes | 0.00105786 | no | same sign |
| 2022 | 365 | 365 | -0.00214287 | yes | 0.00101583 | no | opposite sign |
| 2023 | 365 | 365 | 3.27583e-05 | yes | 0.00109044 | no | same sign |
| 2024 | 366 | 366 | 0.000292095 | yes | 0.00106935 | no | same sign |
| 2025 | 238 | 238 | -0.000401106 | yes | 0.00109581 | no | opposite sign |

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4)
- Strategy (pre-registered rule: long from the next open if x > 0 at the close, else cash), stress cost 0.1500% per side: pooled net return **34.5543** (gross 43.8012); non-negative full blocks **50.0%** (15 of 30); recorded verdict: passes_pooled=True, passes_block_rate=False, passes=False.
- Trades: 154 position-change events (entries and exits, including the forced final exit); 77 complete round trips; hit rate (round trips with net return > 0): 42.9%; long on 55.0% of the days.
- End-of-sample exit: every evaluation segment starts flat and is forced to exit at its last close, charged as an exit cost (this run was flat at the end, so no forced exit occurred). The segment runs from the first origin 2018-01-24 to the last discovery bar 2025-08-31; no holdout bar is touched.
- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): pooled net return **8.50857** (price-only, before costs: 8.53716); non-negative full blocks **43.3%** (13 of 30).

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

| block | start | kind | strategy net | buy-and-hold net |
|---|---|---|---|---|
| 0 | 2018-01-24 | full | -0.0403 | -0.2271 |
| 1 | 2018-04-24 | full | -0.1570 | -0.1578 |
| 2 | 2018-07-23 | full | -0.2223 | -0.1176 |
| 3 | 2018-10-21 | full | -0.0177 | -0.4466 |
| 4 | 2019-01-19 | full | 0.3042 | 0.4398 |
| 5 | 2019-04-19 | full | 0.8127 | 0.8127 |
| 6 | 2019-07-18 | full | -0.0028 | -0.1149 |
| 7 | 2019-10-16 | full | -0.0125 | -0.0194 |
| 8 | 2020-01-14 | full | 0.0655 | -0.1598 |
| 9 | 2020-04-13 | full | 0.4101 | 0.3507 |
| 10 | 2020-07-12 | full | 0.0795 | 0.1763 |
| 11 | 2020-10-10 | full | 2.1847 | 2.3655 |
| 12 | 2021-01-08 | full | 0.5771 | 0.5771 |
| 13 | 2021-04-08 | full | -0.0360 | -0.4190 |
| 14 | 2021-07-07 | full | 0.0870 | 0.4307 |
| 15 | 2021-10-05 | full | 0.1518 | -0.0099 |
| 16 | 2022-01-03 | full | -0.1188 | -0.0302 |
| 17 | 2022-04-03 | full | -0.1171 | -0.5691 |
| 18 | 2022-07-02 | full | -0.1221 | -0.0265 |
| 19 | 2022-09-30 | full | -0.0814 | -0.1394 |
| 20 | 2022-12-29 | full | 0.4909 | 0.6237 |
| 21 | 2023-03-29 | full | 0.0944 | 0.1231 |
| 22 | 2023-06-27 | full | -0.0418 | -0.1276 |
| 23 | 2023-09-25 | full | 0.6647 | 0.6545 |
| 24 | 2023-12-24 | full | 0.3561 | 0.4897 |
| 25 | 2024-03-23 | full | -0.1404 | -0.0080 |
| 26 | 2024-06-21 | full | -0.2051 | -0.0717 |
| 27 | 2024-09-19 | full | 0.6480 | 0.7584 |
| 28 | 2024-12-18 | full | -0.2104 | -0.2214 |
| 29 | 2025-03-18 | full | 0.2460 | 0.2766 |
| 30 | 2025-06-16 | partial | 0.0247 | 0.0253 |

### 6. Registry
Records written by step 5 (live, after the void markers of commit ac63ff2):

| record (line in registry.jsonl) | status | timestamp (UTC) |
|---|---|---|
| 18 | discovery | 2026-10-18T22:58:39.829243+00:00 |
| 19 | stability | 2026-10-18T22:58:40.049273+00:00 |
| 20 | economic_gate | 2026-10-18T22:58:40.058108+00:00 |

`cumulative_count` for BTCUSDT: **1**; `cumulative_cells`: **10**. `holm_at_step` (across candidates; a family of one is unadjusted; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined):

| step | families at this step | p (raw) | Holm across candidates |
|---|---|---|---|
| discovery | 1 | 0.0145107 | 0.0145107 |
| stability | 1 | 0.0554723 | 0.0554723 |
| economic_gate | 1 | NaN | NaN |

### 7. Cutoff
The discovery frame (the file truncated at the cutoff 2025-08-31 23:59:59+00:00 before any computation) ends at 2025-08-31 and holds **0** rows after the cutoff (file: 3322 rows, 2017-08-17 to 2026-09-20; 2937 discovery rows).


## 8. Interpretation choices (all of them)
1. Void design (amendment A1, message-14): a void marker is one `void_pre_fix` record; every record of that (family, pair) written BEFORE its latest marker is void; refuses families with a live frozen/holdout_consumed record. Void commit of step 1: ac63ff2.
2. Registry hygiene (message-15): `append_record` refuses the live registry without `commit_to_registry=True`; the default registry is scratch; step 5 used the flag once per pair after a scratch dry run whose records the live records equal.
3. Origins (message-16): one common origin set on a complete daily calendar; a nominal origin needs every bar it uses (C_t, C_t-L for each L, the 31 closes behind sigma30, C_t+h for both h, the entry bar of day t+1) or it is excluded and counted; blocks are 90 calendar days tiled from the first origin, per-block index sets, partial block never scored. Here no gaps occurred.
4. Stability (message-17): global centring over the whole origin set including the partial block's origins (M1 ruling 1); bootstrap pool is the genuine returns r[1:] with the r[0]=0 anchor never resampled; R = 2000, mean block 20 days, seed 12345 (my choice, stored); `combine` follows the reference exactly; a series with missing days is refused. The acceptance run's S2-Gaussian row (0.085 against a band of 0.07) is OPEN for the mathematician (message-17); it does not concern S1.
5. Economic gate: unchanged (R4). It tiles the discovery rows (through the last discovery bar) from the common set's first origin, so its partial block runs to that bar while the origin-based partial block ends at the last origin; the pooled figure includes the partial block.
6. Buy-and-hold comparator (R4): the same evaluator, segment (first origin to the last discovery bar), blocks and stress cost, with the signal fixed at 1 (it enters at the open after the first origin and pays one entry and one forced exit). 'Price-only' is the same segment before costs. Whether 'over the same origins' should instead end at the last origin is the mathematician's call; I used the gate's own segment.
7. MDE: 2.486 x HAC SE (z 0.95 + z 0.80: one-sided 5% test, 80% power), in slope units; computed from the standard error as answer-01 requires. Correlation: Pearson, descriptive, at the common origins (the HAC SE is for the slope only).
8. By-year: calendar years of the origin dates (the first origin is in January 2018, the last in August 2025); the estimator is the primary cell's HAC regression slope on that year's origins, via the production hooks; the year-driven rule and the 120-day rule are `nonstationarity.py` as built in item 2.
9. P-values are one-sided in the pre-registered positive direction; Holm within the 10 cells is the family adjustment; across candidates each pair has a family of one at the discovery and stability steps, so the adjusted p equals the raw p there; the economic gate has no p-value.
10. Cutoff: the loader reads the full daily file and `truncate_at_cutoff` is applied before any computation (the item-2 pattern), so no post-cutoff row enters any figure; the check above counts rows after the cutoff in the discovery frame.
11. Nothing in this report is a recommendation. Freeze and forward-test were not run and the holdout was not touched; the stability and economic-gate outcomes are as recorded (`passes`).
