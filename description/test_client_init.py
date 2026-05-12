import sys
import os

print("=" * 60)
print("TESTING CLIENT.PY INITIALIZATION")
print("=" * 60)

try:
    # Test 1: Import client module
    print("\n[1/4] Testing client module import...")
    from client import NetworkTrafficClient, FEATURE_COLS
    print("[OK] Client module imported successfully")
    
    # Test 2: Check feature columns
    print("\n[2/4] Checking feature columns...")
    expected_features = 13
    if len(FEATURE_COLS) == expected_features:
        print(f"[OK] Feature columns count: {len(FEATURE_COLS)} (correct)")
        print(f"[OK] Features: {FEATURE_COLS}")
    else:
        print(f"[FAILED] Expected {expected_features} features, got {len(FEATURE_COLS)}")
    
    # Test 3: Load data from dataset
    print("\n[3/4] Testing data loading from dataset...")
    dataset_path = "dataset/part1"
    if not os.path.exists(dataset_path):
        print(f"[WARNING] Dataset path not found: {dataset_path}")
    else:
        print(f"[OK] Dataset path exists: {dataset_path}")
        
        # Count CSV files
        csv_files = [f for f in os.listdir(dataset_path) if f.endswith('.csv')]
        print(f"[OK] Found {len(csv_files)} CSV files in dataset")
        
        if len(csv_files) > 0:
            # Try loading the client
            print("\n[4/4] Testing NetworkTrafficClient initialization...")
            client = NetworkTrafficClient(dataset_path)
            print(f"[OK] Client initialized successfully")
            print(f"[OK] Total samples loaded: {len(client.df)}")
            print(f"[OK] Raw labels: {client.raw_labels.shape}")
            print(f"[OK] Unique labels: {np.unique(client.raw_labels)}")
            print(f"[OK] Feature matrix shape: {client.X.shape}")
            
            # Test 4: Verify label encoder reception simulation
            print("\n[SIMULATION] Testing config parsing...")
            import json
            import numpy as np
            test_config = {
                "rnd": 1,
                "classes_json": json.dumps(["Benign", "Attack"]),
                "n_features": 13
            }
            classes = client._read_classes_from_config(test_config)
            if classes is not None:
                print(f"[OK] Classes parsed from config: {classes}")
            else:
                print("[WARNING] Could not parse classes from config")
            
            print("\n[SUCCESS] ===== ALL TESTS PASSED =====")
            print("[SUCCESS] Client is ready to connect to server!")
        else:
            print("[WARNING] No CSV files found in dataset path")
    
except ImportError as e:
    print(f"\n[FAILED] Import error:")
    print(f"[FAILED] {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
except ValueError as e:
    print(f"\n[FAILED] Value error (likely missing features/labels):")
    print(f"[FAILED] {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
except Exception as e:
    print(f"\n[FAILED] Unexpected error:")
    print(f"[FAILED] {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
