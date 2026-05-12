"""
Example Usage of Prediction Script
Shows practical examples of how to use predict.py for different scenarios
"""

from predict import (
    load_model_and_encoder,
    predict_single_sample,
    predict_batch_csv,
    predict_from_dataframe,
    predict_with_different_rounds
)
import pandas as pd


def example_1_single_prediction():
    """
    Example 1: Make prediction on a single network traffic sample
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Single Sample Prediction")
    print("="*60)
    
    # Load model
    model, le = load_model_and_encoder()
    if model is None:
        print("Failed to load model")
        return
    
    # Create a sample (typical Benign traffic)
    sample = {
        "frame.len": 164.0,
        "ip.proto": 6.0,
        "ip.checksum": 0x736d,
        "ip.tos": 128.0,
        "tcp.srcport": 43325.0,
        "tcp.dstport": 1883.0,
        "tcp.flags": 0x0018,
        "tcp.window_size_value": 502.0,
        "tcp.window_size_scalefactor": -1.0,
        "tcp.checksum": 0x5da1,
        "tcp.pdu.size": 98.0,
        "udp.srcport": 0.0,
        "udp.dstport": 0.0,
    }
    
    print("\nSample Data:")
    for key, value in sample.items():
        print(f"  {key}: {value}")
    
    # Make prediction
    result = predict_single_sample(model, le, sample)
    
    # Display results
    if result['success']:
        print(f"\nPrediction Results:")
        print(f"  Class: {result['prediction']}")
        print(f"  Confidence: {result['confidence']:.4f} ({result['confidence']*100:.2f}%)")
        print(f"\n  Probability Breakdown:")
        for class_name, prob in result['probabilities'].items():
            print(f"    {class_name}: {prob:.4f}")
    else:
        print(f"Error: {result['error']}")


def example_2_batch_prediction():
    """
    Example 2: Make predictions on entire CSV file
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Batch CSV Prediction")
    print("="*60)
    
    # Load model
    model, le = load_model_and_encoder()
    if model is None:
        print("Failed to load model")
        return
    
    # Path to dataset
    csv_path = "dataset/iotsim-cooler-motor-2.csv"
    
    print(f"\nPredicting on: {csv_path}")
    
    # Get predictions
    results = predict_batch_csv(model, le, csv_path)
    
    if results is not None:
        # Save to file
        output_file = csv_path.replace('.csv', '_example_predictions.csv')
        results.to_csv(output_file, index=False)
        
        print(f"\n✓ Results saved to {output_file}")
        print(f"\nPrediction Summary:")
        print(f"  Total samples: {len(results)}")
        print(f"  Benign predictions: {(results['predicted_class'] == 'Benign').sum()}")
        print(f"  Attack predictions: {(results['predicted_class'] == 'Attack').sum()}")
        print(f"\nConfidence Statistics:")
        print(f"  Mean: {results['confidence'].mean():.4f}")
        print(f"  Min: {results['confidence'].min():.4f}")
        print(f"  Max: {results['confidence'].max():.4f}")
        print(f"\nFirst 5 Predictions:")
        print(results[['predicted_class', 'confidence']].head())


def example_3_dataframe_prediction():
    """
    Example 3: Predict on data you have in memory (DataFrame)
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: DataFrame Prediction")
    print("="*60)
    
    # Load model
    model, le = load_model_and_encoder()
    if model is None:
        print("Failed to load model")
        return
    
    # Load CSV data
    df = pd.read_csv("dataset/iotsim-cooler-motor-2.csv")
    
    print(f"\nLoaded DataFrame with shape: {df.shape}")
    print(f"Columns: {list(df.columns)[:5]}... (and {len(df.columns)-5} more)")
    
    # Take first 100 samples
    df_sample = df.head(100)
    
    print(f"Making predictions on {len(df_sample)} samples...")
    
    # Predict
    from predict import predict_from_dataframe
    results = predict_from_dataframe(model, le, df_sample)
    
    if results is not None:
        print(f"\n✓ Predictions complete!")
        print(f"\nResults Preview:")
        print(results[['predicted_class', 'confidence', 'prob_Benign', 'prob_Attack']].head(10))
        
        # Analyze
        attack_count = (results['predicted_class'] == 'Attack').sum()
        print(f"\nAnalysis:")
        print(f"  Attacks found: {attack_count}")
        print(f"  Average confidence: {results['confidence'].mean():.4f}")


def example_4_round_comparison():
    """
    Example 4: Compare predictions across federated rounds
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Federated Round Comparison")
    print("="*60)
    
    csv_path = "dataset/iotsim-cooler-motor-2.csv"
    
    print(f"\nComparing predictions from all 4 models on: {csv_path}")
    
    # Get predictions from all rounds
    results = predict_with_different_rounds(csv_path)
    
    if results is not None:
        # Save to file
        output_file = csv_path.replace('.csv', '_round_comparison.csv')
        results.to_csv(output_file, index=False)
        
        print(f"\n✓ Comparison saved to {output_file}")
        
        # Compare predictions
        print(f"\nComparison Results:")
        comparison_cols = [col for col in results.columns if 'prediction' in col]
        print(results[comparison_cols].head(10))
        
        # Check agreement
        print(f"\nPrediction Agreement:")
        if 'main_prediction' in results.columns:
            main_pred = results['main_prediction']
            
            for round_num in range(1, 4):
                round_col = f'round{round_num}_prediction'
                if round_col in results.columns:
                    agreement = (main_pred == results[round_col]).sum()
                    agreement_pct = (agreement / len(results)) * 100
                    print(f"  Main vs Round {round_num}: {agreement_pct:.2f}% agreement")


def example_5_anomaly_detection():
    """
    Example 5: Use predictions for anomaly detection
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Anomaly Detection")
    print("="*60)
    
    # Load model
    model, le = load_model_and_encoder()
    if model is None:
        print("Failed to load model")
        return
    
    # Get predictions
    print(f"\nLoading and predicting on dataset...")
    results = predict_batch_csv(model, le, "dataset/iotsim-cooler-motor-2.csv")
    
    if results is not None:
        # Find potential attacks
        attacks = results[results['predicted_class'] == 'Attack']
        low_confidence = results[results['confidence'] < 0.8]
        
        print(f"\nAnomaly Detection Results:")
        print(f"  Total samples: {len(results)}")
        print(f"  Attack predictions: {len(attacks)}")
        print(f"  Low confidence predictions: {len(low_confidence)}")
        
        if len(attacks) > 0:
            print(f"\n  Attacks found:")
            print(attacks[['predicted_class', 'confidence']].head())
        else:
            print(f"\n  No attacks detected in this dataset")
        
        if len(low_confidence) > 0:
            print(f"\n  Low confidence samples (< 80%):")
            print(low_confidence[['predicted_class', 'confidence']].head())


def example_6_threshold_analysis():
    """
    Example 6: Analyze predictions with different confidence thresholds
    """
    print("\n" + "="*60)
    print("EXAMPLE 6: Confidence Threshold Analysis")
    print("="*60)
    
    # Load model
    model, le = load_model_and_encoder()
    if model is None:
        print("Failed to load model")
        return
    
    # Get predictions
    print(f"\nLoading and predicting...")
    results = predict_batch_csv(model, le, "dataset/iotsim-cooler-motor-2.csv")
    
    if results is not None:
        print(f"\nThreshold Analysis (on Attack predictions only):")
        
        attacks = results[results['predicted_class'] == 'Attack']
        
        if len(attacks) > 0:
            thresholds = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
            for threshold in thresholds:
                count = (attacks['confidence'] >= threshold).sum()
                percentage = (count / len(attacks)) * 100 if len(attacks) > 0 else 0
                print(f"  >=  {threshold:.2f}: {count} attacks ({percentage:.1f}%)")
        else:
            print("  No attacks found to analyze")


# Run all examples
if __name__ == "__main__":
    print("\n" + "="*60)
    print("PREDICTION SCRIPT - USAGE EXAMPLES")
    print("="*60)
    
    # Note: Only run examples that have required files
    try:
        # Check if dataset exists
        import os
        if os.path.exists("dataset/iotsim-cooler-motor-2.csv"):
            example_1_single_prediction()
            example_2_batch_prediction()
            example_3_dataframe_prediction()
            example_4_round_comparison()
            example_5_anomaly_detection()
        else:
            print("\nNote: Dataset not found, running single sample example only")
            example_1_single_prediction()
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60 + "\n")
