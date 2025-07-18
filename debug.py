import os
import sys
import json
import socket

try:
    import itasca as it
except ImportError:
    print("[FATAL] This script must be run within the PFC application environment.")
    sys.exit(1)


def _run_single_simulation():
    """
    The core logic for running one PFC simulation.
    *** FINAL VERSION - ALL STAGES CORRECTED, USING HISTORY RECORDING ***
    This version strictly adheres to the user-provided standard code for all stages.

    Returns:
        dict: A dictionary with 'Strain' and 'Stress' lists.
    """
    history_filename = "temp_server_history.txt"
    try:
        # --- Set Micro-parameters from the optimizer ---

        emod = 1e10
        kratio = 2.0
        pb_emod = 5e10
        pb_kratio = 2.0
        pb_fric = 0.5
        pb_coh = 5e7
        pb_ten = 5e7
        
        
        # --- 路径配置 ---
        project_root = os.getcwd()
        model_dir = os.path.join(project_root, "pfc_model")
        ss_wall_path = os.path.join(model_dir, "ss_wall.fis").replace('\\', '/')
        fracture_path = os.path.join(model_dir, "fracture.p2fis").replace('\\', '/')

        # ======================================================================
        # --- 步骤 1 & 2: 创建并胶结试样 (流程已验证) ---
        # ======================================================================
        print("  步骤 1 & 2: 创建并胶结试样...")
        it.command("model new")
        it.command("model domain extent -0.05 0.05 -0.1 0.1 condition destroy")
        it.command("contact cmat default model linear method deform emod 1.0e9 kratio 0.0")
        it.command("contact cmat default property dp_nratio 0.5")
        it.command("wall create vertices -0.03,0.05 0.03,0.05 id 1")
        it.command("wall create vertices -0.03,-0.05 0.03,-0.05 id 2")
        it.command("wall create vertices -0.025,-0.06 -0.025,0.06 id 3")
        it.command("wall create vertices 0.025,-0.06 0.025,0.06 id 4")
        it.command("model random 10001")
        it.command("ball distribute porosity 0.1 radius 0.5e-3 0.75e-3 box -0.025 0.025 -0.05 0.05")
        it.command("ball attribute density 2500 damp 0.7")
        it.command("model cycle 1000 calm 10")
        it.command("model mechanical timestep scale")
        it.command("model solve ratio-average 1e-4")
        it.command("model mechanical timestep auto")
        it.command("model calm")
        it.command("wall delete range id 3 4")
        it.command("contact model linearpbond range contact type 'ball-ball'")
        it.command("contact method bond gap 0.5e-4")
        it.command(f"contact method deform emod {emod} krat {kratio}")
        it.command(f"contact method pb_deform emod {pb_emod} krat {pb_kratio}")
        it.command(f"contact property pb_ten {pb_ten} pb_coh {pb_coh} pb_fa 0.0")
        it.command(f"contact property fric {pb_fric} range contact type 'ball-ball'")
        it.command("contact property dp_nratio 0.5")
        it.command("ball attribute displacement multiply 0.0")
        it.command("contact property lin_force 0.0 0.0 lin_mode 1")
        it.command("ball attribute force-contact multiply 0.0 moment-contact multiply 0.0")
        it.command("model cycle 1")
        it.command("model solve ratio-average 1e-5")

        # ======================================================================
        # --- 步骤 3: 运行压缩测试并记录History ---
        # ======================================================================
        print("  步骤 3: 开始压缩测试并设置History...")
        it.command(f"call '{ss_wall_path}'")
        it.command(f"call '{fracture_path}'")
        it.command("@setup_wall")
        it.command("history delete")
        it.command("fish history name 1 @axial_strain_wall")
        it.command("fish history name 2 @axial_stress_wall")
        it.command("[u=0.05]")
        it.command("wall attribute velocity-y [-u] range id 1")
        it.command("wall attribute velocity-y [u] range id 2")
        it.command("ball attribute damp 0.1")
        it.command("model cycle 1000")
        it.command("[peak_fraction = 0.7]")
        it.command("model solve fish-halt @loadhalt_wall")
        it.command(f"history export 1 2 file '{history_filename}'")

        # ======================================================================
        # --- 步骤 4: 使用纯Python从导出的文件中读取数据 ---
        # ======================================================================
        print(f"  读取导出的历史文件: '{history_filename}'")
        strain_list = []
        stress_list = []
        try:
            with open(history_filename, 'r') as f:
                for line in f:
                    try:
                        # 尝试将行分割并转换为浮点数
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            # 第1列是步数，第2列是应变，第3列是应力
                            strain = abs(float(parts[1]))
                            stress_pa = abs(float(parts[2]))
                            stress_mpa = stress_pa / 1e6
                            
                            strain_list.append(strain)
                            stress_list.append(stress_mpa)
                    except (ValueError, IndexError):
                        # 如果某一行是文本或格式不正确，则忽略这一行
                        # print(f"Skipping non-numeric line: {line.strip()}")
                        continue
            
            if strain_list and stress_list:
                return {'Strain': strain_list, 'Stress': stress_list}
        except Exception as file_error:
            print(f"  [错误] 无法读取或解析历史文件: {file_error}")

    except Exception as e:
        print(f"[PFC ERROR] 模拟过程中发生异常: {e}")
    finally:
        if os.path.exists(history_filename):
            print('1')
            #os.remove(history_filename)

    return {'Strain': [], 'Stress': []}

_run_single_simulation()