# Prediction Script Documentation

## Overview
The `predict.py` script loads your trained federated learning models and makes predictions on new network traffic data for intrusion detection.

## Features

✓ **Single Sample Prediction** - Predict class for individual network flows
✓ **Batch Prediction** - Predict on entire CSV files
✓ **Confidence Scores** - Get prediction confidence for each sample
✓ **Probability Distribution** - See probabilities for all classes
✓ **Round Comparison** - Compare predictions across federated rounds
✓ **Interactive Mode** - Enter values manually and get instant predictions
✓ **CSV Export** - Save predictions to output files

## Installation

### Requirements
```bash
pip install pandas numpy scikit-learn joblib
```

## Usage

### Interactive Menu (Recommended for First Time)
```bash
cd F:\federate_learning
python predict.py
```

You'll see a menu with options:
1. Predict single sample (interactive)
2. Predict from CSV file
3. Compare predictions across federated rounds
4. Show model information
5. Exit

### Option 1: Interactive Single Sample Prediction

When you select option 1, the script will:
1. Ask you to enter values for each of the 13 features
2. Make a prediction using the trained model
3. Show the prediction class and confidence

**Example Input:**
```
Enter comma-separated values: 164,6,0x736d,128,43325,1883,0x0018,502,-1,0x5da1,98,0,0
```

**Example Output:**
```
========================================
PREDICTION: Benign
Confidence: 0.9956 (99.56%)

Probabilities:
  Benign    : ████████████████████ 0.9956
  Attack    : ░░░░░░░░░░░░░░░░░░░░ 0.0044
========================================
```

### Option 2: Batch Prediction from CSV

Predicts on all samples in a CSV file:

```
Select option: 2
Enter path to CSV file: dataset/iotsim-cooler-motor-2.csv
```

**Output:**
- Loads the CSV file
- Makes predictions on all rows
- Saves results to `dataset/iotsim-cooler-motor-2_predictions.csv`
- Shows first 5 predictions

**Output CSV columns will include:**
- All original columns from input CSV
- `predicted_class` - Predicted class (Benign/Attack)
- `confidence` - Confidence score (0-1)
- `prob_Benign` - Probability for Benign class
- `prob_Attack` - Probability for Attack class

### Option 3: Compare Federated Rounds

Compare predictions from different federated rounds:

```
Select option: 3
Enter path to CSV file: dataset/iotsim-cooler-motor-2.csv
```

**Output CSV will include:**
- All original columns
- `main_prediction` - Main model prediction
- `main_confidence` - Main model confidence
- `round1_prediction` - Round 1 model prediction
- `round1_confidence` - Round 1 confidence
- `round2_prediction` - Round 2 model prediction
- `round2_confidence` - Round 2 confidence
- `round3_prediction` - Round 3 model prediction
- `round3_confidence` - Round 3 confidence

Useful for:
- Verifying model consistency
- Understanding model evolution
- Detecting discrepancies between rounds

### Option 4: Show Model Information

Displays:
- Model path and type
- Number of features (13)
- Number of classes (2: Benign, Attack)
- Model parameters

### Option 5: Exit

Closes the application.

## Programmatic Usage

Use `predict.py` functions in your own Python code:

### Example 1: Single Sample Prediction

```python
from predict import load_model_and_encoder, predict_single_sample

# Load model
model, le = load_model_and_encoder()

# Create sample
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

# Predict
result = predict_single_sample(model, le, sample)

# Use result
if result['success']:
    print(f"Class: {result['prediction']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Probabilities: {result['probabilities']}")
else:
    print(f"Error: {result['error']}")
```

### Example 2: Batch Prediction from CSV

```python
from predict import load_model_and_encoder, predict_batch_csv

# Load model
model, le = load_model_and_encoder()

# Predict on CSV
results = predict_batch_csv(model, le, "dataset/sample.csv")

# Save to file
if results is not None:
    results.to_csv("predictions.csv", index=False)
    print("Predictions saved!")
```

### Example 3: Prediction from DataFrame

```python
import pandas as pd
from predict import load_model_and_encoder, predict_from_dataframe

# Load data
df = pd.read_csv("dataset/sample.csv")

# Load model
model, le = load_model_and_encoder()

# Predict
results = predict_from_dataframe(model, le, df)

# Use results
print(results[['predicted_class', 'confidence']])
```

### Example 4: Compare Rounds

```python
from predict import predict_with_different_rounds

# Get predictions from all rounds
results = predict_with_different_rounds("dataset/sample.csv")

# Save comparison
results.to_csv("round_comparison.csv", index=False)

# Analyze differences
print(results[['main_prediction', 'round1_prediction', 'round2_prediction', 'round3_prediction']])
```

## Input Feature Columns (Order Matters)

The 13 required features in exact order:

1. `frame.len` - Frame length
2. `ip.proto` - IP protocol number
3. `ip.checksum` - IP checksum value
4. `ip.tos` - IP Type of Service
5. `tcp.srcport` - TCP source port
6. `tcp.dstport` - TCP destination port
7. `tcp.flags` - TCP flags
8. `tcp.window_size_value` - TCP window size
9. `tcp.window_size_scalefactor` - TCP window scale factor
10. `tcp.checksum` - TCP checksum
11. `tcp.pdu.size` - TCP PDU size
12. `udp.srcport` - UDP source port
13. `udp.dstport` - UDP destination port

**Note:** Hex values (starting with "0x") are automatically converted to numeric values.

## Output Interpretation

### Prediction Output

**Predicted Class:**
- `Benign` - Network traffic appears normal
- `Attack` - Network traffic shows signs of attack/anomaly

**Confidence Score (0-1):**
- 0.5-0.7 = Low confidence (unreliable prediction)
- 0.7-0.85 = Medium confidence (reasonable prediction)
- 0.85-0.95 = High confidence (reliable prediction)
- >0.95 = Very high confidence (very reliable prediction)

### Probability Distribution

Shows probability for each class:
- Sum of all probabilities = 1.0
- Higher probability = more likely that class
- Use to understand model uncertainty

## Common Tasks

### Task 1: Predict on New CSV File
```
python predict.py
→ Select option 2
→ Enter CSV path
→ Get _predictions.csv output file
```

### Task 2: Check if System Detects Attacks
```
python predict.py
→ Select option 3 (Compare rounds)
→ Look for "Attack" predictions
→ Check confidence scores
```

### Task 3: Verify Model Consistency
```
python predict.py
→ Select option 3
→ Compare main vs round predictions
→ Check if all models agree
```

### Task 4: Integrate with Your Application
```python
# In your application code:
from predict import load_model_and_encoder, predict_batch_csv

model, le = load_model_and_encoder()
results = predict_batch_csv(model, le, "new_data.csv")
# Use results...
```

## Troubleshooting

### Issue: Model not found
**Solution:** Ensure `models/network_sgd_classifier.joblib` exists in your project directory

### Issue: Missing features error
**Solution:** Ensure your CSV has all 13 required feature columns

### Issue: ValueError when entering numbers
**Solution:** Enter values separated by commas, e.g., `164,6,0x736d,128,...`

### Issue: Predictions seem wrong
**Solution:** 
- Check input data preprocessing (hex values, NaN handling)
- Verify feature order matches FEATURE_COLS
- Compare with test.py results on known data

### Issue: Different predictions for same input
**Solution:** This is normal - some variation is expected. Check confidence scores.

## Performance Tips

1. **Batch Processing** - Use CSV prediction for large datasets (faster)
2. **Round Comparison** - Use when debugging to compare models
3. **Confidence Scores** - High confidence predictions are more reliable
4. **Monitor Trends** - Track predictions over time for anomaly detection

## Output Files

When using batch prediction:
- Input: `dataset/sample.csv`
- Output: `dataset/sample_predictions.csv`

When comparing rounds:
- Input: `dataset/sample.csv`
- Output: `dataset/sample_all_rounds.csv`

## Function Reference

### `load_model_and_encoder()`
- Loads trained model and label encoder
- Returns: (model, label_encoder) or (None, None)

### `predict_single_sample(model, le, features_dict)`
- Predicts class for single sample
- Returns: Dictionary with prediction results

### `predict_batch_csv(model, le, csv_path)`
- Predicts on entire CSV file
- Returns: DataFrame with predictions

### `predict_from_dataframe(model, le, df)`
- Predicts on provided DataFrame
- Returns: DataFrame with predictions added

### `predict_with_different_rounds(csv_path)`
- Gets predictions from all 4 models
- Returns: DataFrame with all predictions

### `interactive_prediction(model, le)`
- Runs interactive prediction mode
- No return value

## Integration Examples

### Example 1: Real-time Monitoring
```python
import pandas as pd
from predict import load_model_and_encoder, predict_single_sample

model, le = load_model_and_encoder()

# Simulate real-time traffic
traffic_samples = [
    {"frame.len": 164, "ip.proto": 6, ...},
    {"frame.len": 72, "ip.proto": 17, ...},
]

for sample in traffic_samples:
    result = predict_single_sample(model, le, sample)
    if result['success'] and result['prediction'] == 'Attack':
        print(f"ALERT: Attack detected with {result['confidence']:.2%} confidence")
```

### Example 2: Batch Analysis
```python
from predict import load_model_and_encoder, predict_batch_csv

model, le = load_model_and_encoder()
results = predict_batch_csv(model, le, "traffic.csv")

# Find attacks
attacks = results[results['predicted_class'] == 'Attack']
print(f"Found {len(attacks)} potential attacks")
print(f"Confidence range: {attacks['confidence'].min():.2%} - {attacks['confidence'].max():.2%}")
```

---

**Created:** November 11, 2025
**Status:** Ready for Production
**Version:** 1.0

