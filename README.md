# 🛡️ FraudShield: AI-Powered UPI Fraud Prevention

**FraudShield** is a secure, intelligent UPI transaction simulation built on Django. It integrates real-time Machine Learning and geospatial analysis to detect and block fraudulent financial activities before they settle.

## 🧠 Core AI & Security Features

### 1. Machine Learning Fraud Detection
- **Algorithm**: Random Forest Classifier (Scikit-Learn).
- **Training Data**: Trained on synthetic datasets including legitimate and fraudulent patterns.
- **Features Analyzed**:
  - Transaction Amount
  - Time of Day (Hourly patterns)
  - Cyclical Time Encoding (Day of Week)
  - Geospatial Distance (Haversine)

### 2. Geospatial "Impossible Travel" Analysis
- **Logic**: Implements the **Haversine Formula** to calculate the distance between the user's last known location and the current transaction location.
- **Trigger**: Blocks transactions if the velocity implies travel > 100km within 1 hour.

### 3. Risk-Based Authentication & Emergency Override
- **Safety Valve**: Recognizes that AI can yield false positives.
- **Flow**:
  1. High-Risk Transaction detected (>80% Fraud Probability).
  2. Transaction status set to `PENDING_VERIFICATION`.
  3. User redirected to **Emergency Verification Board**.
  4. Client-side OTP simulation verifies human presence.
  5. Valid OTP finalizes the transaction securely.

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Backend Framework** | Django (Python) |
| **ML Engine** | Scikit-Learn, Pandas, Joblib |
| **Database** | SQLite (Default) |
| **Frontend** | HTML5, CSS3, JavaScript |
| **Security** | Django Auth, CSRF Protection |

## 🏗️ Project Architecture

1.  **Initiation**: User submits payment via `send_money` view.
2.  **Analysis**:
    *   `analyze_risk()` function is called.
    *   **Heuristics**: Checks balance, "Bad Actor" reports, and Night Owl patterns.
    *   **AI Inference**: Loads `fraud_model.pkl` to predict fraud probability.
3.  **Decision**:
    *   **Safe**: Transaction succeeds.
    *   **Suspicious**: Transaction Blocked or Sent for Verification.
4.  **Logging**: All events recorded in `Transaction` and `LocationHistory` models.

## 🚀 Setup & Installation

Follow these steps to deploy FraudShield locally.

### 1. Clone & Install Dependencies
```bash
# Install required python packages
pip install django pandas scikit-learn joblib
```

### 2. Database Initialization
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. AI System Bootstrap
Generate synthetic training data and train the model.
```bash
# Generate 500+ synthetic transactions for training
python manage.py generate_ai_data

# Train the Random Forest Model (Creates fraud_model.pkl)
python train_fraud_model.py
```

### 4. Run the Server
```bash
python manage.py runserver
```
Access the application at `http://127.0.0.1:8000`.

## 👮 Admin Dashboard

The default Django Admin is enhanced for fraud monitoring:
- **Color-Coded Status**:
  - 🔴 **BLOCKED**: Confirmed threats.
  - 🟠 **PENDING_VERIFICATION**: Awaiting interactions.
  - 🟢 **SUCCESS**: Verified payments.
- **Metrics**: View `Fraud Score` and `Is Suspicious` flags directly in the transaction list.
