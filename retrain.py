"""
retrain.py

Retraining server for the federated IDS project.

Features:
- Mirrors server.py architecture: maintains global model + label encoder.
- Accepts aggregated model updates (coef_, intercept_) from clients (e.g., saved in files).
- Aggregates client updates using weighted averaging (by sample count).
- Expands model to accommodate new classes discovered during federated rounds.
- Persists model and label encoder with timestamped backups.
- Scheduled retraining loop: runs aggregation every N days (default 3).
- Supports --once for single run and --interval-days N for custom intervals.

Usage examples:
  python retrain.py --once
  python retrain.py              # runs and then sleeps 3 days between aggregation
  python retrain.py --interval-days 7 --client-dir models/client_updates
"""

import os
import sys
import time
import json
import glob
import joblib
import argparse
import subprocess
import psutil
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder

# ---------- CONFIG (consistent with server.py) ----------
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "network_sgd_classifier.joblib")
LE_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")
FEATURE_COUNT = 13
NUM_ROUNDS = 3
NUM_CLIENTS = 2
SERVER_ADDRESS = "0.0.0.0:8080"
CSV_GLOB_PATTERN = "dataset/**/*.csv"
CLIENT_MODELS_DIR = "models/client_updates"  # where client updates are saved
# --------------------------------------------------------

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(CLIENT_MODELS_DIR, exist_ok=True)


def build_or_load_label_encoder(csv_pattern=CSV_GLOB_PATTERN):
    """Load existing LE or scan CSVs to build classes."""
    if os.path.exists(LE_PATH):
        le = joblib.load(LE_PATH)
        classes_list = list(le.classes_)
        if "Unknown" not in classes_list:
            classes_list.append("Unknown")
            le.classes_ = np.array(classes_list)
            joblib.dump(le, LE_PATH)
            print(f"[INFO] Appended 'Unknown' to existing label encoder and saved to {LE_PATH}")
        print(f"[INFO] Loaded existing label encoder with classes: {list(le.classes_)}")
        return le

    # Build new label encoder by scanning dataset CSVs
    all_labels = set()
    csv_files = glob.glob(csv_pattern, recursive=True)
    if not csv_files:
        print(f"[WARNING] No CSV files found matching '{csv_pattern}'. Using default classes.")
        le = LabelEncoder()
        le.classes_ = np.array(["Benign", "Attack", "Unknown"])
        joblib.dump(le, LE_PATH)
        print(f"[INFO] Saved label encoder to {LE_PATH}")
        return le

    print(f"[INFO] Scanning {len(csv_files)} CSV files for unique labels...")
    for csv_file in csv_files:
        try:
            chunks = pd.read_csv(csv_file, chunksize=50000, usecols=["label"], low_memory=False)
            for chunk in chunks:
                if "label" in chunk.columns:
                    all_labels.update([str(x).strip() for x in chunk["label"].unique() if pd.notna(x)])
        except Exception as e:
            print(f"[WARNING] Could not read {csv_file}: {e}")

    unique_labels = sorted(list(all_labels))
    if "Unknown" not in unique_labels:
        unique_labels.append("Unknown")

    if len(unique_labels) == 0:
        print("[WARNING] No labels found in CSV files. Using default classes.")
        le = LabelEncoder()
        le.classes_ = np.array(["Benign", "Attack", "Unknown"])
    else:
        le = LabelEncoder()
        le.classes_ = np.array(unique_labels)
        print(f"[INFO] Auto-detected {len(unique_labels)} classes:")
        for i, cls in enumerate(unique_labels, 1):
            print(f"      {i:2d}. {cls}")

    joblib.dump(le, LE_PATH)
    print(f"[INFO] Saved label encoder to {LE_PATH}")
    return le


def build_or_load_model(le):
    """Create or load initial model matching label encoder classes."""
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        print(f"[INFO] Loaded initial model from {MODEL_PATH}")
        # Adjust model if class count doesn't match
        if model.coef_.shape[0] != len(le.classes_):
            print("[INFO] Adjusting loaded model to match current label encoder class count...")
            n_old = model.coef_.shape[0]
            n_new = len(le.classes_)
            n_features = model.coef_.shape[1]
            new_coef = np.zeros((n_new, n_features), dtype=np.float64)
            new_intercept = np.zeros((n_new,), dtype=np.float64)
            new_coef[:n_old, :] = model.coef_
            new_intercept[:n_old] = model.intercept_
            model.coef_ = new_coef
            model.intercept_ = new_intercept
            joblib.dump(model, MODEL_PATH)
            print(f"[INFO] Expanded and saved model to {MODEL_PATH} to have {n_new} classes.")
        return model

    # Create fresh model
    model = SGDClassifier(loss="log_loss", max_iter=1, tol=None, warm_start=True, random_state=42)
    dummy_X = np.zeros((1, FEATURE_COUNT))
    dummy_y = np.array([0])
    model.partial_fit(dummy_X, dummy_y, classes=np.arange(len(le.classes_)))
    joblib.dump(model, MODEL_PATH)
    print(f"[INFO] Created and saved initial model to {MODEL_PATH}")
    return model


def get_model_parameters(m):
    """Extract coef and intercept as float32."""
    return [m.coef_.astype(np.float32), m.intercept_.astype(np.float32)]


def load_client_updates(client_dir=CLIENT_MODELS_DIR):
    """
    Load client model updates from saved files.
    Expected format: each client saves {coef, intercept, n_samples} as JSON or joblib.
    Returns list of tuples: (coef, intercept, n_samples)
    """
    updates = []
    if not os.path.exists(client_dir):
        print(f"[WARNING] Client directory '{client_dir}' does not exist. No updates to load.")
        return updates

    # Look for client update files (can be .joblib or .json)
    client_files = glob.glob(os.path.join(client_dir, "client_*_update.*"))
    print(f"[INFO] Found {len(client_files)} client update files in {client_dir}")

    for fname in sorted(client_files):
        try:
            if fname.endswith(".joblib"):
                data = joblib.load(fname)
                coef = np.asarray(data.get("coef", None), dtype=np.float64)
                intercept = np.asarray(data.get("intercept", None), dtype=np.float64)
                n_samples = int(data.get("n_samples", 1))
                if coef.size > 0 and intercept.size > 0:
                    updates.append((coef, intercept, n_samples))
                    print(f"[INFO] Loaded update from {fname}: shape={coef.shape}, n_samples={n_samples}")
            elif fname.endswith(".json"):
                with open(fname, "r") as f:
                    data = json.load(f)
                coef = np.asarray(data.get("coef", []), dtype=np.float64)
                intercept = np.asarray(data.get("intercept", []), dtype=np.float64)
                n_samples = int(data.get("n_samples", 1))
                if coef.size > 0 and intercept.size > 0:
                    updates.append((coef, intercept, n_samples))
                    print(f"[INFO] Loaded update from {fname}: shape={coef.shape}, n_samples={n_samples}")
        except Exception as e:
            print(f"[WARNING] Failed to load client update {fname}: {e}")

    return updates


def aggregate_client_updates(updates, model, le):
    """
    Aggregate client updates using weighted averaging.
    Returns aggregated (coef, intercept) or None if no valid updates.
    """
    if not updates:
        print("[INFO] No client updates to aggregate.")
        return None

    # Validate and collect updates
    valid_updates = []
    total_samples = 0
    for coef, intercept, n_samples in updates:
        # Check shape compatibility
        if coef.shape[1] != model.coef_.shape[1]:
            print(f"[WARNING] Client update coef has {coef.shape[1]} features, expected {model.coef_.shape[1]}. Skipping.")
            continue
        # Expand if client has fewer classes than server
        if coef.shape[0] < model.coef_.shape[0]:
            n_new = model.coef_.shape[0]
            n_features = coef.shape[1]
            expanded_coef = np.zeros((n_new, n_features), dtype=np.float64)
            expanded_intercept = np.zeros((n_new,), dtype=np.float64)
            expanded_coef[:coef.shape[0], :] = coef
            expanded_intercept[:intercept.shape[0]] = intercept
            coef = expanded_coef
            intercept = expanded_intercept
        valid_updates.append((coef, intercept, n_samples))
        total_samples += n_samples

    if not valid_updates:
        print("[WARNING] No valid client updates after compatibility checks.")
        return None

    # Weighted average
    print(f"[INFO] Aggregating {len(valid_updates)} client updates (total {total_samples} samples)...")
    agg_coef = np.zeros_like(valid_updates[0][0], dtype=np.float64)
    agg_intercept = np.zeros_like(valid_updates[0][1], dtype=np.float64)

    for coef, intercept, n_samples in valid_updates:
        weight = float(n_samples) / float(total_samples)
        agg_coef += weight * coef
        agg_intercept += weight * intercept

    return agg_coef, agg_intercept


def kill_server_process(server_script=None):
    """
    Kill the Flower server process by searching for 'server.py' in running processes.
    If server_script is provided, use it to find the specific process.
    """
    try:
        target_name = os.path.basename(server_script) if server_script else "server.py"
        killed = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any(target_name in arg for arg in cmdline):
                    print(f"[RETRAIN] Killing server process with PID {proc.pid}")
                    proc.terminate()
                    proc.wait(timeout=5)
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
        if killed:
            print("[RETRAIN] Server process killed successfully.")
            time.sleep(2)  # Wait a bit for cleanup
            return True
        else:
            print("[RETRAIN] No server process found to kill.")
            return False
    except Exception as e:
        print(f"[RETRAIN] Warning: Failed to kill server process: {e}")
        return False


def restart_server_process(server_script):
    """
    Restart the Flower server by running server.py as a new subprocess.
    """
    try:
        if not os.path.exists(server_script):
            print(f"[RETRAIN] Error: Server script not found at {server_script}")
            return False
        
        print(f"[RETRAIN] Restarting server from {server_script}...")
        # Start server in background without capturing output
        server_process = subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"[RETRAIN] Server restarted with PID {server_process.pid}")
        time.sleep(3)  # Wait for server to initialize
        return True
    except Exception as e:
        print(f"[RETRAIN] Error: Failed to restart server: {e}")
        return False


def wait_for_client_updates(client_dir=CLIENT_MODELS_DIR, timeout_seconds=600, check_interval=5):
    """
    Wait for new client updates to arrive after cool down.
    Returns True if updates found, False if timeout.
    """
    print(f"[RETRAIN] Waiting for client updates (timeout: {timeout_seconds}s, check every {check_interval}s)...")
    elapsed = 0
    while elapsed < timeout_seconds:
        try:
            client_files = glob.glob(os.path.join(client_dir, "client_*_update.*"))
            if client_files:
                print(f"[RETRAIN] Found {len(client_files)} client update file(s)! Proceeding with aggregation.")
                return True
            if elapsed % 30 == 0:  # Log every 30 seconds
                print(f"[RETRAIN] Waiting for updates... ({elapsed}s / {timeout_seconds}s)")
            time.sleep(check_interval)
            elapsed += check_interval
        except Exception as e:
            print(f"[RETRAIN] Error checking for updates: {e}")
            time.sleep(check_interval)
            elapsed += check_interval
    
    print(f"[RETRAIN] Timeout waiting for client updates ({timeout_seconds}s). Skipping aggregation this cycle.")
    return False


def retrain_aggregation_round(model, le, client_dir=CLIENT_MODELS_DIR):
    """
    Perform one aggregation round:
    1. Load client updates
    2. Aggregate them (weighted average)
    3. Update global model
    4. Persist model and label encoder
    """
    print("[INFO] === Starting aggregation round ===")
    
    # Load client updates
    updates = load_client_updates(client_dir)
    
    # Aggregate
    aggregated = aggregate_client_updates(updates, model, le)
    if aggregated is None:
        print("[INFO] Aggregation produced no updates. Model unchanged.")
        return False

    agg_coef, agg_intercept = aggregated

    # Update global model
    try:
        model.coef_ = agg_coef
        model.intercept_ = agg_intercept
    except Exception as e:
        print(f"[ERROR] Failed to update model weights: {e}")
        return False

    # Persist model
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    try:
        joblib.dump(model, MODEL_PATH)
        backup_fname = os.path.join(MODEL_DIR, f"network_sgd_classifier_aggregated_{ts}.joblib")
        joblib.dump(model, backup_fname)
        print(f"[INFO] Saved aggregated model to {MODEL_PATH} and backup {backup_fname}")
    except Exception as e:
        print(f"[ERROR] Failed to save model: {e}")
        return False

    try:
        joblib.dump(le, LE_PATH)
        le_backup = os.path.join(MODEL_DIR, f"label_encoder_aggregated_{ts}.joblib")
        joblib.dump(le, le_backup)
        print(f"[INFO] Saved label encoder to {LE_PATH} and backup {le_backup}")
    except Exception as e:
        print(f"[ERROR] Failed to save label encoder: {e}")

    print("[INFO] === Aggregation round complete ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Retrain/aggregate model from federated client updates on a schedule.")
    parser.add_argument("--once", action="store_true", help="Run aggregation once and exit.")
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=1.0,  # 1 minute cool down
        help="Minutes cool down before waiting for client updates (default: 1).",
    )
    parser.add_argument(
        "--interval-days",
        type=float,
        default=None,
        help="(DEPRECATED) Days between aggregation runs. Use --interval-minutes instead.",
    )
    parser.add_argument(
        "--client-dir",
        type=str,
        default=CLIENT_MODELS_DIR,
        help="Directory where client model updates are saved.",
    )
    parser.add_argument(
        "--csv-pattern",
        type=str,
        default=CSV_GLOB_PATTERN,
        help="Glob pattern to find CSV files (for initializing label encoder).",
    )
    parser.add_argument(
        "--server-script",
        type=str,
        default="server.py",
        help="Path to server.py script to restart after aggregation.",
    )
    parser.add_argument(
        "--restart-server",
        action="store_true",
        help="Enable server restart after each aggregation round.",
    )
    args = parser.parse_args()

    # Handle deprecated --interval-days parameter
    if args.interval_days is not None:
        interval_minutes = args.interval_days * 24 * 60  # Convert days to minutes
        print(f"[RETRAIN] Note: Using deprecated --interval-days. Converting {args.interval_days} days to {interval_minutes} minutes.")
    else:
        interval_minutes = args.interval_minutes

    interval_seconds = max(0.0, float(interval_minutes)) * 60.0

    # Initialize label encoder and model
    le = build_or_load_label_encoder(args.csv_pattern)
    model = build_or_load_model(le)

    try:
        while True:
            # Cool down period
            print(
                f"[RETRAIN] Cool down for {interval_minutes} minute(s) ({int(interval_seconds)} seconds)...\n"
            )
            try:
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("[RETRAIN] Interrupted during cooldown — exiting.")
                break
            
            # Wait for client updates to arrive
            print("[RETRAIN] Cool down complete. Now waiting for client model updates...\n")
            updates_found = wait_for_client_updates(
                client_dir=args.client_dir,
                timeout_seconds=600,  # 10 minute timeout
                check_interval=5  # Check every 5 seconds
            )
            
            if not updates_found:
                print("[RETRAIN] No client updates received. Skipping aggregation and restarting server...\n")
                # Still restart server to allow new training round
                if args.restart_server:
                    print("[RETRAIN] Restarting Flower server to accept new client connections...")
                    kill_server_process(args.server_script)
                    restart_server_process(args.server_script)
                continue
            
            start = datetime.utcnow()
            print(f"[RETRAIN] Starting aggregation round at {start.isoformat()}")
            try:
                retrain_aggregation_round(model, le, client_dir=args.client_dir)
                
                # Restart server after aggregation if enabled
                if args.restart_server:
                    print("[RETRAIN] Restarting Flower server after aggregation...")
                    kill_server_process(args.server_script)
                    restart_server_process(args.server_script)
                    
            except Exception as e:
                print(f"[ERROR] Aggregation round failed: {e}")

            if args.once:
                print("[RETRAIN] --once flag set, exiting after single run.")
                break

            # Check interval
            if interval_seconds <= 0:
                print("[RETRAIN] interval-minutes <= 0, exiting after single run.")
                break

    except KeyboardInterrupt:
        print("[RETRAIN] Interrupted by user — exiting.")


if __name__ == "__main__":
    main()
