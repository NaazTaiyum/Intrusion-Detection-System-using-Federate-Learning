# 🛡️ Federated Learning–Based Intrusion Detection System (IDS)

    This project implements a **Federated Learning Intrusion Detection System (IDS)** where multiple distributed clients collaboratively train a machine learning model without sharing raw datasets. Each client trains locally and sends only model updates to the server, ensuring data privacy and scalability.

---

## 🚀 Key Features

    - **Federated Learning Architecture**
      - Multiple clients train on local CSV datasets
      - Model updates sent every round using HTTP POST
      - Flower server orchestrates federated rounds via gRPC

    - **Privacy-Preserving Training**
     - Raw data stays on client devices
      - Only model weights + sample counts are transmitted

    - **Model Aggregation (Day 3 Cycle)**
      - Weighted averaging of client updates
      - Automatic global model update every 3 days
      - Timestamped model persistence

    - **Modular and Extensible**
      - Add/remove clients anytime
      - Works on LAN (multi-PC support)
      - Uses scikit-learn’s incremental learner: `SGDClassifier.partial_fit()`

---

## 📁 Project Structure

    federated-learning-system/
    ├── client/
    │ ├── client.py # Client-side local training
    │ ├── data/ # Local CSV datasets
    │ └── saved_models/ # Local model storage

    federated-learning-system/
    ├── server/
    │ ├── server.py # Flower server (gRPC 8080) + Flask (5000)
    │ ├── retrain.py # Aggregation every 3 days
    │ └── models/
    │ ├── network_sgd_classifier.joblib
    │ └── client_updates/ # Stores uploaded local updates
    │
    └── README.md


---

## 🧠 System Workflow

### **Day 1–2: Client Training & Upload**
    1. Load CSV dataset  
    2. Preprocess features  
    3. Train using `partial_fit()`  
    4. Save local update  
    5. Upload update to server via Flask API  
    6. Flower server coordinates FL rounds

### **Day 3: Aggregation Phase**
    1. `retrain.py` loads all client update files  
    2. Validates shapes and class sizes  
    3. Performs **weighted average**:
       - weight = `client_samples / total_samples`
    4. Updates global model coefficients  
    5. Saves global model + timestamp backup  
    6. Restarts FL cycle

---

## 🔧 Technologies Used

    - Python 3  
    - Flower Federated Learning Framework  
    - Flask (HTTP API for client updates)  
    - scikit-learn (`SGDClassifier`)  
    - NumPy / Pandas  
    - Joblib  

---

## 🌐 Multi-PC Support

    - Same PC:  
      `127.0.0.1:5000` (HTTP)  
      `127.0.0.1:8080` (gRPC)

    - Different PCs on LAN:  
      Set server IP in `client.py`  
      Example:  
      `SERVER_URL = "http://192.168.0.102:5000"`

---

## 📈 Advantages of This System

    - Data privacy maintained  
    - Incremental learning ensures low resource usage  
    - Supports many clients with asynchronous updates  
    - Ideal for distributed IDS deployment in organizations  

---

## 🔮 Future Improvements

    - Secure aggregation (encrypted updates)  
    - Deep learning models (CNN/LSTM)  
    - Real-time monitoring dashboard  
    - Docker/Kubernetes deployment  

---

## 📬 Contribution

    Pull requests are welcome.  
    For major changes, open an issue first to discuss what you’d like to modify.

---

## Requirements(pip install requirements)
    flwr
    flask
    scikit-learn
    numpy
    pandas
    joblib

# On the server machine
    python server/server.py    # starts Flower + Flask (or whichever entrypoint you have)
    python server/retrain.py   # if retrain isn't launched by server

# On each client
    python client/client.py    # ensure SERVER_URL is set in the client or passed as arg

## 🔄 System Workflow (Simplified)
                 +--------------------+
                 |     Server         |
                 | (Flower + Flask)   |
                 +--------------------+
                       ↑        ↓
             Global model   Aggregated updates
                       ↑        ↓
         -------------------------------------------
         |                  |                      |
      +--------+       +--------+            +-----------+
      | Client |       | Client |            |  Client   |
      |   #1   |       |   #2   |            |    #N     |
      +--------+       +--------+            +-----------+
          ↑               ↑                        ↑
       Local training   Local training          Local training
          ↑               ↑                        ↑
          Raw data stays on each client device



