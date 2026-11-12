import os
import csv
import time
import numpy as np
import matplotlib.pyplot as plt

# ===========================================================
# SETUP & CONFIGURATION
# ===========================================================

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.join(base_dir, 'plots', 'final_validation')
os.makedirs(out_dir, exist_ok=True)

# Original ISC Parameters
DEFAULT_PARAMS = {'a': 0.9, 'c': 0.4, 'd': 6.0, 'omega': 10.0}
x0, y0 = 0.1, 0.1

def log(msg):
    print(f"[*] {msg}")

# ===========================================================
# ISC MAP DEFINITION (UNMODIFIED)
# ===========================================================

def sine_chebyshev_ikeda_step(x, y, a=0.9, c=0.4, d=6.0, omega=10.0):
    tn = c - d / (1.0 + x**2 + y**2)
    Xn = 1.0 + a * (x * np.cos(tn) - y * np.sin(tn))
    Yn = a * (x * np.sin(tn) + y * np.cos(tn))
    xn = 2.0 * (np.sin(omega * Xn)**2) - 1.0
    yn = 2.0 * (np.sin(omega * Yn)**2) - 1.0
    return xn, yn

def generate_trajectory(n_iter, n_transient=5000, dtype=np.float64):
    x, y = dtype(x0), dtype(y0)
    for _ in range(n_transient):
        x, y = sine_chebyshev_ikeda_step(x, y, **DEFAULT_PARAMS)
        x, y = dtype(x), dtype(y)
        
    xs = np.zeros(n_iter, dtype=dtype)
    ys = np.zeros(n_iter, dtype=dtype)
    for i in range(n_iter):
        x, y = sine_chebyshev_ikeda_step(x, y, **DEFAULT_PARAMS)
        x, y = dtype(x), dtype(y)
        xs[i], ys[i] = x, y
    return xs, ys

# ===========================================================
# 1. AUTOCORRELATION TEST
# ===========================================================

def test_autocorrelation(xs, ys, max_lag=100):
    log("Running Autocorrelation Test...")
    
    def acf(seq):
        seq = seq - np.mean(seq)
        corr = np.correlate(seq, seq, mode='full')
        corr = corr[len(corr)//2:]
        return corr / corr[0]
        
    acf_x = acf(xs)[:max_lag]
    acf_y = acf(ys)[:max_lag]
    
    plt.figure(figsize=(10, 5), facecolor='white')
    plt.stem(range(max_lag), acf_x, linefmt='b-', markerfmt='b.', basefmt='k-')
    plt.title('Autocorrelation of $x_n$ (ISC Map)', fontsize=14)
    plt.xlabel('Lag', fontsize=12)
    plt.ylabel('Autocorrelation', fontsize=12)
    plt.xlim(0, max_lag)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '1_autocorrelation_x.png'), dpi=200)
    plt.close()
    
    return acf_x[1], acf_y[1]

# ===========================================================
# 2. 0-1 TEST FOR CHAOS
# ===========================================================

def zero_one_test_for_chaos(phi, c_values=100):
    log("Running 0-1 Test for Chaos...")
    N = len(phi)
    t = np.arange(1, N + 1)
    
    K_c = []
    
    # Generate random c values between 0 and pi
    np.random.seed(42) # For reproducibility
    cs = np.random.uniform(0.1, np.pi - 0.1, c_values)
    
    for c in cs:
        p_c = np.cumsum(phi * np.cos(t * c))
        s_c = np.cumsum(phi * np.sin(t * c))
        
        # Mean square displacement
        n_max = N // 10
        M_c = np.zeros(n_max)
        
        for n in range(1, n_max + 1):
            diff_p = p_c[n:] - p_c[:-n]
            diff_s = s_c[n:] - s_c[:-n]
            M_c[n-1] = np.mean(diff_p**2 + diff_s**2)
            
        # Asymptotic growth rate K
        # Linear regression of log(M_c(n)) vs log(n)
        n_vals = np.arange(1, n_max + 1)
        # Avoid log(0)
        M_c = np.maximum(M_c, 1e-15)
        
        # Pearson correlation method (K = corr(n, M_c))
        V_c = M_c - np.mean(phi)**2 * (1 - np.cos(n_vals * c)) / (1 - np.cos(c))
        
        corr = np.corrcoef(n_vals, V_c)[0, 1]
        if not np.isnan(corr):
            K_c.append(corr)
        
    K_median = np.median(K_c) if K_c else 0.0
    
    # Plot p-s plane for one value of c to visualize
    c_sample = cs[0]
    p_c = np.cumsum(phi * np.cos(t * c_sample))
    s_c = np.cumsum(phi * np.sin(t * c_sample))
    
    plt.figure(figsize=(8, 8), facecolor='white')
    plt.plot(p_c, s_c, linewidth=0.5, alpha=0.7, color='purple')
    plt.title('0-1 Test: p-s Translation Dynamics (Brownian-like = Chaos)', fontsize=14)
    plt.xlabel('p_c(n)', fontsize=12)
    plt.ylabel('s_c(n)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '2_zero_one_test_ps_plane.png'), dpi=200)
    plt.close()
    
    return K_median

# ===========================================================
# 3. APPROXIMATE ENTROPY (ApEn)
# ===========================================================

def approximate_entropy(U, m=2, r=0.2):
    log(f"Running Approximate Entropy Test (N={len(U)}, m={m}, r={r})...")
    
    def _maxdist(x_i, x_j):
        return np.max(np.abs(np.array(x_i) - np.array(x_j)))
        
    def _phi(m):
        N = len(U)
        x = [U[i:i + m] for i in range(N - m + 1)]
        C = []
        for x_i in x:
            count = sum(1 for x_j in x if _maxdist(x_i, x_j) <= r)
            C.append(count / (N - m + 1.0))
        return np.sum(np.log(C)) / (N - m + 1.0)
        
    return np.abs(_phi(m + 1) - _phi(m))

# ===========================================================
# 4. INITIAL CONDITION SENSITIVITY (BUTTERFLY EFFECT)
# ===========================================================

def test_sensitivity(delta=1e-10, n_iter=100):
    log("Running Sensitivity to Initial Conditions Test...")
    
    # Trajectory 1
    x1, y1 = x0, y0
    
    # Trajectory 2
    x2, y2 = x0 + delta, y0 + delta
    
    distances = []
    
    for _ in range(n_iter):
        distances.append(np.sqrt((x1 - x2)**2 + (y1 - y2)**2))
        x1, y1 = sine_chebyshev_ikeda_step(x1, y1, **DEFAULT_PARAMS)
        x2, y2 = sine_chebyshev_ikeda_step(x2, y2, **DEFAULT_PARAMS)
        
    plt.figure(figsize=(10, 5), facecolor='white')
    plt.plot(range(n_iter), distances, 'r.-')
    plt.yscale('log')
    plt.title(f'Sensitivity to Initial Conditions ($\Delta = {delta}$)', fontsize=14)
    plt.xlabel('Iteration (n)', fontsize=12)
    plt.ylabel('Euclidean Distance (log scale)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '3_sensitivity_divergence.png'), dpi=200)
    plt.close()
    
    # Return iterations required to diverge by more than 1.0
    diverge_point = -1
    for i, d in enumerate(distances):
        if d > 1.0:
            diverge_point = i
            break
    return diverge_point

# ===========================================================
# 5. FINITE PRECISION & CYCLE LENGTH (FLOAT32 VS FLOAT64)
# ===========================================================

def test_finite_precision(max_iter=1000000):
    log("Running Finite Precision (Cycle Finding) Test...")
    
    def find_cycle(dtype):
        # Floyd's Tortoise and Hare algorithm
        x_t, y_t = dtype(x0), dtype(y0)
        x_h, y_h = dtype(x0), dtype(y0)
        
        # Advance hare by 1 step
        x_h, y_h = sine_chebyshev_ikeda_step(x_h, y_h, **DEFAULT_PARAMS)
        x_h, y_h = dtype(x_h), dtype(y_h)
        
        for i in range(1, max_iter):
            if x_t == x_h and y_t == y_h:
                return i # Cycle detected
                
            # Tortoise moves 1
            x_t, y_t = sine_chebyshev_ikeda_step(x_t, y_t, **DEFAULT_PARAMS)
            x_t, y_t = dtype(x_t), dtype(y_t)
            
            # Hare moves 2
            x_h, y_h = sine_chebyshev_ikeda_step(x_h, y_h, **DEFAULT_PARAMS)
            x_h, y_h = dtype(x_h), dtype(y_h)
            x_h, y_h = sine_chebyshev_ikeda_step(x_h, y_h, **DEFAULT_PARAMS)
            x_h, y_h = dtype(x_h), dtype(y_h)
            
        return -1 # No cycle detected
        
    cycle_f32 = find_cycle(np.float32)
    cycle_f64 = find_cycle(np.float64)
    
    return cycle_f32, cycle_f64

# ===========================================================
# 6. NIST SP 800-22
# ===========================================================

def run_nist_validation():
    log("Running NIST SP 800-22 Test (1,000,000 bits)...")
    
    xs, ys = generate_trajectory(500000, n_transient=5000)
    
    seq_x = (xs > 0).astype(np.int8)
    seq_y = (ys > 0).astype(np.int8)
    binary_seq = np.concatenate([seq_x, seq_y])
    
    try:
        from nistrng import check_eligibility_all_battery, run_all_battery, SP800_22R1A_BATTERY
    except ImportError:
        log("nistrng package not installed. Skipping NIST tests.")
        return -1, -1
        
    eligible_battery = check_eligibility_all_battery(binary_seq, SP800_22R1A_BATTERY)
    
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = run_all_battery(binary_seq, eligible_battery, False)
        
    csv_path = os.path.join(out_dir, "4_nist_validation_results.csv")
    passed_tests = 0
    total_tests = len(results)
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Test Name", "Passed", "Time_ms"])
        for result, elapsed_time in results:
            if result.passed: passed_tests += 1
            writer.writerow([result.name, result.passed, elapsed_time])
            
    return passed_tests, total_tests

# ===========================================================
# MAIN EXECUTION
# ===========================================================

def main():
    print("\n" + "="*70)
    print("FINAL VALIDATION SUITE: SINE-CHEBYSHEV-IKEDA MAP")
    print("="*70 + "\n")
    
    results = {}
    start_time = time.time()
    
    log("Generating base trajectory (N=100,000)...")
    xs_full, ys_full = generate_trajectory(100000)
    
    lag_1_x, lag_1_y = test_autocorrelation(xs_full, ys_full)
    results['ACF_Lag1_X'] = lag_1_x
    results['ACF_Lag1_Y'] = lag_1_y
    
    k_median = zero_one_test_for_chaos(xs_full[:10000])
    results['Zero_One_K'] = k_median
    
    r_val = 0.2 * np.std(xs_full[:1000])
    apen_x = approximate_entropy(xs_full[:1000], m=2, r=r_val)
    results['ApEn_X'] = apen_x
    
    diverge_iter = test_sensitivity()
    results['Divergence_Iter_1e-10'] = diverge_iter
    
    cycle_f32, cycle_f64 = test_finite_precision(max_iter=1000000)
    results['Cycle_Length_Float32'] = "No Cycle (<1M)" if cycle_f32 == -1 else cycle_f32
    results['Cycle_Length_Float64'] = "No Cycle (<1M)" if cycle_f64 == -1 else cycle_f64
    
    nist_pass, nist_tot = run_nist_validation()
    results['NIST_Score'] = f"{nist_pass}/{nist_tot}"
    
    report_path = os.path.join(out_dir, 'validation_report.csv')
    with open(report_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value", "Status"])
        for k, v in results.items():
            status = "OK"
            if k == 'Zero_One_K' and v < 0.9: status = "WARN (Not ~1)"
            if k == 'Divergence_Iter_1e-10' and v == -1: status = "FAIL (No divergence)"
            if k == 'Cycle_Length_Float64' and v != "No Cycle (<1M)": status = "FAIL (Cycle detected)"
            writer.writerow([k, v, status])
            
    exec_time = time.time() - start_time
    print("\n" + "="*70)
    print(f"VALIDATION COMPLETE in {exec_time:.2f} seconds.")
    print(f"Results saved to: {out_dir}")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
