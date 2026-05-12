"""
Federated Learning IDS - Model Prediction Script
This script loads trained federated learning models and makes predictions
on new network traffic data for intrusion detection.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder
from pathlib import Path

# ==================== CONFIG ====================
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "network_sgd_classifier.joblib")
LE_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")

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
# =================================================


def load_model_and_encoder(model_path=MODEL_PATH, le_path=LE_PATH):
    """
    Load the trained model and label encoder.
    
    Args:
        model_path: Path to the trained model
        le_path: Path to the label encoder
    
    Returns:
        Tuple of (model, label_encoder) or (None, None) if loading fails
    """
    print(f"Loading model from {model_path}...")
    
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return None, None
    
    if not os.path.exists(le_path):
        print(f"ERROR: Label encoder not found at {le_path}")
        return None, None
    
    try:
        model = joblib.load(model_path)
        le = joblib.load(le_path)
        print(f"[OK] Model loaded successfully")
        print(f"[OK] Label encoder loaded successfully")
        print(f"  Classes: {le.classes_}")
        return model, le
    except Exception as e:
        print(f"ERROR loading model/encoder: {e}")
        return None, None


def preprocess_features(df):
    """
    Convert feature columns to numeric values.
    Handles hex strings (0x format) and NaN values.
    
    Args:
        df: DataFrame with feature columns
    
    Returns:
        DataFrame with numeric features
    """
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


def validate_features(df, required_cols=FEATURE_COLS):
    """
    Validate that all required features are present in the dataframe.
    
    Args:
        df: Input dataframe
        required_cols: List of required feature columns
    
    Returns:
        List of missing columns (empty if all present)
    """
    missing = [col for col in required_cols if col not in df.columns]
    return missing


def predict_single_sample(model, le, features_dict):
    """
    Make prediction on a single sample.
    
    Args:
        model: Trained model
        le: Label encoder
        features_dict: Dictionary of features {feature_name: value}
    
    Returns:
        Dictionary with prediction results
    """
    try:
        # Convert to dataframe
        df = pd.DataFrame([features_dict])
        
        # Validate features
        missing = validate_features(df)
        if missing:
            return {
                "success": False,
                "error": f"Missing features: {missing}"
            }
        
        # Select only required features
        X = df[FEATURE_COLS]
        
        # Preprocess
        X = preprocess_features(X)
        X = X.values.astype(np.float64)
        
        # Make prediction
        prediction = model.predict(X)[0]
        probability = model.predict_proba(X)[0]
        
        # Get class name
        class_name = le.inverse_transform([prediction])[0]
        
        # Get confidence
        confidence = float(np.max(probability))
        
        # Get probabilities for all classes
        probs = {
            class_name: float(probability[prediction])
            for prediction, class_name in enumerate(le.classes_)
        }
        
        return {
            "success": True,
            "prediction": class_name,
            "confidence": confidence,
            "probabilities": probs,
            "all_classes": list(le.classes_)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def predict_batch_csv(model, le, csv_path):
    """
    Make predictions on a CSV file containing network traffic data.
    
    Args:
        model: Trained model
        le: Label encoder
        csv_path: Path to CSV file
    
    Returns:
        DataFrame with predictions
    """
    try:
        print(f"\nLoading data from {csv_path}...")
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} samples")
        
        # Validate features
        missing = validate_features(df)
        if missing:
            print(f"ERROR: Missing features: {missing}")
            return None
        
        # Select and preprocess features
        X = df[FEATURE_COLS].copy()
        X = preprocess_features(X)
        
        print(f"Making predictions on {len(X)} samples...")
        
        # Make predictions
        predictions = model.predict(X)
        probabilities = model.predict_proba(X)
        
        # Convert predictions to class names
        pred_classes = le.inverse_transform(predictions)
        
        # Get confidence scores
        confidence = np.max(probabilities, axis=1)
        
        # Create results dataframe
        results = df.copy()
        results['predicted_class'] = pred_classes
        results['confidence'] = confidence
        
        # Add probability for each class
        for idx, class_name in enumerate(le.classes_):
            results[f'prob_{class_name}'] = probabilities[:, idx]
        
        print(f"[OK] Predictions complete")
        
        return results
    
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def predict_from_dataframe(model, le, df):
    """
    Make predictions on samples provided as dataframe.
    
    Args:
        model: Trained model
        le: Label encoder
        df: DataFrame with features
    
    Returns:
        DataFrame with predictions added
    """
    try:
        # Validate features
        missing = validate_features(df)
        if missing:
            print(f"ERROR: Missing features: {missing}")
            return None
        
        # Select and preprocess features
        X = df[FEATURE_COLS].copy()
        X = preprocess_features(X)
        
        # Make predictions
        predictions = model.predict(X)
        probabilities = model.predict_proba(X)
        
        # Convert to class names
        pred_classes = le.inverse_transform(predictions)
        
        # Get confidence
        confidence = np.max(probabilities, axis=1)
        
        # Add to dataframe
        results = df.copy()
        results['predicted_class'] = pred_classes
        results['confidence'] = confidence
        
        for idx, class_name in enumerate(le.classes_):
            results[f'prob_{class_name}'] = probabilities[:, idx]
        
        return results
    
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def predict_with_different_rounds(csv_path, model_dir=MODEL_DIR):
    """
    Compare predictions across different federated rounds.
    Useful for understanding model evolution.
    
    Args:
        csv_path: Path to CSV file with data
        model_dir: Directory containing models
    
    Returns:
        DataFrame with predictions from all models
    """
    try:
        # Load data
        print(f"Loading data from {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # Validate features
        missing = validate_features(df)
        if missing:
            print(f"ERROR: Missing features: {missing}")
            return None
        
        # Preprocess features once
        X = df[FEATURE_COLS].copy()
        X = preprocess_features(X)
        
        # Load label encoder
        le_path = os.path.join(model_dir, "label_encoder.joblib")
        le = joblib.load(le_path)
        
        results = df.copy()
        
        # Test main model
        print("\nTesting Main Model...")
        model_path = os.path.join(model_dir, "network_sgd_classifier.joblib")
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            predictions = model.predict(X)
            probabilities = model.predict_proba(X)
            pred_classes = le.inverse_transform(predictions)
            results['main_prediction'] = pred_classes
            results['main_confidence'] = np.max(probabilities, axis=1)
            print(f"[OK] Main model predictions added")
        
        # Test federated rounds
        for round_num in range(1, 4):
            print(f"\nTesting Round {round_num} Model...")
            model_path = os.path.join(
                model_dir, f"network_sgd_classifier_round{round_num}.joblib"
            )
            if os.path.exists(model_path):
                model = joblib.load(model_path)
                predictions = model.predict(X)
                probabilities = model.predict_proba(X)
                pred_classes = le.inverse_transform(predictions)
                results[f'round{round_num}_prediction'] = pred_classes
                results[f'round{round_num}_confidence'] = np.max(probabilities, axis=1)
                print(f"[OK] Round {round_num} predictions added")
            else:
                print(f"✗ Round {round_num} model not found")
        
        return results
    
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def interactive_prediction(model, le):
    """
    Interactive mode for predicting individual network traffic samples.
    
    Args:
        model: Trained model
        le: Label encoder
    """
    print("\n" + "="*60)
    print("INTERACTIVE PREDICTION MODE")
    print("="*60)
    print("\nEnter network traffic feature values for prediction.")
    print("Type 'exit' to quit, 'help' for feature info\n")
    
    while True:
        try:
            print(f"\nEnter values for {len(FEATURE_COLS)} features:")
            print(f"Features: {', '.join(FEATURE_COLS)}")
            
            features_str = input("\nEnter comma-separated values (or 'exit'): ").strip()
            
            if features_str.lower() == 'exit':
                print("Exiting prediction mode...")
                break
            
            if features_str.lower() == 'help':
                print("\nFeature Information:")
                for i, col in enumerate(FEATURE_COLS, 1):
                    print(f"  {i}. {col}")
                continue
            
            # Parse values
            values = [float(v.strip()) for v in features_str.split(',')]
            
            if len(values) != len(FEATURE_COLS):
                print(f"ERROR: Expected {len(FEATURE_COLS)} values, got {len(values)}")
                continue
            
            # Create sample
            sample = dict(zip(FEATURE_COLS, values))
            
            # Predict
            result = predict_single_sample(model, le, sample)
            
            if result['success']:
                print(f"\n{'='*40}")
                print(f"PREDICTION: {result['prediction']}")
                print(f"Confidence: {result['confidence']:.4f} ({result['confidence']*100:.2f}%)")
                print(f"\nProbabilities:")
                for class_name, prob in result['probabilities'].items():
                    bar_length = int(prob * 20)
                    bar = "█" * bar_length + "░" * (20 - bar_length)
                    print(f"  {class_name:10s}: {bar} {prob:.4f}")
                print(f"{'='*40}")
            else:
                print(f"ERROR: {result['error']}")
        
        except ValueError:
            print("ERROR: Invalid input. Please enter numeric values separated by commas.")
        except Exception as e:
            print(f"ERROR: {e}")


def main():
    """Main entry point with menu options."""
    print("\n" + "="*60)
    print("FEDERATED LEARNING IDS - PREDICTION")
    print("="*60 + "\n")
    
    # Load model and encoder
    model, le = load_model_and_encoder()
    
    if model is None or le is None:
        print("ERROR: Could not load model. Exiting.")
        return
    
    while True:
        print("\n" + "="*60)
        print("PREDICTION MENU")
        print("="*60)
        print("""
1. Predict single sample (interactive)
2. Predict from CSV file
3. Compare predictions across federated rounds
4. Show model information
5. Exit
        """)
        
        choice = input("Select option (1-5): ").strip()
        
        if choice == '1':
            interactive_prediction(model, le)
        
        elif choice == '2':
            csv_file = input("Enter path to CSV file: ").strip()
            if os.path.exists(csv_file):
                results = predict_batch_csv(model, le, csv_file)
                if results is not None:
                    output_file = csv_file.replace('.csv', '_predictions.csv')
                    results.to_csv(output_file, index=False)
                    print(f"\n[OK] Results saved to {output_file}")
                    print(f"\nFirst 5 predictions:")
                    print(results[['predicted_class', 'confidence']].head())
            else:
                print(f"ERROR: File not found: {csv_file}")
        
        elif choice == '3':
            csv_file = input("Enter path to CSV file: ").strip()
            if os.path.exists(csv_file):
                results = predict_with_different_rounds(csv_file)
                if results is not None:
                    output_file = csv_file.replace('.csv', '_all_rounds.csv')
                    results.to_csv(output_file, index=False)
                    print(f"\n[OK] Results saved to {output_file}")
            else:
                print(f"ERROR: File not found: {csv_file}")
        
        elif choice == '4':
            print("\n" + "="*60)
            print("MODEL INFORMATION")
            print("="*60)
            print(f"Model path: {MODEL_PATH}")
            print(f"Model type: {type(model).__name__}")
            print(f"Number of features: {model.coef_.shape[1]}")
            print(f"Number of classes: {len(le.classes_)}")
            print(f"Classes: {list(le.classes_)}")
            print(f"Model coefficients shape: {model.coef_.shape}")
            print(f"Model intercept: {model.intercept_}")
        
        elif choice == '5':
            print("Exiting...")
            break
        
        else:
            print("Invalid option. Please select 1-5.")


if __name__ == "__main__":
    # You can also use this script programmatically:
    
    # Example 1: Load model and make single prediction
    # model, le = load_model_and_encoder()
    # sample = {
    #     "frame.len": 164.0,
    #     "ip.proto": 6.0,
    #     "ip.checksum": 0x736d,
    #     ...
    # }
    # result = predict_single_sample(model, le, sample)
    # print(result)
    
    # Example 2: Batch prediction from CSV
    # model, le = load_model_and_encoder()
    # results = predict_batch_csv(model, le, "dataset/sample.csv")
    # results.to_csv("predictions.csv", index=False)
    
    # Example 3: Compare rounds
    # results = predict_with_different_rounds("dataset/sample.csv")
    # results.to_csv("round_comparison.csv", index=False)
    
    # Run interactive menu
    main()
