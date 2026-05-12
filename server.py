# server.py
import os
import sys
import joblib
import json
import glob
import subprocess
import threading
import numpy as np
import pandas as pd
import flwr as fl
from flask import Flask, request, jsonify
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from flwr.common import parameters_to_ndarrays, ndarrays_to_parameters

# ---------- CONFIG ----------
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "network_sgd_classifier.joblib")
LE_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")
FEATURE_COUNT = 13
NUM_ROUNDS = 1  # Run 1 round per server startup
NUM_CLIENTS = 2
SERVER_ADDRESS = "0.0.0.0:8080"
CSV_GLOB_PATTERN = "dataset/**/*.csv"  # adjust to your dataset layout
CLIENT_UPDATES_DIR = "models/client_updates"  # where server stores client updates
HTTP_PORT = 5000  # Flask server port for client uploads
# ----------------------------

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(CLIENT_UPDATES_DIR, exist_ok=True)

# Load or build label encoder (auto-detect labels). Ensure "Unknown" exists.
if os.path.exists(LE_PATH):
    le = joblib.load(LE_PATH)
    # ensure Unknown exists
    classes_list = list(le.classes_)
    if "Unknown" not in classes_list:
        classes_list.append("Unknown")
        le.classes_ = np.array(classes_list)
        joblib.dump(le, LE_PATH)
        print(
            f"[INFO] Appended 'Unknown' to existing label encoder and saved to {LE_PATH}"
        )
    print(f"[INFO] Loaded existing label encoder with classes: {list(le.classes_)}")
else:
    le = LabelEncoder()
    all_labels = set()
    csv_files = glob.glob(CSV_GLOB_PATTERN, recursive=True)
    if not csv_files:
        print(
            f"[WARNING] No CSV files found matching '{CSV_GLOB_PATTERN}'. Using default classes."
        )
        le.classes_ = np.array(["Benign", "Attack", "Unknown"])
    else:
        print(f"[INFO] Scanning {len(csv_files)} CSV files for all unique labels...")
        for csv_file in csv_files:
            try:
                chunks = pd.read_csv(
                    csv_file, chunksize=50000, usecols=["label"], low_memory=False
                )
                for chunk in chunks:
                    if "label" in chunk.columns:
                        all_labels.update(
                            [
                                str(x).strip()
                                for x in chunk["label"].unique()
                                if pd.notna(x)
                            ]
                        )
            except Exception as e:
                print(f"[WARNING] Could not read {csv_file}: {e}")

        unique_labels = sorted(list(all_labels))
        # always ensure Unknown is included
        if "Unknown" not in unique_labels:
            unique_labels.append("Unknown")

        if len(unique_labels) == 0:
            print("[WARNING] No labels found in CSV files. Using default classes.")
            le.classes_ = np.array(["Benign", "Attack", "Unknown"])
        else:
            le.classes_ = np.array(unique_labels)
            print(f"[INFO] Auto-detected {len(unique_labels)} classes:")
            for i, cls in enumerate(unique_labels, 1):
                print(f"      {i:2d}. {cls}")

    joblib.dump(le, LE_PATH)
    print(f"[INFO] Saved label encoder to {LE_PATH}")

# Create or load initial model (ensure it matches le.classes_ length)
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    print(f"[INFO] Loaded initial model from {MODEL_PATH}")
    # If model has fewer/more classes than le, expand or trim accordingly
    if model.coef_.shape[0] != len(le.classes_):
        print(
            "[INFO] Adjusting loaded model to match current label encoder class count..."
        )
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
        print(
            f"[INFO] Expanded and saved model to {MODEL_PATH} to have {n_new} classes."
        )
else:
    model = SGDClassifier(
        loss="log_loss", max_iter=1, tol=None, warm_start=True, random_state=42
    )
    dummy_X = np.zeros((1, FEATURE_COUNT))
    dummy_y = np.array([0])
    model.partial_fit(dummy_X, dummy_y, classes=np.arange(len(le.classes_)))
    joblib.dump(model, MODEL_PATH)
    print(f"[INFO] Created and saved initial model to {MODEL_PATH}")


def get_model_parameters(m):
    return [m.coef_.astype(np.float32), m.intercept_.astype(np.float32)]


initial_parameters = ndarrays_to_parameters(get_model_parameters(model))


class LoggingFedAvg(fl.server.strategy.FedAvg):
    def __init__(
        self,
        *args,
        model_obj=None,
        model_dir=MODEL_DIR,
        initial_ndarrays=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.model_obj = model_obj
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self._last_ndarrays = (
            initial_ndarrays
            if initial_ndarrays is not None
            else parameters_to_ndarrays(initial_parameters)
        )

    def _make_config(self, server_round):
        return {
            "rnd": server_round,
            "classes_json": json.dumps(list(le.classes_)),
            "n_features": int(self.model_obj.coef_.shape[1]),
        }

    def configure_fit(self, server_round, parameters, client_manager):
        config = self._make_config(server_round)
        fit_ins = fl.common.FitIns(parameters, config)
        clients = client_manager.sample(
            num_clients=self.min_fit_clients, min_num_clients=self.min_available_clients
        )
        return [(client, fit_ins) for client in clients]

    def configure_evaluate(self, server_round, parameters, client_manager):
        config = self._make_config(server_round)
        evaluate_ins = fl.common.EvaluateIns(parameters, config)
        clients = client_manager.sample(
            num_clients=self.min_evaluate_clients,
            min_num_clients=self.min_available_clients,
        )
        return [(client, evaluate_ins) for client in clients]

    def aggregate_fit(self, server_round, results, failures):
        n_clients = len(results)
        print(
            f"[Server] aggregate_fit called for round {server_round} with {n_clients} client updates (failures={len(failures)})"
        )
        if failures:
            print("[Server] Failures details:")
            for i, f in enumerate(failures):
                try:
                    print(f"  Failure #{i}: {repr(f)}")
                except Exception:
                    print(f"  Failure #{i}: (couldn't repr the failure)")

        # 1) Collect any new-classes reported by clients in this round
        reported_new = set()
        for _, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics:
                # metric value might be a dict-like with strings or bytes
                try:
                    # Metrics may be dict or bytes; handle both
                    if isinstance(metrics, dict) and "new_classes_json" in metrics:
                        val = metrics["new_classes_json"]
                        if isinstance(val, (bytes, bytearray)):
                            val = val.decode()
                        reported = json.loads(val)
                        reported_new.update([str(x).strip() for x in reported])
                    # Sometimes metrics could be protobuf/other type; attempt safe decode
                except Exception as e:
                    print(
                        f"[Server] Warning: failed to parse new_classes_json from client metrics: {e}"
                    )

        # 2) Aggregate updates from clients (this uses the server's current parameter shape)
        aggregated = super().aggregate_fit(server_round, results, failures)
        if aggregated is None:
            print(
                "[Server] No aggregated parameters returned (None). Skipping persistence for this round."
            )
            return None

        # Extract aggregated parameters (Parameters or (Parameters, ...))
        if isinstance(aggregated, tuple) and len(aggregated) >= 1:
            aggregated_params = aggregated[0]
            aggregated_aux = aggregated[1:]
        else:
            aggregated_params = aggregated
            aggregated_aux = None

        try:
            new_ndarrays = parameters_to_ndarrays(aggregated_params)
        except Exception as e:
            print(f"[Server] ERROR converting aggregated params to ndarrays: {e}")
            return aggregated

        # 3) If clients reported new labels, update server label encoder and expand the global model
        if reported_new:
            print(
                f"[Server] Clients reported new classes: {sorted(list(reported_new))}"
            )
            # Merge current classes with reported new ones (preserve existing order)
            current = list(le.classes_)
            for cls in sorted(reported_new):
                if cls not in current:
                    current.append(cls)
            le.classes_ = np.array(current)
            try:
                joblib.dump(le, LE_PATH)
                print(
                    f"[Server] Updated label encoder saved with {len(le.classes_)} classes."
                )
            except Exception as e:
                print(f"[Server] WARNING: failed to save updated label encoder: {e}")

            # Expand aggregated arrays (coef, intercept) with zero rows for new classes
            try:
                old_coef_arr, old_intercept_arr = new_ndarrays
                old_n_classes = int(old_coef_arr.shape[0])
                new_n_classes = len(le.classes_)
                n_features = int(old_coef_arr.shape[1])

                if new_n_classes > old_n_classes:
                    expanded_coef = np.zeros(
                        (new_n_classes, n_features), dtype=np.float64
                    )
                    expanded_intercept = np.zeros((new_n_classes,), dtype=np.float64)
                    expanded_coef[:old_n_classes, :] = np.asarray(
                        old_coef_arr, dtype=np.float64
                    )
                    expanded_intercept[:old_n_classes] = np.asarray(
                        old_intercept_arr, dtype=np.float64
                    )

                    # Persist expanded model state to self.model_obj and disk
                    if self.model_obj is not None:
                        self.model_obj.coef_ = expanded_coef
                        self.model_obj.intercept_ = expanded_intercept
                        fname = os.path.join(
                            self.model_dir,
                            f"network_sgd_classifier_round{server_round}_expanded.joblib",
                        )
                        joblib.dump(self.model_obj, fname)
                        print(f"[Server] Expanded model saved to: {fname}")
                    else:
                        fname = os.path.join(
                            self.model_dir, f"params_round{server_round}_expanded.npz"
                        )
                        np.savez(fname, expanded_coef, expanded_intercept)
                        print(f"[Server] Saved expanded ndarray params to: {fname}")

                    # Replace new_ndarrays with expanded versions for diffs/persistence and next-round broadcasting
                    new_ndarrays = [expanded_coef, expanded_intercept]
                    # Build aggregated_params to return (Parameters with expanded shape)
                    aggregated_params = ndarrays_to_parameters(
                        [
                            expanded_coef.astype(np.float32),
                            expanded_intercept.astype(np.float32),
                        ]
                    )
                else:
                    # No expansion needed; keep aggregated as is
                    if self.model_obj is not None:
                        self.model_obj.coef_ = np.asarray(
                            old_coef_arr, dtype=np.float64
                        )
                        self.model_obj.intercept_ = np.asarray(
                            old_intercept_arr, dtype=np.float64
                        )
                        fname = os.path.join(
                            self.model_dir,
                            f"network_sgd_classifier_round{server_round}.joblib",
                        )
                        joblib.dump(self.model_obj, fname)
                        print(f"[Server] Saved aggregated model to: {fname}")
            except Exception as e:
                print(f"[Server] Error expanding/persisting model for new classes: {e}")
                # fallback: try to persist unexpanded result
                try:
                    coef_arr, intercept_arr = new_ndarrays
                    if self.model_obj is not None:
                        self.model_obj.coef_ = np.asarray(coef_arr, dtype=np.float64)
                        self.model_obj.intercept_ = np.asarray(
                            intercept_arr, dtype=np.float64
                        )
                        joblib.dump(
                            self.model_obj,
                            os.path.join(
                                self.model_dir,
                                f"network_sgd_classifier_round{server_round}_fallback.joblib",
                            ),
                        )
                except Exception:
                    pass
        else:
            # no new classes reported: persist aggregated model normally
            try:
                coef_arr, intercept_arr = new_ndarrays
                if self.model_obj is not None:
                    self.model_obj.coef_ = np.asarray(coef_arr, dtype=np.float64)
                    self.model_obj.intercept_ = np.asarray(
                        intercept_arr, dtype=np.float64
                    )
                    fname = os.path.join(
                        self.model_dir,
                        f"network_sgd_classifier_round{server_round}.joblib",
                    )
                    joblib.dump(self.model_obj, fname)
                    print(f"[Server] Saved aggregated model to: {fname}")
                else:
                    fname = os.path.join(
                        self.model_dir, f"params_round{server_round}.npz"
                    )
                    np.savez(fname, *new_ndarrays)
                    print(f"[Server] Saved aggregated ndarray params to: {fname}")
            except Exception as e:
                print(f"[Server] WARNING: failed to persist aggregated model: {e}")

        # Diagnostic diffs
        try:
            for i, (prev, new) in enumerate(zip(self._last_ndarrays, new_ndarrays)):
                prev_arr = np.asarray(prev, dtype=np.float64)
                new_arr = np.asarray(new, dtype=np.float64)
                diff = new_arr - prev_arr
                l2 = float(np.linalg.norm(diff))
                max_abs = float(np.max(np.abs(diff)))
                print(
                    f"[Server] param #{i}: L2-change={l2:.6e}, max-abs-change={max_abs:.6e}"
                )
        except Exception as e:
            print(f"[Server] Warning computing diffs: {e}")

        # Update last ndarrays so next round uses updated params
        self._last_ndarrays = [np.asarray(a, dtype=np.float64) for a in new_ndarrays]

        # Return aggregated params (Parameters object) — aggregated_params already adjusted above when expanded
        # If we have auxiliary outputs from parent, preserve them
        if aggregated_aux:
            return (aggregated_params, *aggregated_aux)
        return aggregated_params


# ---------- Flask app for receiving client model updates ----------
app = Flask(__name__)


@app.route("/upload_client_update", methods=["POST"])
def upload_client_update():
    """
    Endpoint for clients to upload model updates.
    Expected JSON: {"client_id": "...", "coef": [...], "intercept": [...], "n_samples": int}
    """
    try:
        data = request.get_json()
        client_id = data.get("client_id", "unknown")
        coef = np.array(data.get("coef", []), dtype=np.float64)
        intercept = np.array(data.get("intercept", []), dtype=np.float64)
        n_samples = int(data.get("n_samples", 1))

        if coef.size == 0 or intercept.size == 0:
            return jsonify({"status": "error", "message": "Invalid coef or intercept"}), 400

        # Save update to server's CLIENT_UPDATES_DIR
        update_data = {"coef": coef, "intercept": intercept, "n_samples": n_samples}
        fname = os.path.join(CLIENT_UPDATES_DIR, f"client_{client_id}_update.joblib")
        joblib.dump(update_data, fname)
        print(f"[HTTP] Received and saved client update from {client_id}: {fname}")
        return jsonify({"status": "success", "message": f"Update saved for client {client_id}"}), 200

    except Exception as e:
        print(f"[HTTP] Error receiving client update: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


def run_flask_server(port=HTTP_PORT):
    """Run Flask server in a thread."""
    print(f"[Flask] Starting HTTP server on port {port} for client updates...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


strategy = LoggingFedAvg(
    fraction_fit=1.0,
    fraction_evaluate=1.0,
    min_fit_clients=NUM_CLIENTS,
    min_evaluate_clients=NUM_CLIENTS,
    min_available_clients=NUM_CLIENTS,
    initial_parameters=initial_parameters,
    model_obj=model,
    initial_ndarrays=parameters_to_ndarrays(initial_parameters),
)

if __name__ == "__main__":
    # Start Flask HTTP server in background thread for client uploads
    print(f"[INFO] Starting Flask HTTP server on port {HTTP_PORT} for client model uploads...")
    flask_thread = threading.Thread(target=run_flask_server, args=(HTTP_PORT,), daemon=True)
    flask_thread.start()
    print(f"[INFO] Flask server running at http://0.0.0.0:{HTTP_PORT}")

    print(f"\nStarting Flower server at {SERVER_ADDRESS} for {NUM_ROUNDS} round ...")
    print(f"[Server] Waiting for {NUM_CLIENTS} client(s) to connect...")
    print("[Server] Please start your client(s) with: python client.py\n")
    
    fl.server.start_server(
        server_address=SERVER_ADDRESS,
        config=fl.server.ServerConfig(num_rounds=NUM_ROUNDS),
        strategy=strategy,
    )
    print("Flower server finished. Waiting for retrain process to aggregate and restart...")

    # Start retrain.py as background process for periodic aggregation with 1 minute cool down + wait for updates
    print("\n[INFO] Starting retrain.py in background for model aggregation (1 min cool down + wait for client updates)...")
    try:
        retrain_script = os.path.join(os.path.dirname(__file__), "retrain.py")
        if os.path.exists(retrain_script):
            # Start retrain.py with 1-minute cool down and server restart enabled
            # Don't capture output so we can see retrain logs in real-time
            retrain_process = subprocess.Popen(
                [sys.executable, retrain_script, "--interval-minutes", "1", "--restart-server"],
                # stdout and stderr not captured - displayed in console
            )
            print(f"[INFO] Retrain process started with PID {retrain_process.pid}")
            print("[INFO] Retrain.py will: cool down 1 min → wait for client updates → aggregate → restart server")
            print("[INFO] Retrain output will appear below this line:\n")
        else:
            print(f"[WARNING] retrain.py not found at {retrain_script}. Skipping retrain startup.")
    except Exception as e:
        print(f"[WARNING] Failed to start retrain.py: {e}")
        print("[INFO] You can manually run: python retrain.py --interval-minutes 1 --restart-server")

    # Keep server running
    print("\n[INFO] Server is running. Press Ctrl+C to stop.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")

