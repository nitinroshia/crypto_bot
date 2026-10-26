From: D2 | To: M2 | Re: Work Order 1.7 step 0 and step 1: three questions with defaults, and the readings in formula_t3.py | Date: 2026-10-26

Nothing here blocks me. Each question has a default that I follow unless you rule otherwise; I will run the alternative as a labeled variant where it is cheap.

## Questions (research design)

1. **15m bars and the native file.** Section 1.1 says to check "if ETH has a native 15m file". The owner's store has NO ETH 15m file; it has `BTC_USDT-15m.feather`, which was itself built from the 5m file by
   `build_derived_raw.py` (work order 1.4) with the traded rule: the open comes from the first TRADED 5m bar, zero-trade placeholder bars are skipped. The order's rule (a 15m bar with any of its three 5m bars missing is missing, open = first 5m open)
   differs from that in the presence of placeholders. **Default:** the order's rule for both pairs (15m derived from 5m by `derive_15m`); the BTC file is compared with the derived series on every complete bar and the mismatches are reported (expect
   few or none); the derived series is used.
2. **Zero-trade placeholder 5m bars.** The raw store can contain 5m bars with zero volume (flat placeholders). Section 1.1 says a bar is present if it has open, high, low and close. **Default:** the literal reading, placeholders count as present; the facts
   report the number of zero-volume bars per pair, so you can see whether it matters; a flat placeholder gives a zero return and enters the z windows. If you would rather mask them, say so and I will run that as the primary instead.
3. **Registry and the across-candidate Holm.** Each Task 3 family has two primary cells but the registry holds one p per family. **Default:** the discovery record keeps all 48 cells with the two primary ids; for the across-candidate Holm (R1) each primary cell is a
   separate entry (`Task3-ETHUSDT:5m_k6_down`, `...:5m_k6_up`) at BOTH the discovery step (raw one-sided p) and the stability step (raw p_stab), via one backward-compatible extension of `registry.holm_at_step` (records without an `entries` field behave exactly as
   now; the S1 and S2 reports are re-run as the regression check). The order names the stability step only; applying the same rule at discovery is the stricter reading.

## Readings in `formula_t3.py` (all will be listed in the report)

- Eligible = r_j and the W previous returns unmasked and sd_j > 0 (the order's "valid z window"); origins = eligible bars whose bars j+1..j+12 are present inside the truncated frame; the cutoff is a frame truncation, so "beyond the cutoff" and "not present" are counted separately.
- Classification uses the Holm over all 48 cells of the pair (the primary cells' one-sided p inside it). The reference's Holm over the two primary cells is only a stand-in and is used only in the exact-reproduction rows.
- Stability blocks: a block is scored iff t0 + 90(b+1) days <= (entry time of the last eligible 5m origin + 5 minutes), t0 = entry time of the first eligible 5m origin; on a gap-free series this equals the reference's index rule exactly (verified).
- Dose-response "smaller" is the signed comparison of mean excess (down and up cells separately, both are positive-direction cells).
- The one-bar-late column uses the same origin set for its own baseline mean; robustness (b) uses the origins with |z| < 3 (z defined) for mu_6.
- Day clusters = the UTC calendar day of the entry bar's label; p-values use the normal survival function.
- Acceptance: `--full` runs 200 null / 100 edge paths through production code with the reference generators; a null row above 7% triggers the automatic 1,000-path confirmation. The reduced self-test (60 / 30 paths) uses a 10% band (smoke test only).

Step 1 result for your records (sandbox, not yet the owner's machine): the production code reproduces `1.7-task3_reference.py --one-series 2026` exactly (kept events 5244 / 5506, mu_6 -0.0000018532, all differences below 5e-14 relative); the reduced acceptance rows
read as the reference does (+0.50%: pass 100%, stability 100%; +0.10%: significant 100%, dead 100%; +0.35% information: pass 7%, dead 37%, inconclusive 57% against the reference's 10/35/55).
