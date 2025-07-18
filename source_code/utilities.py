# -*- coding: utf-8 -*-
"""
Utility Module for the Bayesian Optimization Project.

This module contains helper functions for tasks such as setting up results
directories, saving outputs, and plotting, keeping the main scripts clean.
"""

import os
import json
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from skopt.plots import plot_convergence as skopt_plot_convergence

def setup_results_directory():
    """
    Creates a new, timestamped directory for storing the results of an
    optimization run.

    Returns:
        tuple: A tuple containing (results_dir_path, curves_dir_path).
    """
    # Generate a timestamp for the directory name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    results_dir = os.path.join("4_optimization_results", f"run_{timestamp}")
    curves_dir = os.path.join(results_dir, "curves")

    # Create the directories
    os.makedirs(curves_dir, exist_ok=True)
    
    return results_dir, curves_dir

def save_best_parameters(params_dict, filepath):
    """
    Saves the best found parameters to a JSON file.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(params_dict, f, indent=4, ensure_ascii=False)
    print(f"Best parameters saved to: '{filepath}'")

def plot_convergence(result, filepath):
    """
    Plots and saves the optimization convergence plot.
    """
    skopt_plot_convergence(result)
    plt.title("Convergence Plot")
    plt.xlabel("Iteration")
    plt.ylabel("Minimum Loss Found")
    plt.grid(True)
    plt.savefig(filepath)
    plt.close() # Close the plot to free up memory
    print(f"Convergence plot saved to: '{filepath}'")

def plot_comparison_curve(sim_df, target_df, iteration, loss, filepath):
    """
    Plots the simulated curve against the target curve and saves the figure.
    """
    plt.figure(figsize=(10, 7))
    plt.plot(target_df['Strain'], target_df['Stress'], 'k-', label='Target (Experimental)', linewidth=2.5)
    plt.plot(sim_df['Strain'], sim_df['Stress'], 'r--', label=f'Simulation (Iter {iteration})', linewidth=1.5)
    plt.title(f'Iteration {iteration} - DTW Loss: {loss:.4f}')
    plt.xlabel('Strain')
    plt.ylabel('Stress (MPa)')
    plt.legend()
    plt.grid(True)
    plt.savefig(filepath)
    plt.close() # Close the plot to free up memory
    print(f"Comparison plot for iteration {iteration} saved.")

