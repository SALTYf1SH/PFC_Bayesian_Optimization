# -*- coding: utf-8 -*-
"""
Module for calculating loss/distance between stress-strain curves.

This version uses a KEY-POINT based loss function. It focuses on the
most critical mechanical properties: the peak stress point and the
maximum strain. This is computationally much faster and often more
meaningful than DTW.
"""
import numpy as np

def calculate_keypoint_loss(s_target, s_simulated, w_peak_point=1.0, w_max_strain=1.0):
    """
    Calculates a composite loss based on key mechanical property points.

    The loss is a weighted sum of two relative errors:
    1. The relative Euclidean distance between the peak stress points of the two curves.
    2. The relative error of the maximum strain values.

    Args:
        s_target (np.ndarray): The target curve, shape (2, N).
        s_simulated (np.ndarray): The simulated curve, shape (2, M).
        w_peak_point (float): Weight for the peak point distance error.
        w_max_strain (float): Weight for the maximum strain error.

    Returns:
        float: The total composite loss, or a large number if calculation fails.
    """
    try:
        # --- 1. Find Peak Stress Point for Both Curves ---
        # Target Curve
        target_strain = s_target[0]
        target_stress = s_target[1]
        peak_stress_target_idx = np.argmax(target_stress)
        peak_stress_target = target_stress[peak_stress_target_idx]
        strain_at_peak_target = target_strain[peak_stress_target_idx]
        peak_point_target = np.array([strain_at_peak_target, peak_stress_target])

        # Simulated Curve
        sim_strain = s_simulated[0]
        sim_stress = s_simulated[1]
        peak_stress_sim_idx = np.argmax(sim_stress)
        peak_stress_sim = sim_stress[peak_stress_sim_idx]
        strain_at_peak_sim = sim_strain[peak_stress_sim_idx]
        peak_point_sim = np.array([strain_at_peak_sim, peak_stress_sim])

        # --- 2. Calculate Relative Euclidean Distance Error for the Peak Point ---
        # Euclidean distance between the two peak points
        euclidean_dist = np.linalg.norm(peak_point_target - peak_point_sim)
        
        # Normalize the distance by the magnitude of the target's peak point vector
        # This creates a scale-invariant relative error. Add 1e-9 to avoid division by zero.
        target_point_magnitude = np.linalg.norm(peak_point_target)
        relative_peak_dist_error = euclidean_dist / (target_point_magnitude + 1e-9)

        # --- 3. Find Maximum Strain for Both Curves ---
        max_strain_target = np.max(target_strain)
        max_strain_sim = np.max(sim_strain)

        # --- 4. Calculate Relative Error for Maximum Strain ---
        # Add 1e-9 to avoid division by zero if max strain is zero.
        relative_max_strain_error = np.abs(max_strain_target - max_strain_sim) / (max_strain_target + 1e-9)

        # --- 5. Combine Errors with Weights ---
        total_loss = (w_peak_point * relative_peak_dist_error) + (w_max_strain * relative_max_strain_error)
        
        return total_loss

    except (IndexError, ValueError) as e:
        # This can happen if a curve is empty or invalid
        print(f"  [Warning] Could not calculate keypoint loss: {e}")
        return 1e10 # Return a large penalty value
