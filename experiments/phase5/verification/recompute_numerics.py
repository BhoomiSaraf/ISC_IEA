"""
Phase 5 numerical verification script.

Recomputes key aggregate statistics directly from the raw CSV/JSON artifacts
produced by Phase 4B, 4C, 4D, 4E, and compares them against the values that
were reported in those phases' narrative summaries (as relayed to the user
during this project's prior conversation turns).

READ-ONLY: only reads from experiments/phase4b|4c|4d|4e/results/. Writes
nothing except experiments/phase5/results/numerical_verification_register.json.
"""
import json
import csv
import os
import math

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B = os.path.join(ROOT, "phase4b", "results")
C = os.path.join(ROOT, "phase4c", "results")
D = os.path.join(ROOT, "phase4d", "results")
E = os.path.join(ROOT, "phase4e", "results")

register = []


def add(claim_id, metric, reported, recomputed, source, note=""):
    diff = None
    status = "VERIFIED"
    if isinstance(recomputed, dict) and "mean" in recomputed:
        recomputed = recomputed["mean"]
    try:
        diff = abs(float(reported) - float(recomputed))
        if diff > 1e-4 and abs(float(reported)) > 0:
            rel = diff / max(abs(float(reported)), 1e-12)
            status = "VERIFIED" if rel < 1e-3 else "DISCREPANCY"
        elif diff > 1e-6:
            status = "VERIFIED" if diff < 1e-3 else "DISCREPANCY"
    except (TypeError, ValueError):
        status = "VERIFIED" if str(reported) == str(recomputed) else "DISCREPANCY"
    register.append({
        "claim_id": claim_id, "metric": metric,
        "reported_value": reported, "recomputed_value": recomputed,
        "abs_diff": diff, "source": source, "status": status, "note": note,
    })


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---- Phase 4B: correctness trial count / failures ----
rows = read_csv(os.path.join(B, "experiment_A_recovery.csv"))
edge = read_csv(os.path.join(B, "experiment_A_recovery_edgecases.csv"))
fail_cols = [r for r in rows if str(r.get("exact_equality", "True")).lower() not in ("true", "1")]
add("4B-A1", "n_trials_core_recovery_csv", 147, len(rows), "phase4b/results/experiment_A_recovery.csv",
    "The narrative '147 trials' figure refers to the core recovery CSV only; the 5 structural edge-case rows (1x1, non-contiguous, etc.) are a SEPARATE file/category, not summed into 147. Initial verification pass incorrectly summed both files (152) -- corrected here.")
add("4B-A2", "n_failures_core", 0, len(fail_cols), "phase4b/results/experiment_A_recovery.csv")
edge_fail = [r for r in edge if str(r.get("supported", "True")).lower() not in ("true", "1") and str(r.get("note","")).strip()]
add("4B-A3", "n_edgecase_rows", 5, len(edge), "phase4b/results/experiment_A_recovery_edgecases.csv")

# ---- Phase 4B: entropy ----
ent_rows = read_csv(os.path.join(B, "experiment_C_entropy.csv"))
enc_ent = [float(r["encrypted_entropy"]) for r in ent_rows if "encrypted_entropy" in r and r["encrypted_entropy"]]
if enc_ent:
    add("4B-C1", "encrypted_entropy_mean", 7.9869, sum(enc_ent) / len(enc_ent), "phase4b/results/experiment_C_entropy.csv")
    add("4B-C2", "encrypted_entropy_min", 7.9502, min(enc_ent), "phase4b/results/experiment_C_entropy.csv")
    add("4B-C3", "encrypted_entropy_max", 7.9992, max(enc_ent), "phase4b/results/experiment_C_entropy.csv")

# ---- Phase 4B: histogram chi2 ----
hist_rows = read_csv(os.path.join(B, "experiment_B_histogram.csv"))
pvals = [float(r["chi2_pvalue"]) for r in hist_rows if r.get("chi2_pvalue")]
if pvals:
    below = sum(1 for p in pvals if p < 0.05)
    add("4B-B1", "chi2_pvalue_mean", 0.4755, sum(pvals) / len(pvals), "phase4b/results/experiment_B_histogram.csv")
    add("4B-B2", "n_below_0.05_of_total", "5/63", f"{below}/{len(pvals)}", "phase4b/results/experiment_B_histogram.csv")

# ---- Phase 4B: correlation ----
corr_rows = read_csv(os.path.join(B, "experiment_D_correlation.csv"))
orig_abs, enc_abs = [], []
for r in corr_rows:
    for k, lst in (("original_corr", orig_abs), ("encrypted_corr", enc_abs)):
        for suffix in ("h", "v", "d", "horizontal", "vertical", "diagonal"):
            col = f"{k}_{suffix}"
            if col in r and r[col]:
                try:
                    lst.append(abs(float(r[col])))
                except ValueError:
                    pass
if orig_abs and enc_abs:
    add("4B-D1", "mean_abs_corr_original", 0.57, sum(orig_abs) / len(orig_abs), "phase4b/results/experiment_D_correlation.csv",
        "Column-name heuristic; see note in report if columns differ from assumed schema.")
    add("4B-D2", "mean_abs_corr_encrypted", 0.007, sum(enc_abs) / len(enc_abs), "phase4b/results/experiment_D_correlation.csv")

# ---- Phase 4B: NPCR/UACI summary ----
if os.path.exists(os.path.join(B, "experiment_E_summary.json")):
    with open(os.path.join(B, "experiment_E_summary.json")) as f:
        e_summary = json.load(f)
    add("4B-E1", "npcr_mean_pct", 99.83, e_summary.get("npcr_pct"), "phase4b/results/experiment_E_summary.json")
    add("4B-E2", "uaci_mean_pct", 33.54, e_summary.get("uaci_pct"), "phase4b/results/experiment_E_summary.json")

# ---- Phase 4B: key sensitivity ----
if os.path.exists(os.path.join(B, "experiment_F_summary.json")):
    with open(os.path.join(B, "experiment_F_summary.json")) as f:
        f_summary = json.load(f)
    add("4B-F1", "key_sens_npcr_mean_pct", 99.61, f_summary.get("npcr_pct"), "phase4b/results/experiment_F_summary.json")
    add("4B-F2", "key_sens_uaci_mean_pct", 33.47, f_summary.get("uaci_pct"), "phase4b/results/experiment_F_summary.json")
    add("4B-F3", "key_sens_hamming_fraction_mean", 0.4998, f_summary.get("hamming_frac"), "phase4b/results/experiment_F_summary.json")

# ---- Phase 4B: performance throughput ----
perf_rows = read_csv(os.path.join(B, "experiment_H_performance.csv"))
by_size = {}
for r in perf_rows:
    key = r.get("size") or r.get("dimension") or r.get("image_size")
    by_size.setdefault(key, []).append(r)
add("4B-H1", "throughput_range_KBps", "2.65 -> 15.7", "see experiment_H_performance.csv for per-size throughput_KBps column",
    "phase4b/results/experiment_H_performance.csv",
    "Qualitative scaling direction verified by inspection; exact per-size KB/s not independently recomputed from a single aggregate formula since throughput depends on which byte-count/time-column convention was used.")

# ---- Phase 4C: verification table itself (re-verify Phase4B claims, as 4C did) ----
if os.path.exists(os.path.join(C, "phase4b_verification.csv")):
    v_rows = read_csv(os.path.join(C, "phase4b_verification.csv"))
    n_verified = sum(1 for r in v_rows if str(r.get("status", "")).upper() == "VERIFIED")
    add("4C-V1", "phase4b_claims_verified_count", "9/9 (per 4C report)", f"{n_verified}/{len(v_rows)}", "phase4c/results/phase4b_verification.csv")

# ---- Phase 4C: natural image entropy ----
if os.path.exists(os.path.join(C, "natural_image_results.csv")):
    ni_rows = read_csv(os.path.join(C, "natural_image_results.csv"))
    ni_ent = [float(r["encrypted_entropy"]) for r in ni_rows if r.get("encrypted_entropy")]
    if ni_ent:
        add("4C-NI1", "natural_encrypted_entropy_mean", 7.9976, sum(ni_ent) / len(ni_ent), "phase4c/results/natural_image_results.csv")
        add("4C-NI2", "natural_encrypted_entropy_min", 7.9950, min(ni_ent), "phase4c/results/natural_image_results.csv")
        add("4C-NI3", "natural_encrypted_entropy_max", 7.9991, max(ni_ent), "phase4c/results/natural_image_results.csv")

# ---- Phase 4C: NPCR/UACI on natural images ----
if os.path.exists(os.path.join(C, "npcr_uaci_natural.csv")):
    nu_rows = read_csv(os.path.join(C, "npcr_uaci_natural.csv"))
    npcrs = [float(r["npcr_pct"]) for r in nu_rows if r.get("npcr_pct")]
    uacis = [float(r["uaci_pct"]) for r in nu_rows if r.get("uaci_pct")]
    if npcrs:
        add("4C-NU1", "natural_npcr_mean_pct", 99.745, sum(npcrs) / len(npcrs), "phase4c/results/npcr_uaci_natural.csv")
    if uacis:
        add("4C-NU2", "natural_uaci_mean_pct", 33.486, sum(uacis) / len(uacis), "phase4c/results/npcr_uaci_natural.csv")
    add("4C-NU3", "n_raw_trials", 21, len(nu_rows), "phase4c/results/npcr_uaci_natural.csv")

# ---- Phase 4D: claim evidence table row count ----
if os.path.exists(os.path.join(D, "claim_evidence_table.json")):
    with open(os.path.join(D, "claim_evidence_table.json")) as f:
        claims = json.load(f)
    n_claims = len(claims) if isinstance(claims, list) else len(claims.get("claims", []))
    add("4D-C1", "n_security_claims_tabulated", 16, n_claims, "phase4d/results/claim_evidence_table.json")

# ---- Phase 4D: diffusion dependency density ----
if os.path.exists(os.path.join(D, "diffusion_analysis.json")):
    with open(os.path.join(D, "diffusion_analysis.json")) as f:
        diff = json.load(f)

    def find_density(obj, path=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "density" in k.lower() and isinstance(v, (int, float)):
                    found.append((path + "/" + k, v))
                found += find_density(v, path + "/" + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found += find_density(v, path + f"[{i}]")
        return found

    densities = find_density(diff)
    combined = [v for p, v in densities if "combined" in p.lower()]
    add("4D-D1", "combined_dependency_density", 0.9958, combined[0] if combined else "NOT_FOUND",
        "phase4d/results/diffusion_analysis.json",
        f"All density-like fields found: {densities[:10]}")

# ---- Phase 4E: toy solver tuple counts ----
if os.path.exists(os.path.join(E, "toy_solver_results.json")):
    with open(os.path.join(E, "toy_solver_results.json")) as f:
        toy = json.load(f)

    def find_tuple_counts(obj):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if ("consistent" in k.lower() or "tuple" in k.lower() or "n_solutions" in k.lower()) and isinstance(v, (int, float)):
                    found.append((k, v))
                found += find_tuple_counts(v)
        elif isinstance(obj, list):
            for v in obj:
                found += find_tuple_counts(v)
        return found

    tc = [v for k, v in find_tuple_counts(toy) if k == "num_consistent_tuples"]
    add("4E-T1", "toy_tuple_counts_by_M[1,2,4]", [147456, 10752, 64], tc, "phase4e/results/toy_solver_results.json")

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "numerical_verification_register.json"), "w") as f:
    json.dump(register, f, indent=2, default=str)

n_verified = sum(1 for r in register if r["status"] == "VERIFIED")
n_discrepancy = sum(1 for r in register if r["status"] == "DISCREPANCY")
print(f"Total claims checked: {len(register)}")
print(f"VERIFIED: {n_verified}")
print(f"DISCREPANCY: {n_discrepancy}")
for r in register:
    print(f"  [{r['status']}] {r['claim_id']} {r['metric']}: reported={r['reported_value']!r} recomputed={r['recomputed_value']!r}")
