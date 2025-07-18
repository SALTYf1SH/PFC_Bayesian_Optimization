# -*- coding: utf-8 -*-
"""
Main Optimization Client (Corrected)

This script runs in a standard Python environment and acts as the client.
It connects to the PFC server, sends parameter sets for evaluation, and
drives the Bayesian optimization loop.

This version includes a fix for the column name mismatch, the unit conversion
for the target data file, and a robust server connection handling mechanism
with timeouts and a server list.
"""
import os
import json
import socket
import pandas as pd
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args

# --- Import custom modules from the 'source_code' directory ---
from source_code.loss_functions import dtw_distance
from source_code.utilities import setup_results_directory, save_best_parameters, plot_convergence, plot_comparison_curve

# =============================================================================
# --- CONFIGURATION ---
# =============================================================================

# 1. PFC Server Connection Settings
# 可用的PFC服务器列表，格式为 (IP地址, 端口号) 的元组列表
SERVER_LIST = [
    ('127.0.0.1', 50009),
    # ('127.0.0.1', 50010), # 可以添加更多服务器
]
# 连接和接收确认消息的超时时间 (秒)
CONNECTION_TIMEOUT = 10

# 2. File Paths
TARGET_CURVE_PATH = os.path.join("target_data", "111.txt.csv")

# 3. Bayesian Optimization Settings
N_CALLS = 50
N_INITIAL_POINTS = 10

# 4. PFC Micro-parameter Space
PARAMETER_SPACE = [
    Real(1e9, 50e9, name='emod'),
    Real(1.0, 5.0, name='kratio'),
    Real(5e9, 100e9, name='pb_emod'),
    Real(0.3, 1.0, name='pb_fric'),
    Real(10e6, 200e6, name='pb_coh'),
    Real(10e6, 200e6, name='pb_ten')
]

# =============================================================================
# --- GLOBAL VARIABLES AND SETUP ---
# =============================================================================

iteration_counter = 0

# Load the target experimental curve once at the start.
try:
    target_df = pd.read_csv(TARGET_CURVE_PATH)
    
    # Rename the stress column to be consistent.
    if 'Stress(Pa)' in target_df.columns:
        target_df.rename(columns={'Stress(Pa)': 'Stress'}, inplace=True)
        print("成功将目标数据中的列名 'Stress(Pa)' 重命名为 'Stress'。")

    # Convert target stress from Pa to MPa.
    if 'Stress' in target_df.columns:
        target_df['Stress'] = target_df['Stress'] / 1e6
        print("成功将目标数据的应力单位从 Pa 转换为 MPa。")

    # Convert to the NumPy array format required by the DTW function
    s_target = target_df[['Strain', 'Stress']].values.T
    print(f"成功从 '{TARGET_CURVE_PATH}' 加载并处理了目标曲线。")
except FileNotFoundError:
    print(f"[错误] 目标曲线文件 '{TARGET_CURVE_PATH}' 未找到。请先运行数据预处理脚本。")
    exit()
except KeyError:
    print(f"[错误] 目标文件必须包含 'Strain' 和 'Stress(Pa)' 列。")
    exit()


# Create a results directory for this optimization run.
results_dir, curves_dir = setup_results_directory()
print(f"本次运行的结果将保存在: '{results_dir}'")


# =============================================================================
# --- CORE FUNCTIONS ---
# =============================================================================

def evaluate_parameters_via_socket(params):
    """
    从服务器列表中连接一个可用的PFC服务器，发送参数，等待确认，然后获取模拟结果。
    本函数会处理超时，并在当前服务器繁忙或离线时尝试连接下一个。
    """
    params_json = json.dumps(params)
    
    for host, port in SERVER_LIST:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # 为初始连接和ACK确认设置一个较短的超时
                s.settimeout(CONNECTION_TIMEOUT)
                
                print(f"  正在尝试连接PFC服务器 -> {host}:{port}...")
                s.connect((host, port))
                
                # 发送参数
                s.sendall(params_json.encode('utf-8'))
                print("  参数已发送，等待服务器确认...")

                # 等待确认消息
                ack = s.recv(1024)
                if ack == b'ACK_RECEIVED':
                    print(f"  已收到来自 {host}:{port} 的确认。服务器正在计算...")
                    # 为接收最终结果设置一个更长的超时（None代表无限等待）
                    s.settimeout(None) 
                    
                    # 接收最终结果
                    fragments = []
                    while True:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        fragments.append(chunk)
                    
                    data = b"".join(fragments).decode('utf-8')
                    print("  结果已接收。")
                    
                    data_dict = json.loads(data)
                    sim_df = pd.DataFrame(data_dict)
                    return sim_df # 成功获取结果，退出循环和函数
                else:
                    print(f"  从 {host}:{port} 收到意外的回复。正在尝试下一个服务器。")
                    continue

        except socket.timeout:
            print(f"  连接到 {host}:{port} 超时。服务器可能正忙或已离线。正在尝试下一个服务器。")
            continue
        except ConnectionRefusedError:
            print(f"  连接到 {host}:{port} 被拒绝。服务器已离线。正在尝试下一个服务器。")
            continue
        except Exception as e:
            print(f"  与 {host}:{port} 通信时发生意外错误: {e}。正在尝试下一个服务器。")
            continue

    # 如果循环完成仍未返回，说明所有服务器都连接失败
    print("\n[致命错误] 列表中的所有PFC服务器均无响应。")
    raise ConnectionError("无法连接到任何PFC服务器。")


@use_named_args(dimensions=PARAMETER_SPACE)
def objective_function(**params):
    """
    优化器将尝试最小化此目标函数的返回值。
    """
    global iteration_counter
    iteration_counter += 1
    print(f"\n--- 第 {iteration_counter}/{N_CALLS} 次迭代 ---")
    print(f"测试参数: {params}")

    loss = 1e10  # 模拟失败时的默认巨大损失值
    try:
        # 1. 通过socket调用PFC服务器进行计算
        sim_df = evaluate_parameters_via_socket(params)
        
        # 2. 检查模拟是否成功并返回了有效数据
        if sim_df.empty or sim_df.shape[0] < 5:
            print("  -> 模拟失败或未生成有效数据。")
            return loss

        # 3. 计算模拟曲线与目标曲线的DTW误差
        s_simulated = sim_df[['Strain', 'Stress']].values.T
        loss = dtw_distance(s_target, s_simulated)
        print(f"  -> 模拟成功。DTW 误差 = {loss:.4f}")

        # 4. 绘制并保存本次迭代的曲线对比图
        plot_path = os.path.join(curves_dir, f"iteration_{iteration_counter}.png")
        plot_comparison_curve(sim_df, target_df, iteration_counter, loss, plot_path)

    except ConnectionError as e:
        print(f"\n[致命错误] {e}")
        raise # 重新抛出异常以终止优化过程
    except Exception as e:
        print(f"  -> [错误] 发生意外错误: {e}")

    return loss

# =============================================================================
# --- MAIN EXECUTION BLOCK ---
# =============================================================================

if __name__ == '__main__':
    print("\n=========================================================")
    print("===           启动贝叶斯优化客户端程序            ===")
    print(f"===  尝试连接PFC服务器列表...  ===")
    print("=========================================================\n")

    try:
        result = gp_minimize(
            func=objective_function,
            dimensions=PARAMETER_SPACE,
            n_calls=N_CALLS,
            n_initial_points=N_INITIAL_POINTS,
            random_state=123,
            verbose=True
        )
        
        print("\n=========================================================")
        print("===                   优化完成                   ===")
        print("=========================================================\n")

        best_params_dict = {p.name: v for p, v in zip(PARAMETER_SPACE, result.x)}

        print(f"达到的最小DTW误差: {result.fun:.4f}")
        print("找到的最佳参数组合:")
        print(json.dumps(best_params_dict, indent=4))
        
        param_filepath = os.path.join(results_dir, "best_parameters.json")
        save_best_parameters(best_params_dict, param_filepath)
        
        convergence_filepath = os.path.join(results_dir, "convergence_plot.png")
        plot_convergence(result, convergence_filepath)

    except Exception as e:
        print(f"\n[严重] 优化进程因错误而终止: {e}")

    print(f"\n所有结果、绘图和日志均已保存至 '{results_dir}'。")
