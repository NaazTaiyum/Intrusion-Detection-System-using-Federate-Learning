# Federated Learning Model Testing Guide

## Overview
The `test.py` script provides comprehensive testing and validation for your federated learning intrusion detection system. It evaluates model accuracy across federated rounds and verifies client training progress.

## What the Test Script Does

### 1. **Model Evaluation**
- Loads all trained models (main model + 3 federated rounds)
- Tests each model on your dataset
- Calculates accuracy, precision, recall, F1-score, and log loss
- Displays confusion matrices and per-class metrics

### 2. **Training Progress Analysis**
- Compares model weights across federated rounds
- Detects if clients are properly training
- Shows weight changes and percentage improvements
- Provides training verdict (✓ OK or ✗ FAILED)

## Running the Test

```bash
cd F:\federate_learning
python test.py
```

## Understanding the Output

### Model Evaluation Section
```
[1/4] Testing Main Model...
  [OK] Loaded model: models\network_sgd_classifier.joblib

  EVALUATING: Main Model
Test Samples: 17979
Accuracy:     1.0000 (100.00%)
Precision:    1.0000
Recall:       1.0000
F1-Score:     1.0000
Log Loss:     0.0067
```

**What this means:**
- **Accuracy**: Percentage of correct predictions (100% = perfect)
- **Precision**: Of all positive predictions, how many were correct
- **Recall**: Of all actual positives, how many were found
- **F1-Score**: Balanced score between precision and recall
- **Log Loss**: Lower is better (0 = perfect, higher = worse)

### Client Training Analysis Section
```
Model           | Coef L2-Norm    | Intercept
Main            | 0.000000        | -5.000000
Round 1         | 80.297656       | -5.066862
Round 2         | 40.426038       | -5.066862
Round 3         | 27.012863       | -5.066862

Weight Changes Between Rounds:
Main -> Round 1      | Change: +80.297656 (+0.00%)
Round 1 -> Round 2   | Change: -39.871618 (-49.65%)
Round 2 -> Round 3   | Change: -13.413176 (-33.18%)

[OK] Client is properly training!
  Average weight change: 44.527483
  Models are being updated with client data each round.
```

**What this means:**
- **Coef L2-Norm**: The magnitude of model weights (how "trained" the model is)
- **Large changes between rounds** = Client is learning and updating the model
- **Small/no changes** = Client may not be training properly
- **Average weight change > 1e-6** = Training is working

## Key Metrics to Watch

### ✓ Healthy Signs
1. **High Accuracy** (> 95%)
2. **Consistent F1-Score** (close to accuracy)
3. **Low Log Loss** (close to 0)
4. **Significant Weight Changes** between federated rounds
5. **Decreasing Log Loss** across rounds (improvement)

### ✗ Warning Signs
1. **Low Accuracy** (< 70%)
2. **Very High Precision but Low Recall** (model too conservative)
3. **High Log Loss** (> 1)
4. **No Weight Changes** between rounds (client not training)
5. **Increasing Log Loss** (model getting worse)

## Customization

### Test a Specific Model
```python
# At the bottom of test.py, uncomment:
test_single_model("models/network_sgd_classifier_round1.joblib", "dataset")
```

### Test on Different Dataset
```python
test_single_model("models/network_sgd_classifier.joblib", "path/to/your/dataset")
```

### Adjust Test/Train Split
In `test_all_models()` function, change the `test_size` parameter:
```python
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3,  # Change 0.2 to 0.3 for 70/30 split
    random_state=42, 
    stratify=y
)
```

## Features

- ✓ Loads all 4 models (main + 3 rounds)
- ✓ Comprehensive metrics (accuracy, precision, recall, F1, loss)
- ✓ Confusion matrix for each model
- ✓ Per-class performance breakdown
- ✓ Client training verification
- ✓ Weight change analysis
- ✓ Training verdict (OK/FAILED)
- ✓ Progress summary
- ✓ Error handling and validation

## Dataset Requirements

Your dataset CSV files must have:
1. **All 13 feature columns** (as defined in `FEATURE_COLS`)
2. **A 'label' column** with class labels (Benign/Attack)

Feature columns required:
- frame.len
- ip.proto
- ip.checksum
- ip.tos
- tcp.srcport
- tcp.dstport
- tcp.flags
- tcp.window_size_value
- tcp.window_size_scalefactor
- tcp.checksum
- tcp.pdu.size
- udp.srcport
- udp.dstport

## Dependencies

```bash
pip install pandas numpy scikit-learn joblib
```

## Troubleshooting

### Issue: "Dataset path not found"
**Solution**: Ensure your dataset folder is at `F:\federate_learning\dataset`

### Issue: "Missing required feature columns"
**Solution**: Verify your CSV files have all 13 required features

### Issue: "label column not found"
**Solution**: Ensure your CSV files have a 'label' column with class labels

### Issue: "Model weights are not changing"
**Possible causes:**
- Client is not receiving data
- Client data is not being used for training
- Network connection issues between client and server
- Check client.py logs for errors

## Example Interpretation

From the test output above:

1. **Model Accuracy**: All models achieve 100% accuracy on test data
2. **Model Improvement**: No change in accuracy across rounds (both at 100%)
3. **Client Training**: Weight changes show:
   - Round 1: Massive increase (+80.3) - initial learning
   - Round 2: Decrease (-39.9, -49.65%) - model consolidation
   - Round 3: Decrease (-13.4, -33.18%) - fine-tuning
4. **Verdict**: Client IS properly training (weight changes present)
5. **Conclusion**: Your federated learning setup is working correctly!

## Next Steps

1. If accuracy is low, check your feature preprocessing
2. If no weight changes, debug the federated learning pipeline
3. Consider testing on datasets with "Attack" samples for true validation
4. Monitor log loss trends over multiple rounds

