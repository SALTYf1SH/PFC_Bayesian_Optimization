# -*- coding: utf-8 -*-
"""
PFC Simulation Server (FINAL - With Acknowledgment)

This script runs *inside* the Itasca PFC application and acts as a server.
It now sends an immediate acknowledgment message (ACK) upon receiving a task,
allowing the client to know the task has been accepted before the long
computation begins. This is the definitive, fully corrected version incorporating
all best practices and fixes identified.
"""

import os
import sys
import json
import socket

try:
    import itasca as it
except ImportError:
    print("[FATAL] This script must be run within the PFC application environment.")
    sys.exit(1)

# --- Server Configuration ---
HOST = '127.0.0.1'
PORT = 50002 

def _run_single_simulation(params):
    """
    Executes a single, complete PFC simulation from sample generation to testing.
    This is the core function called by the server for each parameter set.

    Args:
        params (dict): A dictionary of micro-parameters sent by the optimization client.

    Returns:
        dict: A dictionary containing the 'Strain' and 'Stress' data lists.
              Returns a dictionary with empty lists if the simulation fails.
    """
    # Use an absolute path for the temporary file to avoid directory issues.
    history_filename = os.path.join(os.getcwd(), "temp_server_history.txt")
    
    try:
        # --- Set Micro-parameters ---
        emod = params.get('emod', 1e10)
        kratio = params.get('kratio', 2.0)
        pb_emod = params.get('pb_emod', 5e10)
        pb_kratio = params.get('pb_kratio', kratio)
        pb_fric = params.get('pb_fric', 0.5)
        pb_coh = params.get('pb_coh', 5e7)
        pb_ten = params.get('pb_ten', 5e7)
        
        # --- Path Configuration ---
        project_root = os.getcwd()
        model_dir = os.path.join(project_root, "pfc_model")
        ss_wall_path = os.path.join(model_dir, "ss_wall.fis").replace('\\', '/')
        fracture_path = os.path.join(model_dir, "fracture.p2fis").replace('\\', '/')

        # ======================================================================
        # --- STAGE 1 & 2: Create, Compact, and Bond the Specimen ---
        # ======================================================================
        print("  STAGE 1 & 2: Creating and bonding the specimen...")
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
        # --- STAGE 3: Run Compression Test and Record Histories ---
        # ======================================================================
        print("  STAGE 3: Starting compression test...")
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
        
        # Export history data AFTER the solve is complete.
        pfc_safe_path = history_filename.replace('\\', '/')
        it.command(f"history export 1 2 file '{pfc_safe_path}'")

        # ======================================================================
        # --- STAGE 4: Read Data from the Exported File using Pure Python ---
        # ======================================================================
        print(f"  Reading data from exported file: '{history_filename}'")
        strain_list = []
        stress_list = []
        try:
            with open(history_filename, 'r') as f:
                for line in f:
                    try:
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            strain = abs(float(parts[1]))
                            strain = abs(float(parts[1]))
                            stress_pa = abs(float(parts[2]))
                            stress_mpa = stress_pa / 1e6
                            strain_list.append(strain)
                            stress_list.append(stress_mpa)
                    except (ValueError, IndexError):
                        # Gracefully skip non-numeric header lines
                        continue
            
            if strain_list and stress_list:
                return {'Strain': strain_list, 'Stress': stress_list}
        except Exception as file_error:
            print(f"  [ERROR] Could not read or parse history file: {file_error}")

    except Exception as e:
        print(f"[PFC ERROR] An exception occurred during the simulation: {e}")
    finally:
        # Ensure the temporary file is cleaned up
        if os.path.exists(history_filename):
            os.remove(history_filename)
    
    return {'Strain': [], 'Stress': []}


def start_blocking_server():
    """
    Initializes and runs the main blocking server loop. Now sends an ACK.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"--- PFC Server started on {HOST}:{PORT} ---")
        
        while True:
            print("\nWaiting for a client connection...")
            conn, addr = server_socket.accept()
            
            with conn:
                print(f"Accepted connection from {addr}")
                data = conn.recv(4096)
                if not data:
                    print("Connection closed without data.")
                    continue

                # 1. Immediately send acknowledgment message
                conn.sendall(b'ACK_RECEIVED')
                print("  Acknowledgment sent. Starting simulation...")

                # 2. Decode parameters and start the long computation
                params = json.loads(data.decode('utf-8'))
                print(f"Received parameters: {params}")
                
                results_dict = _run_single_simulation(params)
                
                # 3. Send the final results
                results_json = json.dumps(results_dict)
                print("Simulation finished. Sending results...")
                
                conn.sendall(results_json.encode('utf-8'))
                print("Results sent. Closing connection.")
    finally:
        print("\n--- Server is shutting down. ---")
        server_socket.close()

if __name__ == '__main__':
    start_blocking_server()
