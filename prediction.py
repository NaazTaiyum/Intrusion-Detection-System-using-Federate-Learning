# prediction.py
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

# ---------- CONFIG ----------
# Update this if your models are somewhere else
MODEL_DIR = r"A:\fed_learning\models"

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
# ----------------------------


def list_model_files(model_dir):
    try:
        files = sorted(
            [f for f in os.listdir(model_dir) if f.endswith(".joblib") and "label" not in f.lower()]
        )
    except FileNotFoundError:
        files = []
    return files


def choose_model_file(model_dir):
    files = list_model_files(model_dir)
    if not files:
        print(f"No model files found in '{model_dir}'. Please place your .joblib model files there.")
        sys.exit(1)

    print("\nAvailable model files:")
    for i, fname in enumerate(files, 1):
        print(f"  {i}. {fname}")

    while True:
        choice = input(f"\nSelect model number (1-{len(files)}), or type path: ").strip()
        if choice == "":
            continue
        # typed number?
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                return os.path.join(model_dir, files[idx])
            print("Invalid number, try again.")
        else:
            # user gave a path
            if os.path.exists(choice):
                return choice
            # maybe a relative name
            alt = os.path.join(model_dir, choice)
            if os.path.exists(alt):
                return alt
            print("Path not found, try again.")


def load_label_encoder(model_dir):
    enc_path = os.path.join(model_dir, "label_encoder.joblib")
    if not os.path.exists(enc_path):
        print(f"Label encoder not found at '{enc_path}'. Please ensure 'label_encoder.joblib' exists.")
        sys.exit(1)
    return joblib.load(enc_path)


def conv_value(x):
    """Convert a single cell value to float. Supports hex strings like '0xa580'."""
    if pd.isna(x):
        return 0.0
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return 0.0
        # hex
        if s.lower().startswith("0x"):
            try:
                return float(int(s, 16))
            except Exception:
                return 0.0
        # remove commas
        try:
            return float(s.replace(",", ""))
        except Exception:
            return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0


def clean_df(df):
    """
    Ensure required FEATURE_COLS exist, convert values to float, avoid SettingWithCopyWarning.
    Returns DataFrame with columns in FEATURE_COLS and dtype float64.
    """
    # make a copy to avoid SettingWithCopyWarning
    df = df.copy()
    # add missing columns with zeros
    for col in FEATURE_COLS:
        if col not in df.columns:
            df.loc[:, col] = 0.0

    # apply conversion column-wise using vectorized approach where possible
    for col in FEATURE_COLS:
        # Use .loc to avoid SettingWithCopyWarning
        df.loc[:, col] = df.loc[:, col].apply(conv_value)

    return df[FEATURE_COLS].astype(np.float64)


def safe_transform_true_labels(label_series, label_encoder):
    """
    Transform true string labels to integer indices used by label_encoder.
    Unseen labels are mapped to 'Unknown' if available, otherwise to the last encoder class.
    Returns numpy integer array.
    """
    # build mapping
    classes = list(label_encoder.classes_)
    class_to_index = {c: i for i, c in enumerate(classes)}
    fallback_idx = class_to_index.get("Unknown", len(classes) - 1)

    y_idx = []
    for raw in label_series:
        s = str(raw).strip()
        if s in class_to_index:
            y_idx.append(class_to_index[s])
        else:
            # map unseen -> Unknown or fallback
            y_idx.append(fallback_idx)
    return np.array(y_idx, dtype=np.int64)


def manual_input_and_predict(model, label_encoder):
    """
    Prompt user for each feature value (supports hex), predict single row and print result.
    """
    print("\nEnter values for each feature (enter empty to use 0). Hex like 0xa580 is accepted.")
    row = {}
    for c in FEATURE_COLS:
        raw = input(f"{c}: ").strip()
        if raw == "":
            row[c] = 0.0
        else:
            # convert hex or numeric
            if raw.lower().startswith("0x"):
                try:
                    row[c] = float(int(raw, 16))
                except Exception:
                    print(f"Warning: couldn't parse '{raw}', using 0.0")
                    row[c] = 0.0
            else:
                try:
                    row[c] = float(raw.replace(",", ""))
                except Exception:
                    print(f"Warning: couldn't parse '{raw}', using 0.0")
                    row[c] = 0.0

    df = pd.DataFrame([row])
    X = clean_df(df)
    X_arr = X.to_numpy(dtype=np.float64)
    pred_idx = model.predict(X_arr)
    # model.predict returns array (even for single sample)
    pred_label = label_encoder.inverse_transform(pred_idx)[0]
    print("\n===== PREDICTION =====")
    print("Predicted label:", pred_label)
    print("=======================")


def csv_input_and_predict(model, label_encoder):
    path = input("\nEnter CSV file path: ").strip()
    if not os.path.exists(path):
        print("File not found:", path)
        return
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        print("Failed to read CSV:", e)
        return

    # Ensure we won't raise on missing columns: clean_df fills missing ones
    X = clean_df(df)
    X_arr = X.to_numpy(dtype=np.float64)

    # Predict using numpy arrays (avoids sklearn feature-name warning)
    try:
        pred_idx = model.predict(X_arr)
    except Exception as e:
        print("Prediction failed:", e)
        return

    try:
        pred_labels = label_encoder.inverse_transform(pred_idx)
    except Exception as e:
        # fallback: convert indices to string
        pred_labels = [str(x) for x in pred_idx]

    out_df = df.copy()
    out_df.loc[:, "predicted_label"] = pred_labels

    # save
    base, ext = os.path.splitext(path)
    save_path = f"{base}_predicted{ext}"
    try:
        out_df.to_csv(save_path, index=False)
        print(f"\nSaved predicted file: {save_path}")
    except Exception as e:
        print("Failed to save predictions:", e)

    # compute accuracy if label column exists
    if "label" in df.columns:
        try:
            true_idx = safe_transform_true_labels(df["label"], label_encoder)
            acc = accuracy_score(true_idx, pred_idx)
            print(f"Accuracy on this CSV: {acc * 100:.2f}% ({int(acc * len(true_idx))}/{len(true_idx)})")
        except Exception as e:
            print("Could not compute accuracy:", e)
    else:
        print("No 'label' column found in CSV -> accuracy cannot be computed.")


def main():
    print(f"Using model directory: {MODEL_DIR}")
    model_path = choose_model_file(MODEL_DIR)
    print("\nUsing model:", model_path)

    # load model
    try:
        model = joblib.load(model_path)
    except Exception as e:
        print("Failed to load model:", e)
        sys.exit(1)

    # load label encoder
    label_encoder = load_label_encoder(MODEL_DIR)

    print("""
====== PREDICTION MODE ======
1. Manual Input (single row)
2. CSV File (batch)
================================
""")
    choice = input("Choose 1 or 2: ").strip()
    if choice == "1":
        manual_input_and_predict(model, label_encoder)
    elif choice == "2":
        csv_input_and_predict(model, label_encoder)
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
