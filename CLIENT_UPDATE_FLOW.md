# How Client Updates the Model - Complete Flow

## Overview
Clients update models through **two mechanisms**:
1. **Federated Learning (Every FL Round)** - via server.py
2. **Periodic Updates to Server (Every 3 Days)** - via HTTP

---

## Mechanism 1: Federated Learning (Real-time, Every Round)

### Flow Diagram:
```
┌──────────────────────────────────────────────────────────────────┐
│                     FEDERATED LEARNING CYCLE                     │
└──────────────────────────────────────────────────────────────────┘

Round N:
  1. Server broadcasts current model to all clients
       ↓
  2. Each client receives (coef, intercept) from server
       ↓
  3. Client.set_parameters(parameters)
       └─→ Assigns server weights to local model
       └─→ self.model.coef_ = server_coef
       └─→ self.model.intercept_ = server_intercept
       ↓
  4. Client.fit() - LOCAL TRAINING
       └─→ Train on local data with server's weights
       └─→ self.model.partial_fit(X_train, y_train)
       └─→ Model learns from local data
       ↓
  5. Client returns updated (coef, intercept)
       └─→ Local training results
       ↓
  6. Server aggregates updates from all clients
       └─→ Weighted average of all client updates
       └─→ Creates new global model
       ↓
  Round N+1: Repeat with new global model
```

### Code Flow in `client.py`:

```python
# STEP 1: Server calls get_parameters() to get initial weights
def get_parameters(self, config):
    return [self.model.coef_.astype(np.float32), 
            self.model.intercept_.astype(np.float32)]

# STEP 2: Server calls set_parameters() to send its weights
def set_parameters(self, parameters):
    coef, intercept = parameters
    # Override local model with server's model
    self.model.coef_ = coef_arr
    self.model.intercept_ = intercept_arr
    print("✓ Loaded server parameters")

# STEP 3: Server calls fit() to train locally
def fit(self, parameters, config):
    # Get server's parameters and set them
    self.set_parameters(parameters)
    
    # Train on LOCAL DATA with server's weights
    X_train_arr = np.asarray(self.X_train, dtype=np.float64)
    y_train_arr = np.asarray(self.y_train, dtype=np.int64)
    print(f"Training locally on {len(X_train_arr)} examples...")
    self.model.partial_fit(X_train_arr, y_train_arr)  # ← LOCAL LEARNING
    print("✓ Local training done")
    
    # Save local update (BONUS: for 3-day aggregation)
    self.save_model_update(len(X_train_arr))
    
    # Return updated model to server
    return (
        [self.model.coef_.astype(np.float32),
         self.model.intercept_.astype(np.float32)],
        len(X_train_arr),  # Sample count
        metrics
    )

# STEP 4: Server aggregates and creates new global model
# (Server-side, not shown here)
```

---

## Mechanism 2: Periodic HTTP Updates (Every 3 Days)

### When Clients Send Updates:

```python
# In fit() method - after local training:
self.save_model_update(len(X_train_arr))  # Called every FL round
    ↓
    └─→ save_model_update() function:
         ├─→ Save locally: models/client_updates/client_default_update.joblib
         └─→ If >= 3 days since last send:
             └─→ Call _send_update_to_server()
                 ├─→ Convert coef/intercept to JSON
                 ├─→ POST to http://SERVER:5000/upload_client_update
                 └─→ Server receives and saves it
```

### Code Flow:

```python
def save_model_update(self, n_samples):
    """Save locally and send to server every 3 days."""
    
    # STEP 1: Save locally
    update_data = {
        "coef": self.model.coef_.astype(np.float64),
        "intercept": self.model.intercept_.astype(np.float64),
        "n_samples": int(n_samples),
    }
    fname = os.path.join(CLIENT_UPDATES_DIR, f"client_default_update.joblib")
    joblib.dump(update_data, fname)
    print(f"✓ Saved locally: {fname}")
    
    # STEP 2: Send to server if 3 days have passed
    now = datetime.utcnow()
    if self._last_update_time is None or \
       (now - self._last_update_time) >= timedelta(days=UPDATE_INTERVAL_DAYS):
        self._send_update_to_server(client_id, update_data)
        self._last_update_time = now  # Update timestamp


def _send_update_to_server(self, client_id, update_data):
    """Send update to server via HTTP."""
    
    # Convert numpy arrays to JSON-serializable lists
    payload = {
        "client_id": str(client_id),
        "coef": update_data["coef"].tolist(),  # numpy → list
        "intercept": update_data["intercept"].tolist(),  # numpy → list
        "n_samples": int(update_data["n_samples"]),
    }
    
    # POST to server's HTTP endpoint
    response = requests.post(
        f"{SERVER_HTTP_URL}/upload_client_update",
        json=payload,
        timeout=10,
    )
    
    if response.status_code == 200:
        print(f"✓ Sent to server: {response.json()}")
    else:
        print(f"✗ Server error: {response.status_code}")
```

---

## How Server Receives & Aggregates (3-Day Cycle)

### Server-Side Flow:

```
Server HTTP Endpoint (port 5000):
  POST /upload_client_update
    ↓
    └─→ Receive from client (every 3 days):
        {
          "client_id": "client_1",
          "coef": [[...], [...], ...],
          "intercept": [...],
          "n_samples": 5000
        }
    ↓
    └─→ Save to: models/client_updates/client_1_update.joblib
    ↓
    └─→ Return: {"status": "success"}

────────────────────────────────

Every 3 Days - Retrain Process:
  retrain.py runs automatically
    ↓
    └─→ Load all client updates:
        ├─ models/client_updates/client_1_update.joblib
        ├─ models/client_updates/client_2_update.joblib
        └─ models/client_updates/client_3_update.joblib
    ↓
    └─→ Aggregate (weighted by n_samples):
        new_coef = (coef_1 * weight_1 + coef_2 * weight_2 + coef_3 * weight_3)
        new_intercept = (intercept_1 * weight_1 + ...)
    ↓
    └─→ Update global model:
        models/network_sgd_classifier.joblib
    ↓
    └─→ Create backup:
        models/network_sgd_classifier_aggregated_20251207T123456Z.joblib
```

---

## Timeline Example

### Scenario: 2 Clients, Server Running Continuously

```
Time          Client 1                    Server                      Retrain
─────────────────────────────────────────────────────────────────────────────

00:00  Round 1:
       ├─ Receives global model
       ├─ Trains locally
       ├─ Saves update (local only)
       └─ Sends coef/intercept        → Receives
                                       → Aggregates
                                       → Creates new model (v2)

12:00  Round 2:
       ├─ Receives global model v2
       ├─ Trains locally
       ├─ Saves update (local only)
       └─ Sends coef/intercept        → Receives
                                       → Aggregates
                                       → Creates new model (v3)

1 day: Round 3:
       ├─ Receives global model v3
       ├─ Trains locally
       ├─ Saves update (local only)
       └─ Sends coef/intercept        → Receives
                                       → Aggregates
                                       → Creates new model (v4)

3 days: (Periodic Update Timer Expires)
       ├─ Trains locally
       └─ Sends to HTTP                → Receives
       (FIRST 3-DAY HTTP SEND)         → Saves to client_updates/
                                       
                                       ← Starts aggregation
                                          Loads all saved updates
                                          (from past 3 days)
                                          Aggregates them
                                          Updates global model

6 days: (Periodic Update Timer Expires Again)
       ├─ Trains locally
       └─ Sends to HTTP                → Receives
       (SECOND 3-DAY HTTP SEND)        → Saves to client_updates/
       
                                       ← (waits for next 3-day cycle)
```

---

## Configuration

### To Set Server IP (for different PCs):

Edit `client.py`:
```python
# For server on same PC:
SERVER_HTTP_URL = "http://localhost:5000"

# For server on different PC (e.g., 192.168.1.100):
SERVER_HTTP_URL = "http://192.168.1.100:5000"
```

### To Set Client ID:

```python
client = NetworkTrafficClient(folder_path)
client.client_id = "client_1"  # or "client_2", etc.
```

### To Change 3-Day Interval:

Edit `client.py`:
```python
UPDATE_INTERVAL_DAYS = 7  # Change to 7 days, 1 day, etc.
```

---

## Summary: Two Types of Updates

| Aspect | Federated Learning | 3-Day HTTP Sends |
|--------|-------------------|------------------|
| **Frequency** | Every FL round | Every 3 days |
| **Purpose** | Real-time global model synchronization | Periodic aggregation backup |
| **Protocol** | Flower gRPC | HTTP REST |
| **Direction** | Bidirectional (client ↔ server) | Unidirectional (client → server) |
| **Storage** | In-memory on server | File-based (`client_updates/`) |
| **When Used** | Active FL rounds | Between FL rounds |

---

## Quick Reference: What Gets Updated Where

```
Client Local Model Updates:
└─ models/client_updates/client_default_update.joblib
   (Every FL round)

Server Receives (via HTTP):
└─ models/client_updates/client_1_update.joblib
└─ models/client_updates/client_2_update.joblib
└─ models/client_updates/client_3_update.joblib
   (Every 3 days from each client)

Server Aggregates (every 3 days):
└─ models/network_sgd_classifier.joblib
   (Global model updated with weighted average)

Backup Timestamped:
└─ models/network_sgd_classifier_aggregated_20251207T123456Z.joblib
```
