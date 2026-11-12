import os
import csv
import numpy as np
import matplotlib.pyplot as plt

# ===========================================================
# Setup
# ===========================================================

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plots_dir = os.path.join(base_dir, 'plots')
os.makedirs(plots_dir, exist_ok=True)

DEFAULT_PARAMS = {'a': 0.9, 'c': 0.4, 'd': 6.0, 'omega': 10.0}

# ===========================================================
# Map & Jacobian Definition: Sine-Chebyshev-Ikeda
# ===========================================================

def sine_chebyshev_ikeda_step(x, y, a, c, d, omega):
    tn = c - d / (1.0 + x**2 + y**2)
    Xn = 1.0 + a * (x * np.cos(tn) - y * np.sin(tn))
    Yn = a * (x * np.sin(tn) + y * np.cos(tn))
    
    xn = 2.0 * (np.sin(omega * Xn)**2) - 1.0
    yn = 2.0 * (np.sin(omega * Yn)**2) - 1.0
    return xn, yn

def sine_chebyshev_ikeda_jac(x, y, a, c, d, omega):
    R2 = x**2 + y**2
    denom = (1.0 + R2)**2
    dtn_dx = 2.0 * d * x / denom
    dtn_dy = 2.0 * d * y / denom

    tn = c - d / (1.0 + R2)
    cos_t = np.cos(tn)
    sin_t = np.sin(tn)

    un = x * cos_t - y * sin_t
    vn = x * sin_t + y * cos_t

    J_ikeda = np.zeros((2, 2))
    J_ikeda[0, 0] = a * (cos_t - vn * dtn_dx)
    J_ikeda[0, 1] = a * (-sin_t - vn * dtn_dy)
    J_ikeda[1, 0] = a * (sin_t + un * dtn_dx)
    J_ikeda[1, 1] = a * (cos_t + un * dtn_dy)
    
    Xn = 1.0 + a * (x * cos_t - y * sin_t)
    Yn = a * (x * sin_t + y * cos_t)
    
    dx_dX = 4.0 * omega * np.sin(omega * Xn) * np.cos(omega * Xn)
    dy_dY = 4.0 * omega * np.sin(omega * Yn) * np.cos(omega * Yn)
    
    diag_wrap = np.diag([dx_dX, dy_dY])
    
    return diag_wrap @ J_ikeda

# ===========================================================
# Simulation Routines
# ===========================================================

def compute_lyapunov(params, x0=0.1, y0=0.1, n_iter=2000, n_transient=1000):
    x, y = x0, y0
    for _ in range(n_transient):
        x, y = sine_chebyshev_ikeda_step(x, y, **params)
        
    Q = np.eye(2)
    sum_log_R = np.zeros(2)
    
    for _ in range(n_iter):
        J = sine_chebyshev_ikeda_jac(x, y, **params)
        x, y = sine_chebyshev_ikeda_step(x, y, **params)
        
        B = J @ Q
        Q, R = np.linalg.qr(B)
        
        sign = np.diag(np.sign(np.diag(R)))
        Q = Q @ sign
        R = sign @ R
        
        diag_R = np.abs(np.diag(R))
        if np.any(diag_R == 0):
            return np.array([np.nan, np.nan])
            
        sum_log_R += np.log(diag_R)
        
    return sum_log_R / n_iter

# ===========================================================
# Plots
# ===========================================================

def plot_trajectory():
    print("Generating Trajectory Graph (Phase Portrait)...")
    n_transient = 5000
    n_iter = 200000
    x, y = 0.1, 0.1
    
    for _ in range(n_transient):
        x, y = sine_chebyshev_ikeda_step(x, y, **DEFAULT_PARAMS)
        
    xs, ys = np.zeros(n_iter), np.zeros(n_iter)
    for i in range(n_iter):
        x, y = sine_chebyshev_ikeda_step(x, y, **DEFAULT_PARAMS)
        xs[i], ys[i] = x, y
        
    plt.figure(figsize=(8, 8), facecolor='white')
    plt.scatter(xs, ys, s=0.1, c='indigo', marker='.', alpha=0.5)
    plt.title('High-Resolution Phase Portrait: Sine-Chebyshev-Ikeda (ω=10.0)', fontsize=14)
    plt.xlabel('$x_i$', fontsize=12)
    plt.ylabel('$y_i$', fontsize=12)
    plt.axis([-1.05, 1.05, -1.05, 1.05])
    plt.grid(True, color='gray', alpha=0.15)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '1_trajectory_graph.png'), dpi=300)
    plt.close()
    
    return xs, ys

def plot_bifurcation():
    print("Generating Bifurcation Diagram...")
    param_range = np.linspace(0, 15, 2000)
    n_transient = 2000
    n_plot = 300
    
    all_p = []
    all_x = []
    
    for p in param_range:
        params = DEFAULT_PARAMS.copy()
        params['omega'] = p
        
        x, y = 0.1, 0.1
        for _ in range(n_transient):
            x, y = sine_chebyshev_ikeda_step(x, y, **params)
            
        for _ in range(n_plot):
            x, y = sine_chebyshev_ikeda_step(x, y, **params)
            all_p.append(p)
            all_x.append(x)
            
    plt.figure(figsize=(12, 6), facecolor='white')
    plt.scatter(all_p, all_x, s=0.1, c='black', marker='.', alpha=0.5)
    plt.title('High-Resolution Bifurcation Diagram: Sine-Chebyshev-Ikeda', fontsize=14)
    plt.xlabel('$\omega$', fontsize=12)
    plt.ylabel('$x_i$', fontsize=12)
    plt.xlim(0, 15)
    plt.grid(True, color='gray', alpha=0.15)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '2_bifurcation.png'), dpi=300)
    plt.close()

def plot_lyapunov_and_ks():
    print("Generating Lyapunov & Kolmogorov Entropy...")
    param_range = np.linspace(0, 15, 400)
    
    le1_list = []
    le2_list = []
    ks_list = []
    p_valid = []
    
    for p in param_range:
        params = DEFAULT_PARAMS.copy()
        params['omega'] = p
        
        le = compute_lyapunov(params, n_iter=2000, n_transient=1000)
        
        if not np.isnan(le[0]):
            le1_list.append(le[0])
            le2_list.append(le[1])
            ks = max(0, le[0]) + max(0, le[1])
            ks_list.append(ks)
            p_valid.append(p)
            
    plt.figure(figsize=(10, 5))
    plt.plot(p_valid, le1_list, label='$\lambda_1$', linewidth=1, color='b')
    plt.plot(p_valid, le2_list, label='$\lambda_2$', linewidth=1, color='r')
    plt.axhline(0, color='k', linestyle='-', linewidth=0.8)
    plt.title('Lyapunov Exponents: Sine-Chebyshev-Ikeda', fontsize=14)
    plt.xlabel('$\omega$', fontsize=12)
    plt.ylabel('$\lambda_1, \lambda_2$', fontsize=12)
    plt.xlim(0, 15)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '3_lyapunov.png'), dpi=150)
    plt.close()
    
    plt.figure(figsize=(10, 5))
    plt.plot(p_valid, ks_list, 'g', linewidth=1.2)
    plt.title('Kolmogorov Entropy: Sine-Chebyshev-Ikeda', fontsize=14)
    plt.xlabel('$\omega$', fontsize=12)
    plt.ylabel('KE', fontsize=12)
    plt.xlim(0, 15)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '4_kolmogorov.png'), dpi=150)
    plt.close()

# ===========================================================
# SHANNON ENTROPY
# ===========================================================

def shannon_entropy(probabilities):
    probabilities = probabilities[probabilities > 0]
    return -np.sum(probabilities * np.log2(probabilities))

def plot_bifurcation_entropy():
    print("Generating Bifurcation Entropy Diagram...")
    param_range = np.linspace(0, 15, 400)
    n_transient = 2000
    n_iter = 5000
    
    entropy_list = []
    
    for p in param_range:
        params = DEFAULT_PARAMS.copy()
        params['omega'] = p
        
        x, y = 0.1, 0.1
        for _ in range(n_transient):
            x, y = sine_chebyshev_ikeda_step(x, y, **params)
            
        xs = np.zeros(n_iter)
        for i in range(n_iter):
            x, y = sine_chebyshev_ikeda_step(x, y, **params)
            xs[i] = x
            
        hist_x, _ = np.histogram(xs, bins=256, range=(-1, 1))
        p_x = hist_x / np.sum(hist_x)
        H_x = shannon_entropy(p_x)
        entropy_list.append(H_x)
        
    plt.figure(figsize=(12, 6), facecolor='white')
    plt.plot(param_range, entropy_list, c='purple', linewidth=1.2)
    plt.title('Bifurcation Entropy ($H_x$ vs $\omega$): Sine-Chebyshev-Ikeda', fontsize=14)
    plt.xlabel('$\omega$', fontsize=12)
    plt.ylabel('Shannon Entropy $H(x)$ (bits)', fontsize=12)
    plt.xlim(0, 15)
    plt.grid(True, color='gray', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '5_bifurcation_entropy.png'), dpi=300)
    plt.close()

def run_shannon_test(xs, ys, bins=256):
    print("\nRunning Shannon Entropy Test...")
    hist_x, _ = np.histogram(xs, bins=bins, range=(-1, 1))
    p_x = hist_x / np.sum(hist_x)
    H_x = shannon_entropy(p_x)
    
    hist_y, _ = np.histogram(ys, bins=bins, range=(-1, 1))
    p_y = hist_y / np.sum(hist_y)
    H_y = shannon_entropy(p_y)
    
    hist_xy, _, _ = np.histogram2d(xs, ys, bins=bins, range=[[-1, 1], [-1, 1]])
    p_xy = hist_xy / np.sum(hist_xy)
    H_xy = shannon_entropy(p_xy.ravel())
    
    H_xy_max = np.log2(bins * bins)
    H_xy_norm = H_xy / H_xy_max
    
    print(f"H(x) = {H_x:.6f} bits")
    print(f"H(y) = {H_y:.6f} bits")
    print(f"H(x,y) = {H_xy:.6f} bits (Max: {H_xy_max:.6f})")
    
    csv_path = os.path.join(plots_dir, "analyze_shannon_results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["H_x_bits", H_x])
        writer.writerow(["H_y_bits", H_y])
        writer.writerow(["H_xy_bits", H_xy])
        writer.writerow(["H_xy_max_bits", H_xy_max])
        writer.writerow(["H_xy_normalized", H_xy_norm])
        
    print(f"Shannon results saved to {csv_path}")

# ===========================================================
# NIST STATISTICAL TEST SUITE
# ===========================================================

def run_nist_test(xs, ys):
    print("\nRunning NIST Statistical Test Suite...")
    
    seq_x = (xs > 0).astype(np.int8)
    seq_y = (ys > 0).astype(np.int8)
    binary_seq = np.concatenate([seq_x, seq_y])
    
    try:
        from nistrng import check_eligibility_all_battery, run_all_battery, SP800_22R1A_BATTERY
    except ImportError:
        print("nistrng package not installed. Skipping NIST tests.")
        return
        
    print(f"Testing {len(binary_seq)} bits...")
    eligible_battery = check_eligibility_all_battery(binary_seq, SP800_22R1A_BATTERY)
    
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = run_all_battery(binary_seq, eligible_battery, False)
        
    csv_path = os.path.join(plots_dir, "analyze_nist_results.csv")
    passed_tests = 0
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Test Name", "Passed", "Time_ms"])
        
        for result, elapsed_time in results:
            status = "PASS" if result.passed else "FAIL"
            if result.passed: passed_tests += 1
            print(f"{result.name:35s} : {status}")
            writer.writerow([result.name, result.passed, elapsed_time])
            
    print(f"Passed {passed_tests} / {len(results)} tests.")
    print(f"NIST results saved to {csv_path}")

def main():
    print("Starting Sine-Chebyshev-Ikeda Analysis...")
    xs, ys = plot_trajectory()
    plot_bifurcation()
    plot_lyapunov_and_ks()
    plot_bifurcation_entropy()
    
    run_shannon_test(xs, ys)
    run_nist_test(xs, ys)
    
    print(f"\nDone! All plots and CSVs saved to {plots_dir}")

if __name__ == '__main__':
    main()
