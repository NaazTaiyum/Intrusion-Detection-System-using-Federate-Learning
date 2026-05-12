# QUICK FIX GUIDE

## What Happened
Client crashed with: `ValueError: y contains previously unseen labels: 'Telnet'`

## Why
Server was only detecting 2 classes, but dataset has 13 unique attack/behavior types.

## What's Fixed
✅ Server now scans ALL 195 CSV files completely
✅ Detects all 13 labels
✅ Client receives complete label list from server
✅ No more ValueError

## What to Do Now

### Option 1: Fresh Start (Recommended)
```bash
REM Delete old label encoder
del models\label_encoder.joblib

REM Delete old models if you want to retrain from scratch  
del models\network_sgd_classifier*.joblib

REM Terminal 1: Start server (will auto-detect all 13 labels)
python server.py

REM Terminal 2: Start client
python client.py
REM When prompted:
REM   Path: F:\federate_learning\dataset\part1
REM   IP: 127.0.0.1
REM   Port: 8080
```

### Option 2: Keep Existing Models
```bash
REM Just delete the old encoder (keeps trained models)
del models\label_encoder.joblib

REM Terminal 1: Start server
python server.py

REM Terminal 2: Start client  
python client.py
```

## Expected Output

### Server Console:
```
[INFO] Scanning 195 CSV files for all unique labels...
[INFO] Auto-detected 13 classes:
       1. Benign
       2. Ingress Tool Transfer
       3. Merlin C&C Communication
       4. Merlin ICMP Flooding
       5. Merlin TCP Flooding
       6. Merlin UDP Flooding
       7. Mirai C&C Communication
       8. Mirai GRE Flooding
       9. Mirai TCP Flooding
      10. Mirai UDP Flooding
      11. Telnet Brute Force
      12. TCP Scan
      13. Unknown
[INFO] Saved label encoder to models/label_encoder.joblib
[Server] aggregate_fit called for round 1...
```

### Client Console:
```
Initializing client...
Loaded iotsim-domotic-monitor-2.csv shape=(1660, 23)
...
>>> fit() called by server. config keys: ['rnd', 'classes_json', 'n_features']
Client initialized inside fit(): data and model ready.
Training locally on XXXXX examples...
Local training done; returning parameters to server.
```

## Key Improvements
- ✅ All 13 classes supported automatically
- ✅ Chunked file reading (memory efficient)  
- ✅ Future-proof (works with any number of classes)
- ✅ No hardcoding of class names

## Questions?
See `FIX_DOCUMENTATION.md` for detailed technical explanation.
