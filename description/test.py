"""
Federated Learning Model Testing Script
This script evaluates the trained federated learning models on the dataset
to verify client training accuracy and model performance.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    log_loss,
)
from sklearn.model_selection import train_test_split

# ==================== CONFIG ====================
MODEL_DIR = "models"
DATASET_PATH = "dataset"
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")

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
# ==================================================


def load_folder_csv(folder_path):
    """Load all CSV files from a folder and concatenate them."""
    all_dfs = []
    csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {folder_path}")
    
    print(f"Found {len(csv_files)} CSV file(s) in {folder_path}")
    
    for filename in sorted(csv_files):
        path = os.path.join(folder_path, filename)
        try:
            df = pd.read_csv(path)
            all_dfs.append(df)
            print(f"  [OK] Loaded {filename}: {df.shape[0]} rows")
        except Exception as e:
            print(f"  [FAILED] Failed to load {filename}: {e}")
    
    if not all_dfs:
        raise ValueError("No CSV files could be loaded.")
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal combined data: {combined_df.shape[0]} rows, {combined_df.shape[1]} columns\n")
    return combined_df


def preprocess_features(df):
    """Convert feature columns to numeric values."""
    X = df.copy()

    def convert_value(x):
        if pd.isna(x):
            return 0.0
        if isinstance(x, str) and x.startswith("0x"):
            try:
                return float(int(x, 16))
            except:
                return 0.0
        try:
            return float(x)
        except:
            return 0.0

    for col in X.columns:
        X[col] = X[col].apply(convert_value)
    return X


def load_model(model_path):
    """Load a trained model from disk."""
    if not os.path.exists(model_path):
        return None
    try:
        model = joblib.load(model_path)
        print(f"  [OK] Loaded model: {model_path}")
        return model
    except Exception as e:
        print(f"  [FAILED] Failed to load {model_path}: {e}")
        return None


def evaluate_model(model, X_test, y_test, le, model_name="Model"):
    """Evaluate a single model and return metrics."""
    if model is None:
        print(f"\n{model_name}: No model to evaluate\n")
        return None

    try:
        print(f"\n{'='*60}")
        print(f"  EVALUATING: {model_name}")
        print(f"{'='*60}")
        
        # Make predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
        loss = log_loss(y_test, y_proba, labels=np.arange(len(le.classes_)))

        # Create results dictionary
        results = {
            "model_name": model_name,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "log_loss": loss,
            "num_test_samples": len(X_test),
        }

        # Print results
        print(f"Test Samples: {len(X_test)}")
        print(f"Accuracy:     {accuracy:.4f} ({accuracy*100:.2f}%)")
        print(f"Precision:    {precision:.4f}")
        print(f"Recall:       {recall:.4f}")
        print(f"F1-Score:     {f1:.4f}")
        print(f"Log Loss:     {loss:.4f}")

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        print(f"\nConfusion Matrix:")
        print(cm)

        # Per-class metrics
        print(f"\nPer-Class Metrics:")
        try:
            print(classification_report(y_test, y_pred, target_names=le.classes_, labels=np.arange(len(le.classes_))))
        except Exception as e:
            print(f"Note: Could not generate per-class report: {e}")
            print("(This may occur when test set contains only one class)")

        return results

    except Exception as e:
        print(f"Error evaluating model: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_all_models():
    """Test all trained models from each federated round."""
    print("\n" + "="*60)
    print("FEDERATED LEARNING MODEL EVALUATION")
    print("="*60 + "\n")

    # Load dataset
    print("Loading dataset...")
    try:
        df = load_folder_csv(DATASET_PATH)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    # Verify features
    missing_features = [col for col in FEATURE_COLS if col not in df.columns]
    if missing_features:
        print(f"Warning: Missing features in dataset: {missing_features}")

    # Check for label column
    if "label" not in df.columns:
        print("Error: 'label' column not found in dataset")
        return

    # Extract features and labels
    print("Preprocessing features...")
    X = preprocess_features(df[FEATURE_COLS])
    raw_labels = df["label"].values

    # Load or create label encoder
    print("Loading label encoder...")
    if os.path.exists(LABEL_ENCODER_PATH):
        le = joblib.load(LABEL_ENCODER_PATH)
        print(f"  [OK] Loaded label encoder")
    else:
        le = LabelEncoder()
        le.classes_ = np.array(["Benign", "Attack"])
        print(f"  [OK] Created default label encoder")

    print(f"Classes: {le.classes_}")

    # Transform labels
    try:
        y = le.transform(raw_labels)
        print(f"  [OK] Labels transformed successfully")
    except Exception as e:
        print(f"  [FAILED] Error transforming labels: {e}")
        return

    # Split data for testing
    print(f"\nSplitting data into train/test (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train samples: {len(X_train)}")
    print(f"Test samples:  {len(X_test)}")

    # Print label distribution
    print(f"\nLabel Distribution in Test Set:")
    unique, counts = np.unique(y_test, return_counts=True)
    for label, count in zip(le.classes_, counts):
        percentage = (count / len(y_test)) * 100
        print(f"  {label}: {count} ({percentage:.2f}%)")

    # Test all models
    print("\n" + "="*60)
    print("TESTING TRAINED MODELS")
    print("="*60)

    results_list = []

    # Test main model
    print("\n[1/4] Testing Main Model...")
    main_model_path = os.path.join(MODEL_DIR, "network_sgd_classifier.joblib")
    model = load_model(main_model_path)
    if model:
        results = evaluate_model(model, X_test, y_test, le, "Main Model")
        if results:
            results_list.append(results)
    else:
        print(f"  [FAILED] Main model not found at {main_model_path}")

    # Test round models
    for round_num in range(1, 4):
        print(f"\n[{round_num+1}/4] Testing Round {round_num} Model...")
        round_model_path = os.path.join(
            MODEL_DIR, f"network_sgd_classifier_round{round_num}.joblib"
        )
        model = load_model(round_model_path)
        if model:
            results = evaluate_model(
                model, X_test, y_test, le, f"Round {round_num} Model"
            )
            if results:
                results_list.append(results)
        else:
            print(f"  [FAILED] Round {round_num} model not found at {round_model_path}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if results_list:
        print(f"\nEvaluated {len(results_list)} model(s):\n")
        for res in results_list:
            print(f"{res['model_name']:20s} | Accuracy: {res['accuracy']:.4f} | F1: {res['f1_score']:.4f} | Loss: {res['log_loss']:.4f}")

        # Find best model
        best_model = max(results_list, key=lambda x: x["accuracy"])
        print(f"\n[BEST] Best Model: {best_model['model_name']} with {best_model['accuracy']:.4f} accuracy")

        # Check if training improved
        if len(results_list) > 1:
            print("\nTraining Progress Analysis:")
            first_acc = results_list[0]["accuracy"]
            last_acc = results_list[-1]["accuracy"]
            improvement = ((last_acc - first_acc) / first_acc * 100) if first_acc != 0 else 0
            print(f"  Initial Accuracy: {first_acc:.4f}")
            print(f"  Final Accuracy:   {last_acc:.4f}")
            print(f"  Improvement:      {improvement:+.2f}%")

            if improvement > 0:
                print("  [OK] Model is improving with federated learning rounds!")
            elif improvement < 0:
                print("  [FAILED] Model accuracy is decreasing! Check training process.")
            else:
                print("  [INFO] Model accuracy remains the same.")
    else:
        print("No models were successfully evaluated.")

    print("\n" + "="*60 + "\n")


def test_single_model(model_path, dataset_path):
    """Test a specific model on a specific dataset."""
    print(f"\nTesting model: {model_path}")
    print(f"Dataset: {dataset_path}\n")

    # Load data
    df = load_folder_csv(dataset_path)

    # Preprocess
    X = preprocess_features(df[FEATURE_COLS])
    
    if "label" not in df.columns:
        print("Error: 'label' column not found")
        return
    
    raw_labels = df["label"].values

    # Load label encoder
    if os.path.exists(LABEL_ENCODER_PATH):
        le = joblib.load(LABEL_ENCODER_PATH)
    else:
        le = LabelEncoder()
        le.classes_ = np.array(["Benign", "Attack"])

    y = le.transform(raw_labels)

    # Load model
    model = load_model(model_path)
    if model is None:
        return

    # Evaluate
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    evaluate_model(model, X_test, y_test, le, os.path.basename(model_path))


def analyze_client_training():
    """Analyze if the client is properly training by checking model weights."""
    print("\n" + "="*60)
    print("CLIENT TRAINING ANALYSIS")
    print("="*60 + "\n")
    
    try:
        # Load models
        main_model_path = os.path.join(MODEL_DIR, "network_sgd_classifier.joblib")
        main_model = load_model(main_model_path)
        
        if main_model is None:
            print("Cannot analyze training: main model not found")
            return
        
        print("Analyzing model weights across federated rounds...\n")
        
        models_data = {
            "Main": main_model
        }
        
        for round_num in range(1, 4):
            round_path = os.path.join(MODEL_DIR, f"network_sgd_classifier_round{round_num}.joblib")
            model = load_model(round_path)
            if model:
                models_data[f"Round {round_num}"] = model
        
        # Compare weights
        model_names = list(models_data.keys())
        print(f"{'Model':<15} | {'Coef L2-Norm':<15} | {'Intercept':<15}")
        print("-" * 50)
        
        coef_norms = []
        for name, model in models_data.items():
            coef_norm = float(np.linalg.norm(model.coef_))
            intercept = float(model.intercept_[0])
            coef_norms.append(coef_norm)
            print(f"{name:<15} | {coef_norm:<15.6f} | {intercept:<15.6f}")
        
        # Check for weight changes
        print("\nWeight Changes Between Rounds:")
        print("-" * 50)
        for i in range(1, len(coef_norms)):
            change = coef_norms[i] - coef_norms[i-1]
            pct_change = (change / coef_norms[i-1] * 100) if coef_norms[i-1] != 0 else 0
            print(f"{model_names[i-1]} -> {model_names[i]:<12} | Change: {change:+.6f} ({pct_change:+.2f}%)")
        
        # Client training verdict
        print("\n" + "="*60)
        print("TRAINING VERDICT:")
        print("="*60)
        
        if len(coef_norms) > 1:
            avg_change = np.mean(np.abs(np.diff(coef_norms)))
            if avg_change > 1e-6:
                print("[OK] Client is properly training!")
                print(f"  Average weight change: {avg_change:.6f}")
                print("  Models are being updated with client data each round.")
            else:
                print("[FAILED] Client may not be training properly!")
                print(f"  Average weight change: {avg_change:.6f}")
                print("  Model weights are not changing significantly between rounds.")
        else:
            print("[INFO] Cannot determine - need multiple models for comparison")
            
    except Exception as e:
        print(f"Error during training analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Federated Learning Model Testing")
    print("="*60)
    
    # Check if dataset exists
    if not os.path.exists(DATASET_PATH):
        print(f"\nError: Dataset path '{DATASET_PATH}' not found!")
        print(f"Please ensure the dataset is at: {os.path.abspath(DATASET_PATH)}")
    else:
        # Test all models
        test_all_models()
        
        # Analyze client training
        analyze_client_training()

        # Uncomment below to test a single model on a specific dataset:
        # test_single_model("models/network_sgd_classifier.joblib", "dataset")
