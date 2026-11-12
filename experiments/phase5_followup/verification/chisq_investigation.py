"""Phase 3B pooled chi-square anomaly: regeneration + diagnostics. Does NOT modify frozen Phase 3B outputs.
Usage: python chisq_investigation.py [--streams sbox,bwd] [--out results/phase3b_chisquare_investigation.json]
Regenerates pooled streams via experiments/phase3b/common.py (same seeds, burn_in=1024, 125000 B/lane),
compares chi2/p to experiments/phase3b/raw/stage_a_stream_metrics.csv, then runs diagnostics."""
import sys, json, csv, argparse, pathlib, time, platform
import numpy as np
from scipy import stats
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments' / 'phase3b'))
import common
ap = argparse.ArgumentParser(); ap.add_argument('--streams', default='sbox,bwd'); ap.add_argument('--out', default=str(ROOT/'experiments/phase5_followup/results/phase3b_chisquare_investigation.json')); a = ap.parse_args()
stored = {(int(r['extraction']), r['seed'], r['stream']): r for r in csv.DictReader(open(ROOT/'experiments/phase3b/raw/stage_a_stream_metrics.csv'))}
def chi(counts, n): e = n/256; c = float(((counts-e)**2/e).sum()); return c, float(stats.chi2.sf(c, 255))
rng = np.random.default_rng(7)
out = {'env': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': stats.__name__}, 'runs': {}}
# null calibration: iid uniform 8M bytes
null = [chi(np.bincount(rng.integers(0,256,8_000_000,dtype=np.uint8), minlength=256).astype(float), 8_000_000)[0] for _ in range(100)]
out['iid_null_chi2_mean_sd_100reps'] = [float(np.mean(null)), float(np.std(null))]
for ext in (1, 2):
  for seed in ('seedA','seedB','seedC'):
    t0 = time.time()
    data = common.generate(seed, ext, 1024, common.BYTES_PER_LANE_PRIMARY, streams_subset=a.streams.split(','))
    for g in a.streams.split(','):
        arr = np.frombuffer(data[g], dtype=np.uint8); n = arr.size
        cnt = np.bincount(arr, minlength=256).astype(float); c, p = chi(cnt, n); s = stored[(ext, seed, g)]
        r = {'n': n, 'chi2': c, 'p': p, 'stored_chi2': float(s['chi2']), 'stored_p': float(s['chi2_p']), 'chi2_matches_stored': abs(c-float(s['chi2']))<1e-6}
        # per-lane chi2 sums and per-lane mean
        lanes = arr.reshape(-1, 64, 2).transpose(1,0,2).reshape(64,-1)
        lc = [chi(np.bincount(l, minlength=256).astype(float), l.size)[0] for l in lanes]
        r['per_lane_chi2_mean'] = float(np.mean(lc)); r['per_lane_chi2_sd'] = float(np.std(lc)); r['expected_lane_mean_sd_if_iid'] = [255.0, float(np.sqrt(510))]
        # effect size: noncentrality estimate and relative bin deviation
        r['excess_chi2_over_df'] = c-255; r['cohen_w'] = float(np.sqrt(max(c-255,0)/n))
        dev = cnt/(n/256)-1; r['max_abs_rel_bin_dev'] = float(np.abs(dev).max()); r['rel_dev_sd'] = float(dev.std()); r['iid_expected_rel_dev_sd'] = float(np.sqrt(256/n))
        # split-half replication: is the pattern persistent? correlate residuals of halves
        h1 = np.bincount(arr[:n//2], minlength=256).astype(float); h2 = np.bincount(arr[n//2:], minlength=256).astype(float)
        r['split_half_resid_corr'] = float(np.corrcoef(h1-h1.mean(), h2-h2.mean())[0,1]); r['split_half_chi2'] = [chi(h1,n//2)[0], chi(h2,n//2)[0]]
        # even/odd position (x vs y output) and across 4 equal segments
        for nm, sub in (('x_pos', arr[0::2]), ('y_pos', arr[1::2])): r[f'chi2_{nm}'] = chi(np.bincount(sub, minlength=256).astype(float), sub.size)[0]
        # lane-wise residual agreement: mean pairwise correlation of lane residuals (shared bias => positive)
        L = np.array([np.bincount(l, minlength=256) - l.size/256 for l in lanes], float); C = np.corrcoef(L); r['mean_pairwise_lane_resid_corr'] = float((C.sum()-64)/(64*63))
        # bit marginals: z-score of P(bit=1)
        bits = np.unpackbits(arr[:,None], axis=1); pz = (bits.mean(0)-0.5)/np.sqrt(0.25/n); r['bit_marginal_z_msb_to_lsb'] = pz.tolist()
        # nibble (high/low) chi2
        r['chi2_high_nibble_df15'] = [float(((np.bincount(arr>>4,minlength=16)-n/16)**2/(n/16)).sum())]; r['chi2_low_nibble_df15'] = [float(((np.bincount(arr&15,minlength=16)-n/16)**2/(n/16)).sum())]
        # dependence: lag-1 pair chi2 on 16x16 nibble-pairs (df 255 under independence+uniform), and byte-count variance inflation via block bootstrap of counts
        pairs = (arr[:-1].astype(np.int32)>>4)*16 + (arr[1:]>>4); pc = np.bincount(pairs, minlength=256).astype(float); r['lag1_highnibble_pair_chi2_df255'] = chi(pc, n-1)[0]
        # block-count variance ratio: variance of per-block bin counts vs multinomial expectation (>1 => positive dependence/clustering)
        blk = arr[:(n//10_000)*10_000].reshape(-1, 10_000); B = np.array([np.bincount(b, minlength=256) for b in blk], float); r['block10k_var_ratio_mean_over_bins'] = float((B.var(0, ddof=1)/(10_000/256*(1-1/256))).mean())
        out['runs'][f'ext{ext}_{seed}_{g}'] = r; print(f'ext{ext} {seed} {g}: chi2={c:.1f} p={p:.2e} stored={s["chi2"][:7]} match={r["chi2_matches_stored"]} laneChi2mean={r["per_lane_chi2_mean"]:.1f} w={r["cohen_w"]:.4f} halfcorr={r["split_half_resid_corr"]:.2f} laneCorr={r["mean_pairwise_lane_resid_corr"]:.3f} varratio={r["block10k_var_ratio_mean_over_bins"]:.3f}', flush=True)
    print(f'  ({time.time()-t0:.0f}s)', flush=True)
pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(a.out,'w'), indent=1)
