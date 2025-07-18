# -*- coding: utf-8 -*-
"""
Module for calculating loss/distance between stress-strain curves.

This module provides functions to quantify the difference between a simulated
stress-strain curve and a target experimental curve. The primary method used
is Dynamic Time Warping (DTW), which is effective for comparing two sequences
that may vary in time or speed.
"""

import numpy as np

def _euclidean_distance(p1, p2):
    """
    Calculates the Euclidean distance between two points.
    计算两个数据点之间的欧氏距离。

    Args:
        p1 (np.ndarray): The first point [strain, stress].
        p2 (np.ndarray): The second point [strain, stress].

    Returns:
        float: The Euclidean distance.
    """
    return np.linalg.norm(p1 - p2)

def dtw_distance(s1, s2):
    """
    Computes the Dynamic Time Warping (DTW) distance between two curves.
    
    This function is adapted from the user's previous DWT.py script. It finds
    the optimal alignment between two curves and returns a value representing
    their dissimilarity. A lower value means the curves are more similar.

    Args:
        s1 (np.ndarray): The first curve, with shape (2, M), where M is the
                         number of points. s1[0] is strain, s1[1] is stress.
        s2 (np.ndarray): The second curve, with shape (2, N), where N is the
                         number of points. s2[0] is strain, s2[1] is stress.

    Returns:
        float: The total DTW distance between the two curves. Returns np.inf
               if either curve is empty.
    """
    # Ensure the input arrays have the correct shape
    if s1.shape[0] != 2 or s2.shape[0] != 2:
        raise ValueError("Input series must have shape (2, N), where rows are strain and stress.")

    M, N = s1.shape[1], s2.shape[1]

    # Handle empty curves
    if M == 0 or N == 0:
        return np.inf

    # Initialize the cost matrix with infinity
    cost_matrix = np.full((M, N), np.inf)

    # Calculate the cost for the first point
    cost_matrix[0, 0] = _euclidean_distance(s1[:, 0], s2[:, 0])

    # Calculate the costs for the first column (aligning s2's start with all of s1)
    for i in range(1, M):
        cost_matrix[i, 0] = cost_matrix[i-1, 0] + _euclidean_distance(s1[:, i], s2[:, 0])

    # Calculate the costs for the first row (aligning s1's start with all of s2)
    for j in range(1, N):
        cost_matrix[0, j] = cost_matrix[0, j-1] + _euclidean_distance(s1[:, 0], s2[:, j])

    # Populate the rest of the cost matrix
    # For each cell (i, j), the cost is the distance between point i and j plus the
    # minimum cost of the three adjacent cells: (i-1, j), (i, j-1), (i-1, j-1).
    for i in range(1, M):
        for j in range(1, N):
            min_prev_cost = min(cost_matrix[i-1, j],    # Insertion
                                cost_matrix[i, j-1],    # Deletion
                                cost_matrix[i-1, j-1])  # Match
            
            cost_matrix[i, j] = _euclidean_distance(s1[:, i], s2[:, j]) + min_prev_cost

    # The final DTW distance is the cost in the top-right corner of the matrix
    return cost_matrix[-1, -1]

# Example usage for testing the function
if __name__ == '__main__':
    # Create two simple, similar curves for demonstration
    # Curve 1: A simple line
    strain1 = np.linspace(0, 1, 100)
    stress1 = 2 * strain1
    curve1 = np.array([strain1, stress1])

    # Curve 2: A similar line, but slightly shifted and with different length
    strain2 = np.linspace(0.1, 1.1, 120)
    stress2 = 2 * strain2 - 0.1
    curve2 = np.array([strain2, stress2])
    
    # Curve 3: A very different curve
    strain3 = np.linspace(0, 1, 100)
    stress3 = 1 - strain1
    curve3 = np.array([strain3, stress3])

    # Calculate DTW distances
    distance_1_2 = dtw_distance(curve1, curve2)
    distance_1_3 = dtw_distance(curve1, curve3)

    print("--- Testing loss_functions.py ---")
    print(f"DTW distance between two similar curves (should be small): {distance_1_2:.4f}")
    print(f"DTW distance between two different curves (should be large): {distance_1_3:.4f}")

    # Visualize the test curves
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8, 6))
    plt.plot(curve1[0], curve1[1], label='Curve 1 (Reference)')
    plt.plot(curve2[0], curve2[1], label='Curve 2 (Similar)', linestyle='--')
    plt.plot(curve3[0], curve3[1], label='Curve 3 (Different)', linestyle=':')
    plt.title('Test Curves for DTW Function')
    plt.xlabel('Strain')
    plt.ylabel('Stress')
    plt.legend()
    plt.grid(True)
    plt.show()
