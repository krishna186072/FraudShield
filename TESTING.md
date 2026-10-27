# 🧪 FraudShield Testing Guide

This document provides credentials and step-by-step workflows to verify the FraudShield application features.

## 🔐 Test Credentials

**Note**: System time is set to **Asia/Kolkata (IST)**. All transaction times will appear in local Indian time.

**Administrator** (Full Access)
- **Username**: `admin`
- **Password**: `admin123`

**Standard User** (High Balance for Testing)
- **Username**: `user1`
- **Password**: `user123`
- **Current Balance**: ~₹5,00,000

---

## 🏗️ Test Scenarios

### Workflow 1: The "Emergency Override" (Main Feature)
**Goal**: Verify that a high-risk transaction (Blocked by Rule #4 "Bad Actor") allows the user to use the OTP override if they have sufficient funds.

1.  **Login** as `user1` / `user123`.
2.  Navigate to **Send Money**.
3.  Enter the following details:
    -   **Receiver UPI**: `user3@upi` (This user is flagged as a "Bad Actor" in the database).
    -   **Amount**: `50000` (A significant amount).
    -   **Description**: "Test Override".
4.  Click **Send**.
5.  **Observation**:
    -   You are redirected to the **"High Risk Detected"** page.
    -   *Note: Standard block would just show an error message.*
6.  **Action**:
    -   Click **"Confirm Emergency Payment"**.
    -   Wait 3 seconds for the simulation to generate a code.
    -   A 6-digit code will appear (e.g., `123456`).
    -   Enter the code in the input box.
    -   Click **"Finalize Payment"**.
7.  **Result**: 
    -   Transaction is successful.
    -   **Check History**: Look for the transaction. It will be marked as <span style="color: #d32f2f; font-weight: bold;">● Verified High Risk</span> (Red/Bold), distinct from normal green success.

### Workflow 2: Genuine Block (Insufficient Funds)
**Goal**: Verify that the safety valve **only** opens if the user can actually afford the transaction.

1.  **Login** as `user1`.
2.  Navigate to **Send Money**.
3.  Enter Details:
    -   **Receiver UPI**: `user3@upi` (Bad Actor).
    -   **Amount**: `1000000` (10 Lakhs - exceeds your 5 Lakh balance).
4.  Click **Send**.
5.  **Result**: 
    -   **Transaction Declined**.
    -   Message: *"Insufficient balance"* or *"Blocked due to suspicious activity"*.
    -   **No** redirection to the verification page.

### Workflow 3: AI Fraud Detection
**Goal**: Test the Machine Learning model's reaction to "Impossible" transactions.

1.  **Login** as `user1`.
2.  Navigate to **Send Money**.
3.  Enter Details:
    -   **Receiver UPI**: `user2@upi` (Good user).
    -   **Amount**: `90000` (High amount).
    -   **City**: *leave as default or change*.
4.  **Note**: Since we cannot easily simulate "GPS Teleporting" in the browser without backend tools, the AI might rely on the **Amount** and **Time** features. 
    -   If the AI predicts Probability > 80%, it will block.
    -   If blocked, you will see *"Transaction declined by FraudShield AI security."*

---

## 👮 Admin Monitoring

1.  **Logout** and login as **`admin`** / **`admin123`**.
2.  Go to the **Admin Dashboard** (`/admin/`).
3.  Click on **Transactions**.
4.  **Verify**:
    -   Locate your recent transactions.
    -   Check the **Status** column:
        -   <span style="color:orange">**PENDING_VERIFICATION**</span> (If you abandoned the override flow).
        -   <span style="color:green">**SUCCESS**</span> (If you completed it).
        -   <span style="color:red">**BLOCKED**</span> (If AI/Rules blocked it).
    -   Check the **Fraud Score** column (Should be high, e.g., >100 for Bad Actor).
