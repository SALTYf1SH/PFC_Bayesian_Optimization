# -*- coding: utf-8 -*-
"""
Data Preprocessing Script for Experimental Stress-Strain Curves.

This script reads raw experimental data from a testing machine, processes it,
and saves a clean stress-strain curve ready for use as a target in the
Bayesian optimization process.

It performs the following steps:
1.  Reads the raw data file.
2.  Identifies the valid loading section of the test.
3.  Converts units from Load(kN)/Displacement(mm) to Stress(MPa)/Strain(%).
4.  Normalizes the curve to start from the origin (0,0).
5.  Truncates the data at the peak stress (UCS).
6.  Saves the final clean curve to the '2_target_data' directory.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =============================================================================
# --- CONFIGURATION ---
# 用户主要在此处修改配置
# =============================================================================

# 1. File Paths (文件路径)
#    请确保这些路径相对于项目根目录是正确的
RAW_DATA_DIR = os.path.join("2_target_data", "raw_experimental_data")
# !! 修改为您要处理的原始数据文件名 !!
RAW_DATA_FILENAME = "experiment_run_1.txt"
# 处理后输出的目标曲线路径
TARGET_CURVE_OUTPUT_PATH = os.path.join("2_target_data", "target_curve.csv")

# 2. Specimen Dimensions (试样尺寸)
#    用于计算应力和应变
SPECIMEN_DIAMETER_MM = 50.0  # 试样直径 (mm)
SPECIMEN_HEIGHT_MM = 100.0 # 试样高度 (mm)

# 3. Raw Data File Format (原始数据文件格式)
#    根据您的试验机输出文件进行调整
#    例如，如果您的数据文件有10行文件头，则设置为10
HEADER_ROWS_TO_SKIP = 9
#    指定数据列的分隔符，'\t' 代表制表符, ',' 代表逗号
COLUMN_SEPARATOR = '\t'
#    指定原始数据中代表位移和载荷的列名
DISPLACEMENT_COL = 'Stroke(mm)' # 位移列名
LOAD_COL = 'Load(kN)'         # 载荷列名

# =============================================================================
# --- DATA PROCESSING FUNCTION ---
# =============================================================================

def process_experimental_data():
    """
    Main function to process the raw experimental data.
    """
    input_file_path = os.path.join(RAW_DATA_DIR, RAW_DATA_FILENAME)

    print(f"--- Starting Data Preprocessing ---")
    print(f"Reading raw data from: '{input_file_path}'")

    # --- 1. Load Raw Data ---
    try:
        df = pd.read_csv(
            input_file_path,
            sep=COLUMN_SEPARATOR,
            skiprows=HEADER_ROWS_TO_SKIP,
            encoding='gb18030' # 使用 'gb18030' 或 'utf-8' 编码以支持中文
        )
        # Select only the necessary columns
        df = df[[DISPLACEMENT_COL, LOAD_COL]]
        # Remove any rows with missing values
        df.dropna(inplace=True)
    except FileNotFoundError:
        print(f"[ERROR] Raw data file not found at '{input_file_path}'.")
        return
    except Exception as e:
        print(f"[ERROR] Failed to read data file: {e}")
        return

    print("Successfully loaded raw data.")

    # --- 2. Data Cleaning and Unit Conversion ---
    # Ensure data is numeric, coercing errors to NaN and then dropping them
    df[LOAD_COL] = pd.to_numeric(df[LOAD_COL], errors='coerce')
    df[DISPLACEMENT_COL] = pd.to_numeric(df[DISPLACEMENT_COL], errors='coerce')
    df.dropna(inplace=True)

    # Convert units
    specimen_area_m2 = np.pi * ((SPECIMEN_DIAMETER_MM / 2 / 1000) ** 2) # m^2
    
    # Stress in MPa
    df['Stress'] = (df[LOAD_COL] * 1000) / specimen_area_m2 / 1e6
    # Strain (unitless)
    df['Strain'] = df[DISPLACEMENT_COL] / SPECIMEN_HEIGHT_MM

    print("Converted units to Stress (MPa) and Strain.")

    # --- 3. Isolate the relevant part of the curve ---
    # Find the peak stress (Ultimate Compressive Strength)
    peak_stress_index = df['Stress'].idxmax()
    
    # Truncate the data up to the peak stress
    df_peak = df.loc[:peak_stress_index].copy()
    
    # Often, the test starts with a small pre-load. We find the "true" start
    # by looking for the minimum stress point before the peak.
    # This handles any initial seating effects.
    min_stress_before_peak_index = df_peak['Stress'].idxmin()
    df_final = df_peak.loc[min_stress_before_peak_index:].copy()

    print("Isolated the loading curve up to peak stress.")

    # --- 4. Normalize the curve to start at (0,0) ---
    df_final['Strain'] = df_final['Strain'] - df_final['Strain'].iloc[0]
    df_final['Stress'] = df_final['Stress'] - df_final['Stress'].iloc[0]

    print("Normalized curve to start at (0,0).")

    # --- 5. Save the Processed Data ---
    # Select only the final 'Strain' and 'Stress' columns
    output_df = df_final[['Strain', 'Stress']]
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(TARGET_CURVE_OUTPUT_PATH), exist_ok=True)
    
    output_df.to_csv(TARGET_CURVE_OUTPUT_PATH, index=False)
    print(f"Successfully saved processed target curve to: '{TARGET_CURVE_OUTPUT_PATH}'")

    # --- 6. (Optional) Plot for Verification ---
    plt.figure(figsize=(8, 6))
    plt.plot(output_df['Strain'], output_df['Stress'], label='Processed Target Curve')
    plt.title('Processed Experimental Stress-Strain Curve')
    plt.xlabel('Strain')
    plt.ylabel('Stress (MPa)')
    plt.grid(True)
    plt.legend()
    plot_filename = os.path.join(os.path.dirname(TARGET_CURVE_OUTPUT_PATH), "target_curve_verification_plot.png")
    plt.savefig(plot_filename)
    print(f"Verification plot saved to: '{plot_filename}'")
    # plt.show()


# =============================================================================
# --- MAIN EXECUTION BLOCK ---
# =============================================================================

if __name__ == '__main__':
    # This allows the script to be run directly from the command line.
    process_experimental_data()
