# client_fixed.py
import os
import json
import joblib
import numpy as np
import pandas as pd
import flwr as fl
import requests
import threading
import time
from datetime import datetime, timedelta
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss

# Directory to save model updates for retrain.py aggregation
CLIENT_UPDATES_DIR = "models/client_updates"
os.makedirs(CLIENT_UPDATES_DIR, exist_ok=True)

# Server configuration for sending updates
SERVER_HTTP_URL = "http://localhost:5000"  # Change to server IP if on different PC
SEND_UPDATES_EVERY_ROUND = True  # Send updates to server after EVERY training round (Day 1-2)
# Retrain will aggregate all accumulated updates on Day 3

FEATURE_COLS = [
    "frame.len",
    "ip.proto",
    "ip.checksum",
    "ip.tos",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.window_size_scalefactor",
    "tcp.checksum",
    "tcp.pdu.size",
    "udp.srcport",
    "udp.dstport",
]


def load_folder_csv(folder_path):
    all_dfs = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".csv"):
            path = os.path.join(folder_path, filename)
            try:
                # read with low_memory=False to avoid mixed-type warning
                df = pd.read_csv(path, low_memory=False)
                all_dfs.append(df)
                print(f"Loaded {filename} shape={df.shape}")
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
    if not all_dfs:
        raise ValueError("No CSV files found in the provided folder.")
    return pd.concat(all_dfs, ignore_index=True)


def ensure_feature_columns(df):
    # If columns are missing, create them filled with zeros (float)
    for c in FEATURE_COLS:
        if c not in df.columns:
            print(f"Warning: missing feature column '{c}' — filling with 0.0")
            df[c] = 0.0
    return df


def preprocess_features(df):
    # df expected to contain only FEATURE_COLS (or at least those columns present)
    X = df.copy()

    def conv(x):
        # Replace NaN / None / empty with 0.0
        if pd.isna(x):
            return 0.0
        # strings: try to parse hex like '0x1a' or numeric strings
        if isinstance(x, str):
            s = x.strip()
            if s == "":
                return 0.0
            if s.startswith("0x") or s.startswith("0X"):
                try:
                    return float(int(s, 16))
                except Exception:
                    return 0.0
            # try to remove extraneous characters (commas) then convert
            try:
                return float(s.replace(',', ''))
            except Exception:
                return 0.0
        # numeric types
        try:
            return float(x)
        except Exception:
            return 0.0

    for c in X.columns:
        X[c] = X[c].apply(conv)
    # ensure dtype is float64
    return X.astype(np.float64)


class NetworkTrafficClient(fl.client.NumPyClient):
    def __init__(self, folder_path):
        print("Initializing client...")
        self.df = load_folder_csv(folder_path)

        # If label column missing, create it with 'Unknown'
        if "label" not in self.df.columns:
            print("Warning: 'label' column missing in CSVs — filling with 'Unknown'")
            self.df["label"] = "Unknown"

        # Normalize missing labels to 'Unknown'
        def norm_label(x):
            if pd.isna(x):
                return "Unknown"
            s = str(x).strip()
            return s if s != "" else "Unknown"

        self.df["label"] = self.df["label"].apply(norm_label)

        # Ensure feature columns exist; if not, add them with zeros
        self.df = ensure_feature_columns(self.df)

        # Now create X and y
        self.X = preprocess_features(self.df[FEATURE_COLS])
        self.raw_labels = np.array([str(x).strip() for x in self.df["label"].values])

        self.model = None
        self.le = None
        self.initialized = False
        self._new_labels_local = []
        self.client_id = None  # Set by external code if needed
        self._last_update_time = None  # Track last update sent to server

    def _read_classes_from_config(self, config):
        if "classes_json" in config:
            try:
                cls_list = json.loads(config["classes_json"])
                # normalize strings
                cls_list = [str(x).strip() for x in cls_list]
                return np.array(cls_list)
            except Exception as e:
                print("Warning: failed to parse classes_json:", e)
                return None
        return None

    def save_model_update(self, n_samples):
        """
        Save model update (coef, intercept, n_samples) to CLIENT_UPDATES_DIR for retrain.py aggregation.
        Format: models/client_updates/client_{client_id}_update.joblib
        Also send to server HTTP endpoint every UPDATE_INTERVAL_DAYS.
        """
        try:
            if self.model is None:
                print("[Client] Warning: model is None, skipping update save.")
                return

            client_id = getattr(self, "client_id", None) or "default"
            update_data = {
                "coef": self.model.coef_.astype(np.float64),
                "intercept": self.model.intercept_.astype(np.float64),
                "n_samples": int(n_samples),
            }
            fname = os.path.join(CLIENT_UPDATES_DIR, f"client_{client_id}_update.joblib")
            joblib.dump(update_data, fname)
            print(f"[Client] Saved model update to {fname} (coef shape={self.model.coef_.shape}, n_samples={n_samples})")

            # Send to server EVERY ROUND (Day 1-2) if enabled
            if SEND_UPDATES_EVERY_ROUND:
                self._send_update_to_server(client_id, update_data)

        except Exception as e:
            print(f"[Client] Warning: failed to save model update: {e}")

    def _send_update_to_server(self, client_id, update_data):
        """
        Send model update to server HTTP endpoint.
        Converts numpy arrays to lists for JSON serialization.
        """
        try:
            # Convert numpy arrays to Python lists for JSON
            payload = {
                "client_id": str(client_id),
                "coef": update_data["coef"].tolist(),
                "intercept": update_data["intercept"].tolist(),
                "n_samples": int(update_data["n_samples"]),
            }
            response = requests.post(
                f"{SERVER_HTTP_URL}/upload_client_update",
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                print(f"[Client] Successfully sent update to server: {response.json()}")
            else:
                print(f"[Client] Server returned status {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            print(f"[Client] Warning: Could not connect to server at {SERVER_HTTP_URL}. Update saved locally only.")
        except Exception as e:
            print(f"[Client] Warning: Failed to send update to server: {e}")


    def get_parameters(self, config):
        if self.model is None:
            return [np.zeros((1, self.X.shape[1]), dtype=np.float32), np.zeros((1,), dtype=np.float32)]
        return [self.model.coef_.astype(np.float32), self.model.intercept_.astype(np.float32)]

    def set_parameters(self, parameters):
        coef, intercept = parameters
        coef_arr = np.array(coef, dtype=np.float64)
        intercept_arr = np.array(intercept, dtype=np.float64)
        # If model is not initialized yet, create one consistent with provided params
        if self.model is None:
            n_classes, n_features = coef_arr.shape
            self.model = SGDClassifier(
                loss="log_loss", max_iter=1, tol=None, warm_start=True, random_state=42
            )
            # dummy partial fit to initialize internal structures with the right classes
            self.model.partial_fit(
                np.zeros((1, n_features)), np.array([0]), classes=np.arange(n_classes)
            )
        # assign weights directly (override)
        self.model.coef_ = coef_arr
        self.model.intercept_ = intercept_arr

    def fit(self, parameters, config):
        print(
            ">>> fit() called by server. config keys:", list(config.keys())
        )
        try:
            classes_arr = self._read_classes_from_config(config)
            if classes_arr is None and self.le is None:
                raise ValueError(
                    "No classes provided via config and no local label encoder available."
                )

            # If client hasn't been initialized, set up label encoder and data splits now
            if not self.initialized:
                if classes_arr is not None:
                    # canonical classes from server (server should ensure 'Unknown' exists)
                    self.le = LabelEncoder()
                    self.le.classes_ = classes_arr
                elif self.le is None:
                    raise ValueError("No classes available for label encoding.")

                # Normalize labels (strip)
                raw_labels = np.array([str(x).strip() for x in self.raw_labels])

                # Detect unseen labels (relative to server classes)
                server_classes = set(self.le.classes_)
                unseen = sorted(list(set(raw_labels) - server_classes))
                if unseen:
                    print("Client discovered unseen labels:", unseen)
                self._new_labels_local = unseen

                # Map unseen labels to 'Unknown' for this round so we keep parameter shapes consistent
                if "Unknown" not in server_classes:
                    # Server is supposed to include 'Unknown' — if it doesn't, map to an existing class (last) as fallback
                    print(
                        "[Client] Warning: server classes do not include 'Unknown'. Mapping unseen labels to last server class as fallback."
                    )
                    fallback_label = list(self.le.classes_)[-1]
                    mapped = [lbl if lbl in server_classes else fallback_label for lbl in raw_labels]
                else:
                    mapped = [lbl if lbl in server_classes else "Unknown" for lbl in raw_labels]

                # transform labels (safe now)
                self.y = self.le.transform(mapped)

                # Split: try stratify; if stratify fails (very small classes), fall back without stratify
                X = self.X
                y = self.y
                try:
                    self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
                        X, y, test_size=0.2, random_state=42, stratify=y
                    )
                except Exception as e:
                    print("Warning: stratified split failed (probably rare classes). Falling back to random split.", e)
                    self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
                        X, y, test_size=0.2, random_state=42
                    )

                # initialize model (class count must equal len(self.le.classes_))
                n_features = int(config.get("n_features", self.X.shape[1]))
                self.model = SGDClassifier(
                    loss="log_loss",
                    max_iter=1,
                    tol=None,
                    warm_start=True,
                    random_state=42,
                )
                classes_idx = np.arange(len(self.le.classes_))
                # partial_fit with correct classes
                self.model.partial_fit(np.zeros((1, n_features)), np.array([0]), classes=classes_idx)
                self.initialized = True
                print("Client initialized inside fit(): data and model ready.")

            # Set server parameters (this will overwrite model weights to server's parameters)
            self.set_parameters(parameters)

            # Train locally
            X_train_arr = np.asarray(self.X_train, dtype=np.float64)
            y_train_arr = np.asarray(self.y_train, dtype=np.int64)
            print(f"Training locally on {len(X_train_arr)} examples...")
            self.model.partial_fit(X_train_arr, y_train_arr)
            print("Local training done; returning parameters to server.")

            # Save model update for retrain.py aggregation
            self.save_model_update(len(X_train_arr))

            # Prepare metrics: report any newly observed labels to server.
            metrics = {}
            if self._new_labels_local:
                metrics["new_classes_json"] = json.dumps(self._new_labels_local)

            return (
                [
                    self.model.coef_.astype(np.float32),
                    self.model.intercept_.astype(np.float32),
                ],
                len(X_train_arr),
                metrics,
            )
        except Exception as e:
            import traceback

            traceback.print_exc()
            print("Exception in fit():", repr(e))
            raise

    def _safe_proba(self, y_proba, n_classes):
        # Ensure shape matches n_classes by padding zeros if necessary
        if y_proba.ndim == 1:
            y_proba = y_proba.reshape(-1, 1)
        if y_proba.shape[1] != n_classes:
            print(f"Fixing probability matrix: expected {n_classes} cols, got {y_proba.shape[1]}")
            new_proba = np.zeros((y_proba.shape[0], n_classes), dtype=np.float64)
            # copy what we have into the leftmost columns (scikit-learn aligns columns with classes_)
            n_copy = min(y_proba.shape[1], n_classes)
            new_proba[:, :n_copy] = y_proba[:, :n_copy]
            y_proba = new_proba
        # Replace NaN / inf and avoid division by zero
        y_proba = np.nan_to_num(y_proba, nan=0.0, posinf=0.0, neginf=0.0)
        row_sums = y_proba.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        y_proba = y_proba / row_sums
        # Clip to avoid exact 0 or 1 which can cause log_loss numeric issues
        eps = 1e-15
        y_proba = np.clip(y_proba, eps, 1 - eps)
        return y_proba

    def evaluate(self, parameters, config):
        print(
            ">>> evaluate() called by server. config keys:", list(config.keys())
        )
        try:
            classes_arr = self._read_classes_from_config(config)
            if self.model is None:
                if classes_arr is not None:
                    self.le = LabelEncoder()
                    self.le.classes_ = classes_arr
                elif self.le is None:
                    raise ValueError(
                        "No classes provided via config and no local label encoder available for evaluate."
                    )
                self.model = SGDClassifier(
                    loss="log_loss",
                    max_iter=1,
                    tol=None,
                    warm_start=True,
                    random_state=42,
                )
                self.model.partial_fit(
                    np.zeros((1, int(config.get("n_features", self.X.shape[1])))),
                    np.array([0]),
                    classes=np.arange(len(self.le.classes_)),
                )

            # set server-provided parameters
            self.set_parameters(parameters)

            X_test_arr = np.asarray(self.X_test, dtype=np.float64)
            y_test_arr = np.asarray(self.y_test, dtype=np.int64)
            print(f"Evaluating on {len(X_test_arr)} examples...")

            # get raw probabilities
            y_proba = self.model.predict_proba(X_test_arr)

            # make probabilities safe and ensure length matches label encoder
            n_classes = len(self.le.classes_)
            y_proba = self._safe_proba(y_proba, n_classes)

            # compute loss and accuracy safely
            try:
                loss = float(
                    log_loss(
                        y_test_arr,
                        y_proba,
                        labels=np.arange(n_classes),
                        eps=1e-15,
                    )
                )
            except Exception as e:
                print("Warning: log_loss computation failed:", e)
                loss = float("inf")

            y_pred = self.model.predict(X_test_arr)
            acc = float(accuracy_score(y_test_arr, y_pred))
            print(f"Evaluation done. loss={loss:.6f}, acc={acc:.6f}")
            return float(loss), len(X_test_arr), {"accuracy": acc}
        except Exception as e:
            import traceback

            traceback.print_exc()
            print("Exception in evaluate():", repr(e))
            # Do not re-raise — return an indication of failed evaluation to avoid crashing the client
            # Return a very large loss and zero accuracy so server sees a result
            try:
                n = len(getattr(self, "X_test", []))
            except Exception:
                n = 0
            return float("inf"), n, {"accuracy": 0.0}


if __name__ == "__main__":
    folder_path = input("Path to folder with CSV(s): ").strip()
    server_ip = (
        input("Server IP (for same machine use 127.0.0.1): ").strip() or "127.0.0.1"
    )
    server_port = input("Server port (default 8080): ").strip() or "8080"
    server_address = f"{server_ip}:{server_port}"

    client = NetworkTrafficClient(folder_path)
    fl_client = client.to_client()
    print(f"Connecting to Flower server at {server_address} ...")
    print("[Client] Attempting to connect... will retry automatically if server is not ready.\n")
    
    # Start client with automatic reconnection on server restart
    fl.client.start_client(
        server_address=server_address, 
        client=fl_client,
        grpc_max_message_length=536870912  # 512 MB for large model transfers
    )
