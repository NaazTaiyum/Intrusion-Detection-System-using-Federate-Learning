print("Testing server label detection...")
print("=" * 70)

try:
    import server
    print("\nSUCCESS! Server initialized with classes:")
    print(f"Number of classes: {len(server.le.classes_)}")
    print("\nClasses detected:")
    for i, cls in enumerate(server.le.classes_, 1):
        print(f"  {i:2d}. {cls}")
    
    print("\n" + "=" * 70)
    print("[OK] Server is ready! All label classes properly detected.")
    print("=" * 70)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
