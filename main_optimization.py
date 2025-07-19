# -*- coding: utf-8 -*-
"""
Main Optimization Client with Knowledge Base and Key-Point Loss Function

This version automatically finds and processes all target curve files (.csv)
in the 'target_data' directory, running a full optimization for each one.
It uses a fast, key-point based loss function and a persistent knowledge base.
"""
import os
import json
import socket
import pandas as pd
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args

# --- Import custom modules ---
from source_code.loss_functions import calculate_keypoint_loss
from source_code.utilities import setup_results_directory, save_best_parameters, plot_convergence, plot_comparison_curve
from source_code.knowledge_base_manager import warm_start_optimizer, load_from_knowledge_base, save_to_knowledge_base

# =============================================================================
# --- CONFIGURATION ---
# =============================================================================
# 1. PFC Server Connection Settings
SERVER_LIST = [('127.0.0.1', 50001)]
CONNECTION_TIMEOUT = 10

# 2. File Paths
# The script will now automatically scan this directory for target files.
TARGET_DATA_DIR = "target_data"

# 3. Bayesian Optimization Settings
N_CALLS = 10
N_INITIAL_POINTS = 5

# 4. Key-Point Loss Function Settings
W_PEAK_POINT = 1.0
W_MAX_STRAIN = 1.0

# 5. PFC Micro-parameter Space
PARAMETER_SPACE = [
    Real(1e9, 50e9, name='emod'),
    Real(1.0, 5.0, name='kratio'),
    Real(5e9, 100e9, name='pb_emod'),
    Real(0.3, 1.0, name='pb_fric'),
    Real(10e6, 200e6, name='pb_coh'),
    Real(10e6, 200e6, name='pb_ten')
]

# =============================================================================
# --- CORE FUNCTIONS ---
# =============================================================================

def run_simulation(params_dict):
    """
    Manages running a simulation: checks cache, else connects to a PFC server.
    """
    cached_result = load_from_knowledge_base(params_dict)
    if cached_result is not None:
        return cached_result

    print("  -> Cache miss. Connecting to PFC server for simulation...")
    params_json = json.dumps(params_dict)
    for host, port in SERVER_LIST:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONNECTION_TIMEOUT)
                s.connect((host, port))
                s.sendall(params_json.encode('utf-8'))
                ack = s.recv(1024)
                if ack == b'ACK_RECEIVED':
                    s.settimeout(None)
                    fragments = []
                    while True:
                        chunk = s.recv(4096)
                        if not chunk: break
                        fragments.append(chunk)
                    data = b"".join(fragments).decode('utf-8')
                    sim_df = pd.DataFrame(json.loads(data))
                    
                    if not sim_df.empty:
                        save_to_knowledge_base(params_dict, sim_df)
                    return sim_df
        except Exception as e:
            print(f"  -> Server {host}:{port} failed: {e}. Trying next.")
            continue
    
    return pd.DataFrame()

# =============================================================================
# --- MAIN EXECUTION BLOCK ---
# =============================================================================

if __name__ == '__main__':
    # --- Find all target files in the directory ---
    try:
        target_files = [f for f in os.listdir(TARGET_DATA_DIR) if f.endswith('.csv')]
        if not target_files:
            print(f"[致命错误] 在 '{TARGET_DATA_DIR}' 目录中未找到任何 .csv 目标文件。")
            exit()
    except FileNotFoundError:
        print(f"[致命错误] 目标数据目录 '{TARGET_DATA_DIR}' 不存在。")
        exit()

    print(f"发现 {len(target_files)} 个目标文件，将依次进行优化: {target_files}")

    # --- Main loop to iterate over each target file ---
    for target_filename in target_files:
        print(f"\n\n=========================================================")
        print(f"===      开始优化目标: {target_filename}      ===")
        print("=========================================================\n")

        # Reset global counter for each new target
        iteration_counter = 0
        
        # Construct full path for the current target
        target_curve_path = os.path.join(TARGET_DATA_DIR, target_filename)

        # Load and process the current target curve
        try:
            target_df = pd.read_csv(target_curve_path)
            
            if 'Stress(Pa)' in target_df.columns:
                target_df.rename(columns={'Stress(Pa)': 'Stress'}, inplace=True)
            target_df['Stress'] /= 1e6 # Pa to MPa
            s_target = target_df[['Strain', 'Stress']].values.T
            print(f"成功从 '{target_curve_path}' 加载并处理了目标曲线。")
        except Exception as e:
            print(f"[错误] 加载目标文件 '{target_filename}' 失败: {e}. 跳过此文件。")
            continue # Skip to the next file

        # Create a unique results directory for this specific target file
        results_dir, curves_dir = setup_results_directory(target_filename)
        print(f"本次运行的结果将保存在: '{results_dir}'")

        # Define the objective function within this loop's scope.
        # This allows it to "capture" the correct s_target, target_df, etc. for each run.
        @use_named_args(dimensions=PARAMETER_SPACE)
        def objective_function(**params):
            global iteration_counter
            iteration_counter += 1
            print(f"\n--- Iteration {iteration_counter}/{N_CALLS} (New Simulation) ---")
            print(f"Testing parameters: {params}")

            loss = 1e10
            try:
                sim_df = run_simulation(params)
                if sim_df.empty or sim_df.shape[0] < 5:
                    print("  -> Simulation failed or produced insufficient data.")
                    return loss

                s_simulated = sim_df[['Strain', 'Stress']].values.T
                loss = calculate_keypoint_loss(s_target, s_simulated, 
                                               w_peak_point=W_PEAK_POINT, 
                                               w_max_strain=W_MAX_STRAIN)
                print(f"  -> Key-Point Loss = {loss:.4f}")

                plot_path = os.path.join(curves_dir, f"iteration_{iteration_counter}.png")
                plot_comparison_curve(sim_df, target_df, iteration_counter, loss, plot_path)
            except Exception as e:
                print(f"  -> [ERROR] An unexpected error occurred in objective function: {e}")
            return loss

        # --- 1. WARM-START: Load prior knowledge for the current target ---
        x_prior, y_prior = warm_start_optimizer(PARAMETER_SPACE, s_target, 
                                                w_peak_point=W_PEAK_POINT,
                                                w_max_strain=W_MAX_STRAIN)
        
        n_initial = 0 if x_prior else N_INITIAL_POINTS

        try:
            # --- 2. RUN OPTIMIZATION for the current target ---
            result = gp_minimize(
                func=objective_function,
                dimensions=PARAMETER_SPACE,
                x0=x_prior if x_prior else None,
                y0=y_prior if y_prior else None,
                n_calls=N_CALLS,
                n_initial_points=n_initial,
                random_state=123,
                verbose=True
            )
            
            print("\n---------------------------------------------------------")
            print(f"---           优化完成: {target_filename}           ---")
            print("---------------------------------------------------------\n")

            best_params_dict = {p.name: v for p, v in zip(PARAMETER_SPACE, result.x)}
            print(f"达到的最小损失值: {result.fun:.4f}")
            print("找到的最佳参数组合:")
            print(json.dumps(best_params_dict, indent=4))
            
            param_filepath = os.path.join(results_dir, "best_parameters.json")
            save_best_parameters(best_params_dict, param_filepath)
            
            convergence_filepath = os.path.join(results_dir, "convergence_plot.png")
            plot_convergence(result, convergence_filepath)

        except Exception as e:
            print(f"\n[严重] 针对 '{target_filename}' 的优化进程因错误而终止: {e}")

    print(f"\n\n=========================================================")
    print("===            所有目标文件均已优化完成            ===")
    print("=========================================================")
