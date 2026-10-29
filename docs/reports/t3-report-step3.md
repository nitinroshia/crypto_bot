# Task 3 report: ETH_USDT and BTC_USDT (Work Order 1.7 section 5) -- PRE-TAX

Generated 2026-10-29 00:58:13Z by `t3_report.py` (read-only) at repo commit 3143fd8. Registry records are from the Task 3 live run, commit 3143fd8, written once per pair. Every figure below was recomputed from the discovery data with the production code and the recomputed records equal the live registry's field by field (the generator refuses to run otherwise). Freeze and forward test were not run; the holdout is untouched. This report states recorded outcomes and descriptive statistics; it makes no recommendation. M2's rulings of 2026-10-27 (`docs/correspondence/answer-t3-rulings.md`) override Work Order 1.7 where they differ.

### Summary of the primary cells (masked reading; M = 0.0035 on the excess)
| pair | primary cell | n | mean excess | t | one-sided p | Holm (48) | MDE | classification | stability T | p_stab | B' of full blocks | any year-driven | cells with MDE > M (of 48) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETH_USDT | 5m_k6_down | 4076 | -0.000461135 | -2.729 | 0.9968 | 1 | 0.0004201 | DEAD | -1.997 | 0.9771 | 32 of 32 | False | 0 |
| ETH_USDT | 5m_k6_up | 3801 | 0.00104674 | 6.113 | 4.891e-10 | 2.348e-08 | 0.0004257 | DEAD | 5.934 | 1.477e-09 | 31 of 32 | False | 0 |
| BTC_USDT | 5m_k6_down | 3991 | -0.000163071 | -1.086 | 0.8612 | 1 | 0.0003734 | DEAD | -0.120 | 0.548 | 32 of 32 | True | 0 |
| BTC_USDT | 5m_k6_up | 3718 | 0.000635005 | 4.641 | 1.738e-06 | 8.34e-05 | 0.0003402 | DEAD | 4.437 | 4.557e-06 | 32 of 32 | False | 0 |

### Acceptance results (Work Order 1.7 section 4), exact reproduction and checks
Exact reproduction of the reference (seed 2026, t4sv, 845280 bars): kept events identical to the reference's: **True** (down 5244, up 5506); n per side 5244 / 5506; mu_6 -0.0000018532; relative differences of mean excess, SE, t and T (down, up): down.mean 1.1e-14, down.se 2.4e-16, down.t 1.1e-14, down.T 9.6e-15, up.mean 9.3e-15, up.se 0.0e+00, up.t 9.3e-15, up.T 3.4e-14; largest 3.4e-14 (the order requires below 1e-8).

Full acceptance run on the owner's machine (`docs/reports/t3-acceptance-full-step1.txt`):

    Task 3 acceptance, FULL (Work Order 1.7 section 4), produced by deliveries/11/apply.sh on 2026-10-26T08:32:56Z (repo HEAD before this commit: 63edecf)
    Task 3 acceptance (FULL): 200 null paths per kind, 100 edge paths per delta
      PASS  null gauss false-pass down 0.035 up 0.040; p_stab down 0.030 up 0.055; classified dead 1.000
      PASS  null t4sv  false-pass down 0.015 up 0.045; p_stab down 0.030 up 0.040; classified dead 1.000
      PASS  null t3sv  false-pass down 0.035 up 0.035; p_stab down 0.050 up 0.030; classified dead 1.000
      PASS  edge +0.50% (t4sv): significant 1.00 stability 1.00 pass 1.00 dead 0.00 inconclusive 0.00
      PASS  edge +0.10% (t4sv): significant 1.00 stability 1.00 pass 0.00 dead 1.00 inconclusive 0.00
      info  edge +0.35% (t4sv): pass 0.11 dead 0.30 inconclusive 0.59 (reference: 0.10 / 0.35 / 0.55)
    total 91s
    ALL TASK 3 ACCEPTANCE TESTS PASSED

Checks of the live-run delivery (`docs/reports/t3-checks-step3.txt`):

    == check 1: masked-primary variant output against docs/reports/t3-variant-zero-volume-step2.txt
    variant check: 12 lines compared (4 sections x 3 lines per pair) -> all equal to the printed digits
    CHECK PASSED
    == check 2: dry-run primary cells against the masked variant rows
    dry-run records against the masked variant rows: 4 primary cells compared -> all equal to the printed digits
    CHECK PASSED
    == check 3: live records against the dry-run records
    live records against the dry-run records (4 records, every field except timestamp_utc) -> equal
    CHECK PASSED

### S1 / S2 regression result (`docs/reports/t3-regression-after-t3-step3.txt`)
The S1 and S2 reports were regenerated before any Task 3 record existed (S1 equal to the recorded post-S2 state, S2 equal to the committed report) and again after the live write (summary tables identical except the Holm-across-candidates column; only the across-candidate Holm rows and cumulative counts changed, by design):

    s1 report regression (after): 18 differing lines, summary table identical
    REGRESSION CHECK PASSED
    s2 report regression (after): 32 differing lines, summary table differs only in the Holm-across-candidates column
    REGRESSION CHECK PASSED

## ETH_USDT  (Task3-ETHUSDT)  -- pre-tax

### 1. Provenance
- 5m file `ETH_USDT-5m.feather` sha256 `efc4a7afb6bd8e70796e43734c0c0801f3c1b922ce441feaa688cdc9add2ca6f`; native 15m file none (the 15m bars are derived from 5m for both pairs).
- 5m rows in the file before the cutoff truncation 955046; rows in the discovery frame 844093; regular grid 845808 bars from 2017-08-17 04:00:00+00:00 to 2025-08-31 23:55:00+00:00; **rows after the cutoff in the discovery frame: 0**.
- Missing bars in the grid (primary reading, zero-volume bars masked): **3510**, of which 1715 are absent from the file and **1795** are zero-volume placeholder rows masked as missing (M2's ruling 2 of 2026-10-27). Under the literal reading (placeholders present) 1715 bars are missing.
- No native 15m file exists for this pair; nothing to compare.

### 2. Counts (item 8)
| timeframe | threshold | grid bars | present | missing | eligible origins | first origin | last origin | event bars before de-clustering (down / up) | kept after the shared clock (down / up) | dropped for an incomplete window | used in the statistics (down / up) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5m | |z| >= 3 | 845808 | 842298 | 3510 | 814602 | 2017-08-18T04:20 | 2025-08-31T22:55 | 6587 / 6365 | 4078 / 3802 | 3 gap, 0 cutoff | 4076 / 3801 |
| 5m | |z| >= 4 | 845808 | 842298 | 3510 | 814602 | 2017-08-18T04:20 | 2025-08-31T22:55 | 2801 / 2645 | 2001 / 1832 | 2 gap, 0 cutoff | 1999 / 1832 |
| 15m | |z| >= 3 | 281936 | 280164 | 1772 | 271137 | 2017-08-18T04:30 | 2025-08-31T20:45 | 2607 / 2305 | 1807 / 1577 | 4 gap, 0 cutoff | 1805 / 1575 |
| 15m | |z| >= 4 | 281936 | 280164 | 1772 | 271137 | 2017-08-18T04:30 | 2025-08-31T20:45 | 1190 / 1018 | 941 / 823 | 1 gap, 0 cutoff | 940 / 823 |

- [5m] not an origin: z window 30667, target window (gap inside the frame) 527, cutoff (bar j+12 beyond the frame) 12; flags: none
- [15m] not an origin: z window 10268, target window (gap inside the frame) 519, cutoff (bar j+12 beyond the frame) 12; flags: none
- Stability tiling: t0 = 2017-08-18 04:25:00+00:00 (entry time of the first eligible 5m origin); 32 full 90-day blocks; partial block 55.8 days.

### 3. mu_k table
| k | mu_k 5m (mean R_k over all eligible 5m origins) | mu_k 15m |
|---|---|---|
| 1 | 1.09694e-06 | 5.05086e-06 |
| 2 | 3.45374e-06 | 1.25388e-05 |
| 3 | 5.75176e-06 | 1.99021e-05 |
| 4 | 8.1156e-06 | 2.71046e-05 |
| 5 | 1.04054e-05 | 3.44442e-05 |
| 6 | 1.26997e-05 | 4.1467e-05 |
| 7 | 1.49525e-05 | 4.82561e-05 |
| 8 | 1.72103e-05 | 5.46808e-05 |
| 9 | 1.95121e-05 | 6.12451e-05 |
| 10 | 2.17691e-05 | 6.78475e-05 |
| 11 | 2.40197e-05 | 7.47295e-05 |
| 12 | 2.62664e-05 | 8.18299e-05 |

### 4. The 48 cells (family size 48; Holm and Bonferroni over all 48; primary cells one-sided positive, the other 46 two-sided and descriptive)
| tf | k | side | n | mean raw R_k | mean excess | clustered SE | naive SE | t | p (one-sided positive for the primary, two-sided otherwise) | Holm (48) | Bonferroni (48) | MDE (2.486 x SE) | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5m | 1 | down | 4076 | -9.138e-06 | -1.023e-05 | 9.316e-05 | 9.71e-05 | -0.110 | 0.9125 | 1 | 1 | 0.0002316 |  |
| 5m | 1 | up | 3801 | 0.0003298 | 0.0003287 | 8.881e-05 | 8.815e-05 | 3.701 | 0.000215 | 0.00645 | 0.01032 | 0.0002208 |  |
| 5m | 2 | down | 4076 | -0.0001929 | -0.0001963 | 0.0001166 | 0.0001259 | -1.683 | 0.09234 | 1 | 1 | 0.0002899 |  |
| 5m | 2 | up | 3801 | 0.0004031 | 0.0003996 | 0.0001096 | 0.0001101 | 3.646 | 0.0002659 | 0.007711 | 0.01276 | 0.0002724 |  |
| 5m | 3 | down | 4076 | -0.0003661 | -0.0003719 | 0.00014 | 0.0001491 | -2.657 | 0.007881 | 0.1813 | 0.3783 | 0.0003479 |  |
| 5m | 3 | up | 3801 | 0.0006655 | 0.0006598 | 0.0001308 | 0.0001323 | 5.045 | 4.54e-07 | 1.771e-05 | 2.179e-05 | 0.0003251 |  |
| 5m | 4 | down | 4076 | -0.0004643 | -0.0004724 | 0.0001568 | 0.0001733 | -3.013 | 0.002585 | 0.06204 | 0.1241 | 0.0003898 |  |
| 5m | 4 | up | 3801 | 0.000728 | 0.0007199 | 0.0001477 | 0.0001512 | 4.873 | 1.101e-06 | 3.965e-05 | 5.287e-05 | 0.0003673 |  |
| 5m | 5 | down | 4076 | -0.0003955 | -0.0004059 | 0.0001558 | 0.000173 | -2.605 | 0.009192 | 0.2022 | 0.4412 | 0.0003874 |  |
| 5m | 5 | up | 3801 | 0.0007825 | 0.0007721 | 0.0001579 | 0.0001646 | 4.890 | 1.007e-06 | 3.726e-05 | 4.834e-05 | 0.0003925 |  |
| 5m | 6 | down | 4076 | -0.0004484 | -0.0004611 | 0.000169 | 0.0001891 | -2.729 | 0.9968 | 1 | 1 | 0.0004201 | PRIMARY |
| 5m | 6 | up | 3801 | 0.001059 | 0.001047 | 0.0001712 | 0.000175 | 6.113 | 4.891e-10 | 2.348e-08 | 2.348e-08 | 0.0004257 | PRIMARY |
| 5m | 7 | down | 4076 | -0.0004378 | -0.0004528 | 0.0001754 | 0.0002011 | -2.581 | 0.009844 | 0.2067 | 0.4725 | 0.0004361 |  |
| 5m | 7 | up | 3801 | 0.001082 | 0.001067 | 0.0001806 | 0.0001876 | 5.912 | 3.388e-09 | 1.525e-07 | 1.626e-07 | 0.0004489 |  |
| 5m | 8 | down | 4076 | -0.0003718 | -0.000389 | 0.0001862 | 0.0002083 | -2.089 | 0.03669 | 0.6971 | 1 | 0.0004629 |  |
| 5m | 8 | up | 3801 | 0.001062 | 0.001044 | 0.0001853 | 0.0001931 | 5.634 | 1.757e-08 | 7.378e-07 | 8.432e-07 | 0.0004608 |  |
| 5m | 9 | down | 4076 | -0.0001396 | -0.0001592 | 0.0001866 | 0.0002066 | -0.853 | 0.3938 | 1 | 1 | 0.0004639 |  |
| 5m | 9 | up | 3801 | 0.001161 | 0.001142 | 0.0001907 | 0.0001989 | 5.987 | 2.132e-09 | 1.002e-07 | 1.024e-07 | 0.000474 |  |
| 5m | 10 | down | 4076 | -0.0001435 | -0.0001653 | 0.0001897 | 0.0002112 | -0.872 | 0.3835 | 1 | 1 | 0.0004715 |  |
| 5m | 10 | up | 3801 | 0.001205 | 0.001183 | 0.0001992 | 0.000205 | 5.940 | 2.856e-09 | 1.314e-07 | 1.371e-07 | 0.0004953 |  |
| 5m | 11 | down | 4076 | -0.0002127 | -0.0002367 | 0.0001954 | 0.000215 | -1.211 | 0.2258 | 1 | 1 | 0.0004858 |  |
| 5m | 11 | up | 3801 | 0.00118 | 0.001156 | 0.000201 | 0.0002056 | 5.753 | 8.789e-09 | 3.867e-07 | 4.219e-07 | 0.0004997 |  |
| 5m | 12 | down | 4076 | -0.0002319 | -0.0002582 | 0.0002059 | 0.0002283 | -1.254 | 0.2099 | 1 | 1 | 0.0005119 |  |
| 5m | 12 | up | 3801 | 0.001202 | 0.001175 | 0.0002063 | 0.0002119 | 5.697 | 1.22e-08 | 5.244e-07 | 5.854e-07 | 0.0005129 |  |
| 15m | 1 | down | 1805 | -0.0005236 | -0.0005286 | 0.0002318 | 0.0002414 | -2.280 | 0.02258 | 0.4516 | 1 | 0.0005763 |  |
| 15m | 1 | up | 1575 | 0.001002 | 0.0009972 | 0.0002023 | 0.0002018 | 4.928 | 8.305e-07 | 3.156e-05 | 3.986e-05 | 0.000503 |  |
| 15m | 2 | down | 1805 | -0.0005861 | -0.0005986 | 0.0002868 | 0.0003157 | -2.087 | 0.03686 | 0.6971 | 1 | 0.000713 |  |
| 15m | 2 | up | 1575 | 0.001436 | 0.001423 | 0.0002572 | 0.0002566 | 5.532 | 3.162e-08 | 1.296e-06 | 1.518e-06 | 0.0006395 |  |
| 15m | 3 | down | 1805 | -0.0004465 | -0.0004664 | 0.0003173 | 0.0003327 | -1.470 | 0.1415 | 1 | 1 | 0.0007887 |  |
| 15m | 3 | up | 1575 | 0.001602 | 0.001582 | 0.0003073 | 0.000309 | 5.147 | 2.646e-07 | 1.059e-05 | 1.27e-05 | 0.000764 |  |
| 15m | 4 | down | 1805 | -0.0003134 | -0.0003405 | 0.0003894 | 0.0003976 | -0.874 | 0.3818 | 1 | 1 | 0.000968 |  |
| 15m | 4 | up | 1575 | 0.001606 | 0.001579 | 0.0003284 | 0.000332 | 4.808 | 1.528e-06 | 5.348e-05 | 7.334e-05 | 0.0008165 |  |
| 15m | 5 | down | 1805 | 1.586e-05 | -1.858e-05 | 0.0003924 | 0.0004089 | -0.047 | 0.9622 | 1 | 1 | 0.0009756 |  |
| 15m | 5 | up | 1575 | 0.001625 | 0.00159 | 0.0003664 | 0.0003637 | 4.340 | 1.425e-05 | 0.0004845 | 0.000684 | 0.000911 |  |
| 15m | 6 | down | 1805 | -0.0001076 | -0.0001491 | 0.000419 | 0.0004308 | -0.356 | 0.722 | 1 | 1 | 0.001042 |  |
| 15m | 6 | up | 1575 | 0.001583 | 0.001542 | 0.0003782 | 0.0003692 | 4.076 | 4.581e-05 | 0.001466 | 0.002199 | 0.0009402 |  |
| 15m | 7 | down | 1805 | -1.89e-05 | -6.716e-05 | 0.0004462 | 0.0004675 | -0.151 | 0.8804 | 1 | 1 | 0.001109 |  |
| 15m | 7 | up | 1575 | 0.00169 | 0.001642 | 0.0003969 | 0.0003904 | 4.137 | 3.513e-05 | 0.001159 | 0.001686 | 0.0009866 |  |
| 15m | 8 | down | 1805 | 5.21e-06 | -4.947e-05 | 0.0004306 | 0.0004649 | -0.115 | 0.9085 | 1 | 1 | 0.00107 |  |
| 15m | 8 | up | 1575 | 0.001712 | 0.001657 | 0.0004179 | 0.000411 | 3.965 | 7.334e-05 | 0.002274 | 0.00352 | 0.001039 |  |
| 15m | 9 | down | 1805 | 0.000337 | 0.0002758 | 0.0004405 | 0.0004588 | 0.626 | 0.5313 | 1 | 1 | 0.001095 |  |
| 15m | 9 | up | 1575 | 0.001625 | 0.001564 | 0.0004487 | 0.0004409 | 3.485 | 0.000492 | 0.01378 | 0.02361 | 0.001116 |  |
| 15m | 10 | down | 1805 | 0.0002157 | 0.0001478 | 0.0004739 | 0.0004831 | 0.312 | 0.7551 | 1 | 1 | 0.001178 |  |
| 15m | 10 | up | 1575 | 0.001649 | 0.001581 | 0.0004679 | 0.0004587 | 3.380 | 0.000726 | 0.01918 | 0.03485 | 0.001163 |  |
| 15m | 11 | down | 1805 | 0.0001751 | 0.0001003 | 0.0005061 | 0.000504 | 0.198 | 0.8428 | 1 | 1 | 0.001258 |  |
| 15m | 11 | up | 1575 | 0.001715 | 0.001641 | 0.0004846 | 0.0004793 | 3.386 | 0.0007103 | 0.01918 | 0.0341 | 0.001205 |  |
| 15m | 12 | down | 1805 | 2.294e-05 | -5.889e-05 | 0.0005098 | 0.0005121 | -0.116 | 0.908 | 1 | 1 | 0.001267 |  |
| 15m | 12 | up | 1575 | 0.001713 | 0.001631 | 0.0005028 | 0.0004923 | 3.244 | 0.001179 | 0.02948 | 0.05661 | 0.00125 |  |

### 5. Classification of the two primary cells (5m, k = 6)
| primary cell | n | mean excess | clustered SE | t | one-sided p | Holm (48) | MDE | mean + 1.645 SE | classification (M = 0.0035) | sensitivity: zero-volume bars present (literal reading) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5m_k6_down | 4076 | -0.000461135 | 0.000168977 | -2.729 | 0.9968 | 1 | 0.0004201 | -0.0001832 | DEAD | n 4172, mean -0.000448761, t -2.657, Holm 1, DEAD |
| 5m_k6_up | 3801 | 0.00104674 | 0.000171234 | 6.113 | 4.891e-10 | 2.348e-08 | 0.0004257 | 0.001328 | DEAD | n 3897, mean 0.000984773, t 5.741, Holm 2.255e-07, DEAD |

- What masking removes: 5m bars present 842298 against 844093 (1795 bars); eligible 5m origins 814602 against 833932 (**19330** fewer); events per primary cell: down 4076 against 4172 (**96** fewer); up 3801 against 3897 (**96** fewer).

### 6. Dose-response (5m, k = 6, |z| >= 4 with its own fresh clock)
| side | |z| >= 3 mean excess (n) | |z| >= 4 mean excess (n) | verdict (M2's ruling 4: the discard rule only for a positive |z| >= 3 mean) |
|---|---|---|---|
| down | -0.000461135 (4076) | -0.000422554 (1999) | n/a: no positive effect |
| up | 0.00104674 (3801) | 0.00172857 (1832) | keep |

### 7. Stability (event statistic; 90-day calendar blocks from the first eligible 5m origin)

**5m_k6_down**: T = -1.9973, p_stab = 0.977102, B' = 32 of 32 full blocks, partial block 55.8 days.

| block | start | events | t_b | used (>= 30 events) |
|---|---|---|---|---|
| 0 | 2017-08-18 | 31 | -0.378 | True |
| 1 | 2017-11-16 | 108 | 0.064 | True |
| 2 | 2018-02-14 | 156 | -3.277 | True |
| 3 | 2018-05-15 | 140 | -1.654 | True |
| 4 | 2018-08-13 | 121 | -1.030 | True |
| 5 | 2018-11-11 | 99 | -0.934 | True |
| 6 | 2019-02-09 | 112 | 0.017 | True |
| 7 | 2019-05-10 | 125 | -0.502 | True |
| 8 | 2019-08-08 | 108 | -0.238 | True |
| 9 | 2019-11-06 | 132 | -0.574 | True |
| 10 | 2020-02-04 | 121 | -0.764 | True |
| 11 | 2020-05-04 | 120 | -0.556 | True |
| 12 | 2020-08-02 | 123 | -0.094 | True |
| 13 | 2020-10-31 | 143 | 0.629 | True |
| 14 | 2021-01-29 | 117 | 1.529 | True |
| 15 | 2021-04-29 | 123 | -0.795 | True |
| 16 | 2021-07-28 | 121 | -0.200 | True |
| 17 | 2021-10-26 | 126 | -0.375 | True |
| 18 | 2022-01-24 | 127 | -3.520 | True |
| 19 | 2022-04-24 | 137 | -1.034 | True |
| 20 | 2022-07-23 | 146 | -0.884 | True |
| 21 | 2022-10-21 | 141 | -0.733 | True |
| 22 | 2023-01-19 | 139 | 0.929 | True |
| 23 | 2023-04-19 | 137 | -0.854 | True |
| 24 | 2023-07-18 | 122 | 1.460 | True |
| 25 | 2023-10-16 | 116 | 2.538 | True |
| 26 | 2024-01-14 | 127 | 0.733 | True |
| 27 | 2024-04-13 | 154 | 0.054 | True |
| 28 | 2024-07-12 | 143 | -0.267 | True |
| 29 | 2024-10-10 | 117 | 0.915 | True |
| 30 | 2025-01-08 | 144 | -1.386 | True |
| 31 | 2025-04-08 | 132 | -0.116 | True |

**5m_k6_up**: T = 5.9341, p_stab = 1.47737e-09, B' = 31 of 32 full blocks, partial block 55.8 days.

| block | start | events | t_b | used (>= 30 events) |
|---|---|---|---|---|
| 0 | 2017-08-18 | 26 | NaN | False |
| 1 | 2017-11-16 | 90 | 1.488 | True |
| 2 | 2018-02-14 | 99 | 2.284 | True |
| 3 | 2018-05-15 | 113 | 1.038 | True |
| 4 | 2018-08-13 | 126 | 1.482 | True |
| 5 | 2018-11-11 | 124 | 3.068 | True |
| 6 | 2019-02-09 | 102 | 1.930 | True |
| 7 | 2019-05-10 | 108 | 0.988 | True |
| 8 | 2019-08-08 | 111 | 0.923 | True |
| 9 | 2019-11-06 | 110 | -0.959 | True |
| 10 | 2020-02-04 | 104 | 0.745 | True |
| 11 | 2020-05-04 | 143 | -0.203 | True |
| 12 | 2020-08-02 | 118 | 3.429 | True |
| 13 | 2020-10-31 | 108 | 2.544 | True |
| 14 | 2021-01-29 | 91 | 0.765 | True |
| 15 | 2021-04-29 | 122 | 1.209 | True |
| 16 | 2021-07-28 | 100 | 2.238 | True |
| 17 | 2021-10-26 | 132 | -0.273 | True |
| 18 | 2022-01-24 | 143 | 0.968 | True |
| 19 | 2022-04-24 | 147 | 0.480 | True |
| 20 | 2022-07-23 | 118 | -1.251 | True |
| 21 | 2022-10-21 | 116 | 2.261 | True |
| 22 | 2023-01-19 | 132 | 1.249 | True |
| 23 | 2023-04-19 | 136 | 2.526 | True |
| 24 | 2023-07-18 | 127 | -0.254 | True |
| 25 | 2023-10-16 | 127 | 0.130 | True |
| 26 | 2024-01-14 | 125 | 0.825 | True |
| 27 | 2024-04-13 | 110 | 1.771 | True |
| 28 | 2024-07-12 | 124 | 0.883 | True |
| 29 | 2024-10-10 | 135 | 1.648 | True |
| 30 | 2025-01-08 | 113 | -2.035 | True |
| 31 | 2025-04-08 | 131 | 1.144 | True |

Across-candidate Holm (R1; S1, S2 and each Task 3 primary cell are candidates for this pair; the discovery-step Holm is informational, the pass criterion is the Holm over 48):

| step | candidate (family or family:cell) | raw p | Holm across candidates |
|---|---|---|---|
| discovery | S1-ETHUSDT | 0.128192 | 0.384576 |
| discovery | S2-ETHUSDT | 0.463651 | 0.927303 |
| discovery | Task3-ETHUSDT:5m_k6_down | 0.996823 | 0.996823 |
| discovery | Task3-ETHUSDT:5m_k6_up | 4.89129e-10 | 1.95652e-09 |
| stability | S1-ETHUSDT | 0.230385 | 0.691154 |
| stability | S2-ETHUSDT | 0.384308 | 0.768616 |
| stability | Task3-ETHUSDT:5m_k6_down | 0.977102 | 0.977102 |
| stability | Task3-ETHUSDT:5m_k6_up | 1.47737e-09 | 5.90949e-09 |

### 8. By-year and leave-one-year-out (primary cells; years under 120 days are shown, not judged)

**5m_k6_down**: pooled mean excess -0.000461135; any year-driven: **False** (year-driven flags: {2018: False, 2019: False, 2020: False, 2021: False, 2022: False, 2023: False, 2024: False, 2025: False}); every judged year's own sign agrees with the pooled sign: False.

| year | events | days covered (calendar days with an eligible origin) | mean excess | clustered SE | t | judged (>= 120 days) | pooled mean without that year |
|---|---|---|---|---|---|---|---|
| 2017 | 86 | 77 | -0.000904203 | 0.001887 | -0.479 | False | NaN |
| 2018 | 529 | 359 | -0.00172733 | 0.0005205 | -3.319 | True | -0.000272294 |
| 2019 | 467 | 365 | -0.000314351 | 0.0005242 | -0.600 | True | -0.000480129 |
| 2020 | 515 | 366 | -0.000373084 | 0.0005294 | -0.705 | True | -0.000473869 |
| 2021 | 495 | 365 | -8.02983e-05 | 0.0006454 | -0.124 | True | -0.000513778 |
| 2022 | 558 | 365 | -0.00124193 | 0.0004087 | -3.039 | True | -0.000337291 |
| 2023 | 524 | 365 | 0.000417878 | 0.0002687 | 1.555 | True | -0.000590809 |
| 2024 | 551 | 366 | 0.000245332 | 0.000318 | 0.771 | True | -0.000571564 |
| 2025 | 351 | 243 | -0.000485832 | 0.0004712 | -1.031 | True | -0.000458808 |

**5m_k6_up**: pooled mean excess 0.00104674; any year-driven: **False** (year-driven flags: {2018: False, 2019: False, 2020: False, 2021: False, 2022: False, 2023: False, 2024: False, 2025: False}); every judged year's own sign agrees with the pooled sign: False.

| year | events | days covered (calendar days with an eligible origin) | mean excess | clustered SE | t | judged (>= 120 days) | pooled mean without that year |
|---|---|---|---|---|---|---|---|
| 2017 | 71 | 77 | 0.0032587 | 0.002671 | 1.220 | False | NaN |
| 2018 | 457 | 359 | 0.00264919 | 0.000707 | 3.747 | True | 0.000827744 |
| 2019 | 428 | 365 | 0.0011006 | 0.0004564 | 2.412 | True | 0.00103991 |
| 2020 | 493 | 366 | 0.000900489 | 0.0005071 | 1.776 | True | 0.00106854 |
| 2021 | 442 | 365 | 0.00148988 | 0.0005045 | 2.953 | True | 0.000988427 |
| 2022 | 537 | 365 | 0.000368131 | 0.0004068 | 0.905 | True | 0.00115839 |
| 2023 | 530 | 365 | 0.000642353 | 0.0002701 | 2.378 | True | 0.00111226 |
| 2024 | 496 | 366 | 0.000900162 | 0.0003362 | 2.677 | True | 0.00106874 |
| 2025 | 347 | 243 | -6.20485e-05 | 0.0005256 | -0.118 | True | 0.00115813 |

### 9. Robustness columns (descriptive; none is the primary statistic)
| primary cell | (primary) mean excess | (a) one clock per side | (b) mu_6 from |z| < 3 origins | (c) entry one bar late | (d) clustered / naive SE | (f) mean raw return, and minus round-trip costs (information) |
|---|---|---|---|---|---|---|
| 5m_k6_down | -0.000461135 (t -2.73) | n 4721: -0.000424268 (t -2.68) | -0.00045199 (t -2.67) | -0.000442645 (t -2.70) | 0.000169 / 0.0001891 | -0.000448435; minus 0.24%: -0.00284844; minus 0.30%: -0.00344844 |
| 5m_k6_up | 0.00104674 (t 6.11) | n 4700: 0.000859568 (t 5.51) | 0.00105588 (t 6.17) | 0.000748979 (t 4.88) | 0.0001712 / 0.000175 | 0.00105944; minus 0.24%: -0.00134056; minus 0.30%: -0.00194056 |

Kept events by UTC hour of the event bar (24 counts, hour 0 first):
- 5m_k6_down: [233, 186, 140, 107, 77, 80, 100, 108, 135, 137, 126, 138, 179, 253, 296, 252, 251, 185, 171, 199, 188, 180, 202, 155]
- 5m_k6_up: [254, 161, 100, 105, 84, 84, 78, 110, 146, 118, 117, 124, 216, 245, 257, 239, 279, 171, 152, 144, 177, 146, 164, 131]

### 10. Trade lists (pre-tax; one row per kept event with a complete window)
- `t3-trades-ETH_USDT-5m_k6_down.csv`: 4076 rows, sha256 `6ae1bea4bebaa5d86299cc30eb6e593c5aadb15cbb8715da180ad8b9f110bcfd`
- `t3-trades-ETH_USDT-5m_k6_up.csv`: 3801 rows, sha256 `c0bb06304c462ebbcdb51fd40155b60cff6c07f149241bc27c92c79c588d06ab`
Columns: pair, cell, event_bar_time_utc, entry_time_utc (open of bar j+1), exit_time_utc (close of bar j+6), entry_price (O_(j+1)), exit_price (C_(j+6)), gross_log_return, excess.

### 11. Gut-checks
- No look-ahead: z uses returns r_(j-W)..r_(j-1) only (the event bar's own return is excluded), the decision is at the close of bar j and the entry at the open of bar j+1, the clock never looks at later bars (self-tests, exact reproduction of the reference).
- Bug signals: kept events (used) down 4076 / up 3801 (none missing); sides differ by a factor 1.07 (signal above 1.5: no); largest |mean excess| among the 5m cells at k = 12 (60 minutes) 0.001175 (signal above 0.01: no); cells with MDE above M: 0 of 48; cells with a p-value of exactly 0 or 1: 0.
- Microstructure (robustness column c, entry one bar late): 5m_k6_down -0.000442645 (t -2.70) against -0.000461135 on the primary entry; 5m_k6_up 0.000748979 (t 4.88) against 0.00104674 on the primary entry.
- Shared latent state: the excess is measured against one global constant mu_k per timeframe, the SE is clustered by UTC day of the entry bar; no raw mean is quoted as an effect.

## BTC_USDT  (Task3-BTCUSDT)  -- pre-tax

### 1. Provenance
- 5m file `BTC_USDT-5m.feather` sha256 `76649126e52fd303e1a95a6944d37ef018ebfcaf76670bdef0c28b7f334e8af7`; native 15m file `BTC_USDT-15m.feather` sha256 `c7fd4d622a17f7946a447656f072d078fce8a6c7f3aa17169903e9b60e99496c`.
- 5m rows in the file before the cutoff truncation 955676; rows in the discovery frame 844093; regular grid 845808 bars from 2017-08-17 04:00:00+00:00 to 2025-08-31 23:55:00+00:00; **rows after the cutoff in the discovery frame: 0**.
- Missing bars in the grid (primary reading, zero-volume bars masked): **2625**, of which 1715 are absent from the file and **910** are zero-volume placeholder rows masked as missing (M2's ruling 2 of 2026-10-27). Under the literal reading (placeholders present) 1715 bars are missing.
- Derived 15m against the native 15m file (compared on every complete derived bar): primary reading 280707 bars compared, open mismatches 0, close mismatches 0, present in the derived series only 0, present natively only 664; literal reading 281357 bars, open mismatches 202, close mismatches 0, derived only 0, native only 14. (M2's ruling 1: the native file is only a comparison; it was built with the traded-bar rule, which explains the differences.)

### 2. Counts (item 8)
| timeframe | threshold | grid bars | present | missing | eligible origins | first origin | last origin | event bars before de-clustering (down / up) | kept after the shared clock (down / up) | dropped for an incomplete window | used in the statistics (down / up) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5m | |z| >= 3 | 845808 | 843183 | 2625 | 816261 | 2017-08-23T06:20 | 2025-08-31T22:55 | 6563 / 6380 | 3994 / 3719 | 4 gap, 0 cutoff | 3991 / 3718 |
| 5m | |z| >= 4 | 845808 | 843183 | 2625 | 816261 | 2017-08-23T06:20 | 2025-08-31T22:55 | 2972 / 2730 | 2052 / 1847 | 1 gap, 0 cutoff | 2051 / 1847 |
| 15m | |z| >= 3 | 281936 | 280707 | 1229 | 271684 | 2017-08-23T06:30 | 2025-08-31T20:45 | 2692 / 2423 | 1789 / 1587 | 3 gap, 1 cutoff | 1788 / 1584 |
| 15m | |z| >= 4 | 281936 | 280707 | 1229 | 271684 | 2017-08-23T06:30 | 2025-08-31T20:45 | 1251 / 1111 | 962 / 863 | 1 gap, 0 cutoff | 961 / 863 |

- [5m] not an origin: z window 28996, target window (gap inside the frame) 539, cutoff (bar j+12 beyond the frame) 12; flags: none
- [15m] not an origin: z window 9712, target window (gap inside the frame) 528, cutoff (bar j+12 beyond the frame) 12; flags: none
- Stability tiling: t0 = 2017-08-23 06:25:00+00:00 (entry time of the first eligible 5m origin); 32 full 90-day blocks; partial block 50.7 days.

### 3. mu_k table
| k | mu_k 5m (mean R_k over all eligible 5m origins) | mu_k 15m |
|---|---|---|
| 1 | 2.2804e-06 | 9.94935e-06 |
| 2 | 5.7009e-06 | 2.06298e-05 |
| 3 | 9.12115e-06 | 3.1192e-05 |
| 4 | 1.2544e-05 | 4.1801e-05 |
| 5 | 1.59666e-05 | 5.22726e-05 |
| 6 | 1.94111e-05 | 6.25524e-05 |
| 7 | 2.28395e-05 | 7.27379e-05 |
| 8 | 2.62622e-05 | 8.30098e-05 |
| 9 | 2.9689e-05 | 9.31371e-05 |
| 10 | 3.31356e-05 | 0.000103158 |
| 11 | 3.65779e-05 | 0.000113169 |
| 12 | 3.9978e-05 | 0.000123169 |

### 4. The 48 cells (family size 48; Holm and Bonferroni over all 48; primary cells one-sided positive, the other 46 two-sided and descriptive)
| tf | k | side | n | mean raw R_k | mean excess | clustered SE | naive SE | t | p (one-sided positive for the primary, two-sided otherwise) | Holm (48) | Bonferroni (48) | MDE (2.486 x SE) | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5m | 1 | down | 3991 | 6.783e-05 | 6.555e-05 | 8.338e-05 | 8.23e-05 | 0.786 | 0.4318 | 1 | 1 | 0.0002073 |  |
| 5m | 1 | up | 3718 | 0.0001459 | 0.0001436 | 7.493e-05 | 7.667e-05 | 1.917 | 0.05529 | 1 | 1 | 0.0001863 |  |
| 5m | 2 | down | 3991 | -8.074e-05 | -8.644e-05 | 0.0001101 | 0.0001131 | -0.785 | 0.4323 | 1 | 1 | 0.0002736 |  |
| 5m | 2 | up | 3718 | 0.000316 | 0.0003103 | 9.923e-05 | 9.972e-05 | 3.127 | 0.001766 | 0.0459 | 0.08475 | 0.0002467 |  |
| 5m | 3 | down | 3991 | -0.0002924 | -0.0003016 | 0.0001241 | 0.0001243 | -2.429 | 0.01512 | 0.3176 | 0.7259 | 0.0003086 |  |
| 5m | 3 | up | 3718 | 0.0004845 | 0.0004754 | 0.0001063 | 0.0001098 | 4.470 | 7.816e-06 | 0.0003439 | 0.0003752 | 0.0002644 |  |
| 5m | 4 | down | 3991 | -0.0003075 | -0.0003201 | 0.0001362 | 0.0001359 | -2.349 | 0.01881 | 0.3761 | 0.9027 | 0.0003387 |  |
| 5m | 4 | up | 3718 | 0.0005574 | 0.0005448 | 0.0001169 | 0.0001229 | 4.662 | 3.137e-06 | 0.0001474 | 0.0001506 | 0.0002905 |  |
| 5m | 5 | down | 3991 | -0.0002009 | -0.0002169 | 0.0001485 | 0.0001528 | -1.461 | 0.1441 | 1 | 1 | 0.0003691 |  |
| 5m | 5 | up | 3718 | 0.0006113 | 0.0005953 | 0.0001277 | 0.0001353 | 4.662 | 3.136e-06 | 0.0001474 | 0.0001505 | 0.0003175 |  |
| 5m | 6 | down | 3991 | -0.0001437 | -0.0001631 | 0.0001502 | 0.0001584 | -1.086 | 0.8612 | 1 | 1 | 0.0003734 | PRIMARY |
| 5m | 6 | up | 3718 | 0.0006544 | 0.000635 | 0.0001368 | 0.0001458 | 4.641 | 1.738e-06 | 8.34e-05 | 8.34e-05 | 0.0003402 | PRIMARY |
| 5m | 7 | down | 3991 | -1.148e-05 | -3.432e-05 | 0.000147 | 0.0001572 | -0.233 | 0.8154 | 1 | 1 | 0.0003656 |  |
| 5m | 7 | up | 3718 | 0.0006714 | 0.0006486 | 0.0001392 | 0.0001511 | 4.660 | 3.158e-06 | 0.0001474 | 0.0001516 | 0.000346 |  |
| 5m | 8 | down | 3991 | 3.489e-05 | 8.63e-06 | 0.0001565 | 0.0001644 | 0.055 | 0.956 | 1 | 1 | 0.000389 |  |
| 5m | 8 | up | 3718 | 0.0006157 | 0.0005894 | 0.0001454 | 0.0001587 | 4.055 | 5.017e-05 | 0.002057 | 0.002408 | 0.0003614 |  |
| 5m | 9 | down | 3991 | 0.0001277 | 9.8e-05 | 0.0001742 | 0.0001789 | 0.563 | 0.5737 | 1 | 1 | 0.000433 |  |
| 5m | 9 | up | 3718 | 0.0006586 | 0.0006289 | 0.0001558 | 0.0001681 | 4.037 | 5.417e-05 | 0.002167 | 0.0026 | 0.0003873 |  |
| 5m | 10 | down | 3991 | 0.0001988 | 0.0001657 | 0.0001769 | 0.0001834 | 0.937 | 0.349 | 1 | 1 | 0.0004398 |  |
| 5m | 10 | up | 3718 | 0.0006548 | 0.0006217 | 0.0001667 | 0.0001758 | 3.729 | 0.0001924 | 0.006928 | 0.009237 | 0.0004145 |  |
| 5m | 11 | down | 3991 | 0.0002187 | 0.0001821 | 0.0001791 | 0.0001848 | 1.017 | 0.3092 | 1 | 1 | 0.0004452 |  |
| 5m | 11 | up | 3718 | 0.0006565 | 0.00062 | 0.00017 | 0.0001769 | 3.648 | 0.0002644 | 0.009253 | 0.01269 | 0.0004225 |  |
| 5m | 12 | down | 3991 | 0.0002446 | 0.0002046 | 0.0001847 | 0.0001937 | 1.108 | 0.268 | 1 | 1 | 0.0004591 |  |
| 5m | 12 | up | 3718 | 0.0006591 | 0.0006192 | 0.0001721 | 0.0001805 | 3.597 | 0.0003213 | 0.01093 | 0.01542 | 0.0004279 |  |
| 15m | 1 | down | 1788 | -0.0008398 | -0.0008498 | 0.0002011 | 0.0002007 | -4.226 | 2.38e-05 | 0.001023 | 0.001142 | 0.0004999 |  |
| 15m | 1 | up | 1584 | 0.0006021 | 0.0005921 | 0.0001802 | 0.0001819 | 3.286 | 0.001017 | 0.03052 | 0.04883 | 0.000448 |  |
| 15m | 2 | down | 1788 | -0.0008428 | -0.0008635 | 0.0002406 | 0.0002524 | -3.589 | 0.0003315 | 0.01094 | 0.01591 | 0.000598 |  |
| 15m | 2 | up | 1584 | 0.0007764 | 0.0007558 | 0.0002311 | 0.0002307 | 3.270 | 0.001074 | 0.03114 | 0.05154 | 0.0005745 |  |
| 15m | 3 | down | 1788 | -0.0007125 | -0.0007437 | 0.0002577 | 0.000266 | -2.886 | 0.003908 | 0.08988 | 0.1876 | 0.0006407 |  |
| 15m | 3 | up | 1584 | 0.001129 | 0.001098 | 0.0002679 | 0.0002712 | 4.098 | 4.166e-05 | 0.00175 | 0.002 | 0.000666 |  |
| 15m | 4 | down | 1788 | -0.0007589 | -0.0008007 | 0.000321 | 0.0003225 | -2.495 | 0.0126 | 0.2772 | 0.6048 | 0.0007979 |  |
| 15m | 4 | up | 1584 | 0.001181 | 0.001139 | 0.0002914 | 0.0002987 | 3.908 | 9.292e-05 | 0.003624 | 0.00446 | 0.0007243 |  |
| 15m | 5 | down | 1788 | -0.000553 | -0.0006053 | 0.0003291 | 0.0003413 | -1.839 | 0.06589 | 1 | 1 | 0.0008181 |  |
| 15m | 5 | up | 1584 | 0.001157 | 0.001104 | 0.0003109 | 0.0003218 | 3.553 | 0.0003811 | 0.01203 | 0.01829 | 0.0007728 |  |
| 15m | 6 | down | 1788 | -0.0004426 | -0.0005051 | 0.0003386 | 0.0003455 | -1.492 | 0.1357 | 1 | 1 | 0.0008417 |  |
| 15m | 6 | up | 1584 | 0.001296 | 0.001233 | 0.0003192 | 0.0003265 | 3.865 | 0.0001113 | 0.00423 | 0.005343 | 0.0007934 |  |
| 15m | 7 | down | 1788 | -0.000357 | -0.0004297 | 0.0003524 | 0.0003642 | -1.219 | 0.2227 | 1 | 1 | 0.0008761 |  |
| 15m | 7 | up | 1584 | 0.001368 | 0.001295 | 0.0003391 | 0.0003465 | 3.819 | 0.0001342 | 0.004964 | 0.006439 | 0.0008429 |  |
| 15m | 8 | down | 1788 | -0.0002648 | -0.0003478 | 0.000355 | 0.000371 | -0.980 | 0.3272 | 1 | 1 | 0.0008825 |  |
| 15m | 8 | up | 1584 | 0.001369 | 0.001286 | 0.0003615 | 0.0003686 | 3.557 | 0.0003758 | 0.01203 | 0.01804 | 0.0008986 |  |
| 15m | 9 | down | 1788 | -0.0001275 | -0.0002207 | 0.0003621 | 0.0003712 | -0.609 | 0.5422 | 1 | 1 | 0.0009001 |  |
| 15m | 9 | up | 1584 | 0.00131 | 0.001217 | 0.0003773 | 0.0003815 | 3.225 | 0.00126 | 0.03527 | 0.06046 | 0.000938 |  |
| 15m | 10 | down | 1788 | -0.0002331 | -0.0003362 | 0.0003942 | 0.0003937 | -0.853 | 0.3937 | 1 | 1 | 0.0009799 |  |
| 15m | 10 | up | 1584 | 0.001231 | 0.001128 | 0.0003837 | 0.0003922 | 2.940 | 0.003285 | 0.08214 | 0.1577 | 0.000954 |  |
| 15m | 11 | down | 1788 | 1.509e-05 | -9.808e-05 | 0.0004245 | 0.0004171 | -0.231 | 0.8173 | 1 | 1 | 0.001055 |  |
| 15m | 11 | up | 1584 | 0.001278 | 0.001165 | 0.0003973 | 0.0004063 | 2.932 | 0.003367 | 0.08214 | 0.1616 | 0.0009878 |  |
| 15m | 12 | down | 1788 | -0.0003031 | -0.0004263 | 0.0004198 | 0.0004129 | -1.016 | 0.3098 | 1 | 1 | 0.001044 |  |
| 15m | 12 | up | 1584 | 0.001448 | 0.001325 | 0.0004127 | 0.0004199 | 3.209 | 0.00133 | 0.03591 | 0.06383 | 0.001026 |  |

### 5. Classification of the two primary cells (5m, k = 6)
| primary cell | n | mean excess | clustered SE | t | one-sided p | Holm (48) | MDE | mean + 1.645 SE | classification (M = 0.0035) | sensitivity: zero-volume bars present (literal reading) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5m_k6_down | 3991 | -0.000163071 | 0.000150193 | -1.086 | 0.8612 | 1 | 0.0003734 | 8.4e-05 | DEAD | n 4082, mean -0.000108936, t -0.719, Holm 1, DEAD |
| 5m_k6_up | 3718 | 0.000635005 | 0.000136839 | 4.641 | 1.738e-06 | 8.34e-05 | 0.0003402 | 0.0008601 | DEAD | n 3791, mean 0.00064748, t 4.747, Holm 4.946e-05, DEAD |

- What masking removes: 5m bars present 843183 against 844093 (910 bars); eligible 5m origins 816261 against 833932 (**17671** fewer); events per primary cell: down 3991 against 4082 (**91** fewer); up 3718 against 3791 (**73** fewer).

### 6. Dose-response (5m, k = 6, |z| >= 4 with its own fresh clock)
| side | |z| >= 3 mean excess (n) | |z| >= 4 mean excess (n) | verdict (M2's ruling 4: the discard rule only for a positive |z| >= 3 mean) |
|---|---|---|---|
| down | -0.000163071 (3991) | -0.00059621 (2051) | n/a: no positive effect |
| up | 0.000635005 (3718) | 0.000871943 (1847) | keep |

### 7. Stability (event statistic; 90-day calendar blocks from the first eligible 5m origin)

**5m_k6_down**: T = -0.1205, p_stab = 0.547952, B' = 32 of 32 full blocks, partial block 50.7 days.

| block | start | events | t_b | used (>= 30 events) |
|---|---|---|---|---|
| 0 | 2017-08-23 | 34 | 0.394 | True |
| 1 | 2017-11-21 | 117 | -0.583 | True |
| 2 | 2018-02-19 | 144 | -2.298 | True |
| 3 | 2018-05-20 | 119 | -2.409 | True |
| 4 | 2018-08-18 | 131 | 0.426 | True |
| 5 | 2018-11-16 | 124 | -0.497 | True |
| 6 | 2019-02-14 | 115 | 0.694 | True |
| 7 | 2019-05-15 | 121 | -0.831 | True |
| 8 | 2019-08-13 | 89 | -0.070 | True |
| 9 | 2019-11-11 | 126 | -0.224 | True |
| 10 | 2020-02-09 | 124 | -1.002 | True |
| 11 | 2020-05-09 | 121 | -0.158 | True |
| 12 | 2020-08-07 | 115 | -0.038 | True |
| 13 | 2020-11-05 | 130 | 0.497 | True |
| 14 | 2021-02-03 | 103 | 1.480 | True |
| 15 | 2021-05-04 | 136 | -1.019 | True |
| 16 | 2021-08-02 | 109 | 1.143 | True |
| 17 | 2021-10-31 | 97 | -0.778 | True |
| 18 | 2022-01-29 | 122 | -2.776 | True |
| 19 | 2022-04-29 | 149 | 0.213 | True |
| 20 | 2022-07-28 | 143 | -1.131 | True |
| 21 | 2022-10-26 | 131 | 1.577 | True |
| 22 | 2023-01-24 | 131 | 0.931 | True |
| 23 | 2023-04-24 | 136 | 0.561 | True |
| 24 | 2023-07-23 | 126 | 0.625 | True |
| 25 | 2023-10-21 | 122 | 3.885 | True |
| 26 | 2024-01-19 | 135 | 1.241 | True |
| 27 | 2024-04-18 | 148 | -0.388 | True |
| 28 | 2024-07-17 | 142 | -0.419 | True |
| 29 | 2024-10-15 | 127 | 1.141 | True |
| 30 | 2025-01-13 | 129 | -0.841 | True |
| 31 | 2025-04-13 | 129 | -0.027 | True |

**5m_k6_up**: T = 4.4372, p_stab = 4.55733e-06, B' = 32 of 32 full blocks, partial block 50.7 days.

| block | start | events | t_b | used (>= 30 events) |
|---|---|---|---|---|
| 0 | 2017-08-23 | 42 | 0.777 | True |
| 1 | 2017-11-21 | 70 | 1.542 | True |
| 2 | 2018-02-19 | 102 | 2.138 | True |
| 3 | 2018-05-20 | 121 | 1.424 | True |
| 4 | 2018-08-18 | 92 | 1.345 | True |
| 5 | 2018-11-16 | 98 | 1.860 | True |
| 6 | 2019-02-14 | 94 | 0.616 | True |
| 7 | 2019-05-15 | 104 | 3.822 | True |
| 8 | 2019-08-13 | 107 | -0.137 | True |
| 9 | 2019-11-11 | 106 | -0.407 | True |
| 10 | 2020-02-09 | 92 | 0.162 | True |
| 11 | 2020-05-09 | 113 | 1.298 | True |
| 12 | 2020-08-07 | 116 | 1.126 | True |
| 13 | 2020-11-05 | 99 | 2.005 | True |
| 14 | 2021-02-03 | 117 | -0.672 | True |
| 15 | 2021-05-04 | 127 | -0.450 | True |
| 16 | 2021-08-02 | 119 | 2.123 | True |
| 17 | 2021-10-31 | 136 | 0.668 | True |
| 18 | 2022-01-29 | 142 | 0.413 | True |
| 19 | 2022-04-29 | 137 | -2.126 | True |
| 20 | 2022-07-28 | 120 | 0.192 | True |
| 21 | 2022-10-26 | 127 | 0.859 | True |
| 22 | 2023-01-24 | 142 | 1.821 | True |
| 23 | 2023-04-24 | 128 | 1.918 | True |
| 24 | 2023-07-23 | 127 | -0.585 | True |
| 25 | 2023-10-21 | 112 | -0.296 | True |
| 26 | 2024-01-19 | 117 | 1.306 | True |
| 27 | 2024-04-18 | 134 | 0.505 | True |
| 28 | 2024-07-17 | 120 | 1.309 | True |
| 29 | 2024-10-15 | 125 | 0.755 | True |
| 30 | 2025-01-13 | 138 | -0.831 | True |
| 31 | 2025-04-13 | 129 | 0.622 | True |

Across-candidate Holm (R1; S1, S2 and each Task 3 primary cell are candidates for this pair; the discovery-step Holm is informational, the pass criterion is the Holm over 48):

| step | candidate (family or family:cell) | raw p | Holm across candidates |
|---|---|---|---|
| discovery | S1-BTCUSDT | 0.0145107 | 0.043532 |
| discovery | S2-BTCUSDT | 0.158049 | 0.316099 |
| discovery | Task3-BTCUSDT:5m_k6_down | 0.861204 | 0.861204 |
| discovery | Task3-BTCUSDT:5m_k6_up | 1.73759e-06 | 6.95037e-06 |
| stability | S1-BTCUSDT | 0.0554723 | 0.166417 |
| stability | S2-BTCUSDT | 0.0994503 | 0.198901 |
| stability | Task3-BTCUSDT:5m_k6_down | 0.547952 | 0.547952 |
| stability | Task3-BTCUSDT:5m_k6_up | 4.55733e-06 | 1.82293e-05 |

### 8. By-year and leave-one-year-out (primary cells; years under 120 days are shown, not judged)

**5m_k6_down**: pooled mean excess -0.000163071; any year-driven: **True** (year-driven flags: {2018: True, 2019: False, 2020: False, 2021: False, 2022: False, 2023: False, 2024: False, 2025: False}); every judged year's own sign agrees with the pooled sign: False.

| year | events | days covered (calendar days with an eligible origin) | mean excess | clustered SE | t | judged (>= 120 days) | pooled mean without that year |
|---|---|---|---|---|---|---|---|
| 2017 | 102 | 86 | 4.32221e-05 | 0.002101 | 0.021 | False | NaN |
| 2018 | 509 | 359 | -0.00136061 | 0.000509 | -2.673 | True | 1.19852e-05 |
| 2019 | 459 | 365 | -0.000144973 | 0.0004202 | -0.345 | True | -0.000165423 |
| 2020 | 486 | 366 | -0.000429554 | 0.0005156 | -0.833 | True | -0.000126121 |
| 2021 | 463 | 365 | 0.000155308 | 0.0005791 | 0.268 | True | -0.000204854 |
| 2022 | 547 | 365 | -0.000488722 | 0.0002701 | -1.809 | True | -0.000111349 |
| 2023 | 523 | 365 | 0.00077519 | 0.0002439 | 3.179 | True | -0.000304568 |
| 2024 | 557 | 366 | 0.000278745 | 0.0002714 | 1.027 | True | -0.000234734 |
| 2025 | 345 | 243 | -0.000152556 | 0.0002793 | -0.546 | True | -0.000164066 |

**5m_k6_up**: pooled mean excess 0.000635005; any year-driven: **False** (year-driven flags: {2018: False, 2019: False, 2020: False, 2021: False, 2022: False, 2023: False, 2024: False, 2025: False}); every judged year's own sign agrees with the pooled sign: False.

| year | events | days covered (calendar days with an eligible origin) | mean excess | clustered SE | t | judged (>= 120 days) | pooled mean without that year |
|---|---|---|---|---|---|---|---|
| 2017 | 73 | 86 | 0.00264892 | 0.001912 | 1.386 | False | NaN |
| 2018 | 414 | 359 | 0.00216928 | 0.0005149 | 4.213 | True | 0.000442756 |
| 2019 | 396 | 365 | 0.000868851 | 0.0004584 | 1.896 | True | 0.000607129 |
| 2020 | 434 | 366 | 0.000592737 | 0.0003554 | 1.668 | True | 0.000640591 |
| 2021 | 495 | 365 | 0.000677588 | 0.0004596 | 1.474 | True | 0.000628465 |
| 2022 | 529 | 365 | -0.000219147 | 0.0003269 | -0.670 | True | 0.000776694 |
| 2023 | 528 | 365 | 0.000515154 | 0.0002754 | 1.871 | True | 0.000654842 |
| 2024 | 500 | 366 | 0.000487966 | 0.0002964 | 1.646 | True | 0.000657851 |
| 2025 | 349 | 243 | -0.000192778 | 0.0002863 | -0.673 | True | 0.000720756 |

### 9. Robustness columns (descriptive; none is the primary statistic)
| primary cell | (primary) mean excess | (a) one clock per side | (b) mu_6 from |z| < 3 origins | (c) entry one bar late | (d) clustered / naive SE | (f) mean raw return, and minus round-trip costs (information) |
|---|---|---|---|---|---|---|
| 5m_k6_down | -0.000163071 (t -1.09) | n 4704: -0.000121613 (t -0.89) | -0.000156012 (t -1.04) | -0.000115578 (t -0.94) | 0.0001502 / 0.0001584 | -0.00014366; minus 0.24%: -0.00254366; minus 0.30%: -0.00314366 |
| 5m_k6_up | 0.000635005 (t 4.64) | n 4610: 0.000555075 (t 4.15) | 0.000642064 (t 4.69) | 0.000517529 (t 4.24) | 0.0001368 / 0.0001458 | 0.000654416; minus 0.24%: -0.00174558; minus 0.30%: -0.00234558 |

Kept events by UTC hour of the event bar (24 counts, hour 0 first):
- 5m_k6_down: [208, 161, 128, 92, 84, 83, 90, 108, 111, 140, 121, 135, 204, 267, 309, 246, 228, 192, 176, 200, 192, 183, 170, 166]
- 5m_k6_up: [205, 151, 108, 82, 76, 72, 89, 109, 142, 113, 111, 120, 213, 271, 247, 231, 235, 188, 156, 173, 168, 183, 158, 118]

### 10. Trade lists (pre-tax; one row per kept event with a complete window)
- `t3-trades-BTC_USDT-5m_k6_down.csv`: 3991 rows, sha256 `cc3b3abeab1c1be2939ace5e51662e38895c79a98066f2d748255ccf5840571b`
- `t3-trades-BTC_USDT-5m_k6_up.csv`: 3718 rows, sha256 `d1ad1a2cbf6224628ac241f2600d9daf597270c0c0aad29f19e9cb64bbeec823`
Columns: pair, cell, event_bar_time_utc, entry_time_utc (open of bar j+1), exit_time_utc (close of bar j+6), entry_price (O_(j+1)), exit_price (C_(j+6)), gross_log_return, excess.

### 11. Gut-checks
- No look-ahead: z uses returns r_(j-W)..r_(j-1) only (the event bar's own return is excluded), the decision is at the close of bar j and the entry at the open of bar j+1, the clock never looks at later bars (self-tests, exact reproduction of the reference).
- Bug signals: kept events (used) down 3991 / up 3718 (none missing); sides differ by a factor 1.07 (signal above 1.5: no); largest |mean excess| among the 5m cells at k = 12 (60 minutes) 0.0006192 (signal above 0.01: no); cells with MDE above M: 0 of 48; cells with a p-value of exactly 0 or 1: 0.
- Microstructure (robustness column c, entry one bar late): 5m_k6_down -0.000115578 (t -0.94) against -0.000163071 on the primary entry; 5m_k6_up 0.000517529 (t 4.24) against 0.000635005 on the primary entry.
- Shared latent state: the excess is measured against one global constant mu_k per timeframe, the SE is clustered by UTC day of the entry bar; no raw mean is quoted as an effect.


## 12. Interpretation choices (all of them)
1. PRE-TAX. The trade lists exist so that a later after-tax layer can be computed from dated trades.
2. Bars and masking (M2's ruling 2, 2026-10-27, PRIMARY): a 5m bar is present iff open, high, low and close exist and its volume is not zero; a zero-volume placeholder is treated exactly like a missing bar (no return for it or for the next bar, every z window containing it invalid, a target window containing it incomplete, a 15m bin containing it missing, excluded from mu_k). The literal reading (placeholders present) is the labeled sensitivity next to each primary cell.
3. 15m bars (M2's ruling 1): derived from 5m by the order's rule for both pairs (a 15m bin with any of its three 5m bars missing is missing); the native BTC 15m file is only a comparison.
4. z: sample sd (ddof 1) of the W = 288 (5m) / 96 (15m) previous returns, the event bar's own return excluded; eligible iff r_j and all W previous returns are unmasked and sd > 0; event: |z| >= 3 (down z <= -3, up z >= +3); decision at the close of bar j, entry at the open of bar j+1.
5. Clock: one shared clock per timeframe and pair, scanned in time order over the eligible event bars (keep the first, ignore every event bar before j+13); a kept event whose target window later proves incomplete stays on the clock and is dropped from the statistics (counted); one clock per side is a labeled variant.
6. Targets and baseline: R_k = ln(C_(j+k) / O_(j+1)), k = 1..12; an event with any of the bars j+1..j+12 missing is excluded from all k; mu_k = mean of R_k over ALL eligible origins (bars j+1..j+12 present, event bars included), a constant per timeframe; excess e = R_k - mu_k; the |z| < 3 baseline and the one-bar-late entry are labeled variants.
7. Statistics: day-clustered SE (clusters = UTC calendar days of the entry bar), naive SE reported next to it, normal p-values (survival function), MDE = 2.486 x SE; the two primary cells are one-sided positive, the other 46 two-sided; Holm and Bonferroni over all 48 cells of the pair; classification (M = 0.0035): PASS = Holm(48) one-sided p < 0.05 and mean excess >= M; DEAD = mean + 1.645 SE < M and MDE <= M; otherwise INCONCLUSIVE.
8. Dose-response (M2's ruling 4): |z| >= 4 with a fresh shared clock; for a cell whose |z| >= 3 mean excess is positive the |z| >= 3 result is discarded if the |z| >= 4 mean excess is smaller and the |z| >= 4 sample has at least 30 events (fewer: not evaluable, flagged); a cell with a non-positive |z| >= 3 mean prints 'n/a: no positive effect'.
9. Stability: per primary cell, 90-calendar-day blocks tiled from the entry time of the first eligible 5m origin; a block is scored only if its whole window lies inside [t0, entry time of the last eligible 5m origin + 5 minutes]; blocks with fewer than 30 events are listed and excluded; t_b = mean(e) / (sd(e) / sqrt(n_b)); T = sum t_b / sqrt(B'); p_stab = 1 - Phi(T).
10. Registry (M2's ruling 3): family Task3-<PAIR> with two records (discovery, stability); each primary cell is its own across-candidate Holm entry at both steps (raw one-sided p and raw p_stab); the discovery-step Holm is informational. S1's and S2's across-candidate rows changed by design once these records existed.
11. By-year: calendar years of the entry bar; 'days covered' counts calendar days with an eligible origin in that year (an event-day count would undercount sparse events); years under 120 days are shown, not judged; year-driven = dropping the year cuts the pooled mean by more than half or flips its sign (a NaN leave-one-out is never year-driven).
12. Cutoff: every file is truncated at the cutoff before any computation; a bar whose window would extend past the frame's last bar is not an origin (counted separately as 'cutoff').
13. Nothing in this report is a recommendation, and no result is described as a discovery. Freeze and forward test were not run; the holdout is untouched.
