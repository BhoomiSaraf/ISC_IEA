"""Independent Lyapunov spectrum of the frozen ISC map (a=.9,c=.4,d=6,w=10).
Own analytic Jacobian (derived in lyapunov_recomputation.md), checked vs central finite differences.
Usage: python lyapunov_recompute.py [--out results/lyapunov_recomputation.json]
Read-only w.r.t. the repo; uses isc_seq.isc_map.isc_step for the map."""
import sys, json, argparse, pathlib, platform, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from isc_seq.isc_map import isc_step, ISCParams
P = ISCParams()
def jac(x, y, p=P):
    r = 1 + x*x + y*y; t = p.c - p.d/r; tx = 2*p.d*x/r**2; ty = 2*p.d*y/r**2
    ct, st = np.cos(t), np.sin(t)
    X = 1 + p.a*(x*ct - y*st); Y = p.a*(x*st + y*ct)
    dXx = p.a*ct - Y*tx; dXy = -p.a*st - Y*ty
    dYx = p.a*st + (X-1)*tx; dYy = p.a*ct + (X-1)*ty
    fx = 2*p.omega*np.sin(2*p.omega*X); fy = 2*p.omega*np.sin(2*p.omega*Y)
    return np.array([[fx*dXx, fx*dXy],[fy*dYx, fy*dYy]])
def fd_jac(x, y, h=1e-7):
    J = np.zeros((2,2))
    for j,(dx,dy) in enumerate(((h,0),(0,h))):
        a = np.array(isc_step(x+dx,y+dy)); b = np.array(isc_step(x-dx,y-dy)); J[:,j] = (a-b)/(2*h)
    return J
def spectrum(x, y, n_trans, n_iter, p=P):
    for _ in range(n_trans): x, y = isc_step(x, y, p)
    Q = np.eye(2); s = np.zeros(2); cum=[]
    for i in range(n_iter):
        J = jac(x, y, p); x, y = isc_step(x, y, p)
        Q, R = np.linalg.qr(J @ Q); s += np.log(np.abs(np.diag(R)))
        if (i+1) % (n_iter//10) == 0: cum.append((s/(i+1)).tolist())
    return s/n_iter, cum
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(pathlib.Path(__file__).resolve().parents[1]/'results'/'lyapunov_recomputation.json')); a = ap.parse_args()
    rng = np.random.default_rng(20261112)
    res = {'env': {'python': platform.python_version(), 'numpy': np.__version__, 'platform': platform.platform()}, 'params': P.as_dict()}
    # Jacobian verification
    pts = rng.uniform(-1, 1, (1000, 2)); err = max(np.abs(jac(*q) - fd_jac(*q)).max() / max(1, np.abs(jac(*q)).max()) for q in pts)
    res['jacobian_max_rel_err_vs_central_fd'] = err
    # analytic det check: det J = 2w sin(2wX)*2w sin(2wY) * a^2-ish ; compare mean ln|det|
    # (a) legacy-protocol replication: x0=y0=0.1, 1000 transient, 2000 iter
    l, _ = spectrum(0.1, 0.1, 1000, 2000); res['replicate_legacy_protocol_0.1_0.1_T1000_N2000'] = l.tolist()
    # (b) long runs
    l, cum = spectrum(0.1, 0.1, 5000, 2_000_000); res['single_orbit_T5000_N2e6'] = {'lambda': l.tolist(), 'sum': float(l.sum()), 'cumulative_at_deciles': cum}
    # (c) ensemble of random ICs
    L = np.array([spectrum(*rng.uniform(-.9, .9, 2), 5000, 200_000)[0] for _ in range(50)])
    res['ensemble_50IC_T5000_N2e5'] = {'lambda1_mean': L[:,0].mean(), 'lambda1_std': L[:,0].std(), 'lambda2_mean': L[:,1].mean(), 'lambda2_std': L[:,1].std(), 'sum_mean': L.sum(1).mean(), 'sum_std': L.sum(1).std()}
    # (d) transient-length sensitivity
    res['transient_sensitivity_N2e5'] = {str(T): spectrum(0.1, 0.1, T, 200_000)[0].tolist() for T in (0, 100, 1000, 5000, 20000)}
    # (e) iteration-length convergence
    res['iteration_convergence_T5000'] = {str(N): spectrum(0.1, 0.1, 5000, N)[0].tolist() for N in (1000, 10_000, 100_000, 1_000_000)}
    # (f) omega sweep incl 8,10,12 for comparison with legacy CSV
    res['omega_sweep_N5e5'] = {str(w): spectrum(0.1, 0.1, 5000, 500_000, ISCParams(omega=w))[0].tolist() for w in (8.0, 10.0, 12.0)}
    # (g) precision: float32 map rejected as non-comparable; instead compare legacy_step orbit
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True); json.dump(res, open(a.out, 'w'), indent=2, default=float); print(json.dumps(res, indent=1, default=float))
main()
