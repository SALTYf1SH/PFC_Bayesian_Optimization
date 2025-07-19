# -*- coding: utf-8 -*-
"""
Knowledge Base Manager for Bayesian Optimization

This module handles all interactions with the persistent knowledge base,
which stores the results of every PFC simulation. This allows for caching
and warm-starting the optimization process. This version is updated to use
the key-point based loss function for evaluating prior points.
"""
import os
import json
import hashlib
import pandas as pd
# Import the new key-point loss function
from source_code.loss_functions import calculate_keypoint_loss

KNOWLEDGE_BASE_DIR = "knowledge_base"

def ensure_kb_directory():
    """Ensures the knowledge base directory exists."""
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)

def get_params_hash(params_dict):
    """
    Creates a unique, deterministic SHA256 hash for a dictionary of parameters.
    Sorting the keys ensures that the same parameters always produce the same hash.
    """
    sorted_params_str = json.dumps(params_dict, sort_keys=True)
    return hashlib.sha256(sorted_params_str.encode('utf-8')).hexdigest()

def save_to_knowledge_base(params_dict, sim_df):
    """
    Saves a simulation result (parameters and curve) to the knowledge base.
    """
    param_hash = get_params_hash(params_dict)
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{param_hash}.json")
    
    data_to_save = {
        'parameters': params_dict,
        'strain': sim_df['Strain'].tolist(),
        'stress': sim_df['Stress'].tolist()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, indent=4)
    print(f"  -> Result saved to knowledge base: {param_hash[:10]}...")

def load_from_knowledge_base(params_dict):
    """
    Tries to load a simulation result from the knowledge base.
    Returns the DataFrame if found, otherwise returns None.
    """
    param_hash = get_params_hash(params_dict)
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{param_hash}.json")
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sim_df = pd.DataFrame({'Strain': data['strain'], 'Stress': data['stress']})
        print(f"  -> Cache hit! Loaded result from knowledge base: {param_hash[:10]}...")
        return sim_df
    return None

def warm_start_optimizer(parameter_space, s_target, w_peak_point=1.0, w_max_strain=1.0):
    """
    Loads all existing knowledge, calculates their KEY-POINT loss against the new target,
    and prepares them as prior points (x0, y0) for the optimizer.

    Args:
        parameter_space (list): The skopt parameter space definition.
        s_target (np.ndarray): The target curve data.
        w_peak_point (float): Weight for the peak point distance error.
        w_max_strain (float): Weight for the maximum strain error.

    Returns:
        tuple: A tuple containing (x0_prior, y0_prior) lists for the optimizer.
    """
    print("\n--- Initializing Optimizer with Prior Knowledge (Key-Point Loss) ---")
    ensure_kb_directory()
    
    x0_prior = []
    y0_prior = []
    
    param_names = [p.name for p in parameter_space]
    
    kb_files = [f for f in os.listdir(KNOWLEDGE_BASE_DIR) if f.endswith(".json")]
    total_files = len(kb_files)
    
    if total_files == 0:
        print("No prior knowledge found. Starting with random exploration.")
        return [], []

    for i, filename in enumerate(kb_files):
        # A simple progress indicator for the user
        print(f"  Processing prior point {i+1}/{total_files}...", end='\r')
        
        filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Recreate the parameter list in the correct order for skopt
        params_dict = data['parameters']
        params_list = [params_dict[name] for name in param_names]
        
        # Recreate the simulation curve DataFrame and numpy array
        sim_curve = pd.DataFrame({'Strain': data['strain'], 'Stress': data['stress']})
        s_simulated = sim_curve[['Strain', 'Stress']].values.T
        
        # Call the new key-point loss function with the specified weights
        loss = calculate_keypoint_loss(s_target, s_simulated, 
                                       w_peak_point=w_peak_point, 
                                       w_max_strain=w_max_strain)
        
        x0_prior.append(params_list)
        y0_prior.append(loss)

    print("\n") # Add a newline to move past the progress indicator line
    print(f"Loaded and processed {len(x0_prior)} prior data points from the knowledge base.")
        
    return x0_prior, y0_prior
