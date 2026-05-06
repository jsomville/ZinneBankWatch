from datetime import datetime, timedelta, timezone
import json
import os

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

LAST_CHECK_FILE = os.path.join(DATA_FOLDER, "last_check.json")

DATA_CHECK_FOLDER = os.path.join(DATA_FOLDER, "checks")
if not os.path.exists(DATA_CHECK_FOLDER):
    os.makedirs(DATA_CHECK_FOLDER)

TRANSACTIONS_CHECK_FILE = os.path.join(DATA_FOLDER, "transactions.json")

TRANSACTION_DAYS_TO_KEEP = 90

def save_last_check(account_details):
    """Save the last check information to a file"""
    data = {
        "availableBalance": account_details.get("availableBalance"),
        "currentBalance": account_details.get("currentBalance"),
        "account_number": account_details.get("iban"),
        "last_check": datetime.now().isoformat(),
    }

    with open(LAST_CHECK_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_last_check():
    """Load the last check information from the file and return it as a dictionary, or return None if the file does not exist"""
    if os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE, "r") as f:
            data = json.load(f)
            return data
    return None

def save_transactions(transactions):
    """Save the transactions to a file"""

    # Cleanup older transactions, to avoid keeping too much data in the file
    if transactions is not None:
        transactions = [
            t
            for t in transactions
            if get_transaction_date(t).date()
            > datetime.now().date() - timedelta(days=TRANSACTION_DAYS_TO_KEEP)
        ]

    # Save Transactions to file
    with open(TRANSACTIONS_CHECK_FILE, "w") as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)


def load_transactions():
    """Load the transactions from the file and return it as a list, or return None if the file does not exist"""
    if os.path.exists(TRANSACTIONS_CHECK_FILE):
        with open(TRANSACTIONS_CHECK_FILE, "r") as f:
            data = json.load(f)
            return data
    return None

def get_transaction_date(transaction):
    """Normalize transaction date as datetime for mixed input types."""
    value = transaction.get("date")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported transaction date type: {type(value)}")

def save_transactions_history(transactions):
    """Save transactions to a file"""

    path = check_for_check_folder()

    date_formatted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    user_file_path = os.path.join(path, f"{date_formatted}.json")
    with open(user_file_path, "w") as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)

def check_for_check_folder():
    """Check if the check folder exists for the current day, create it if it doesn't"""

    folder = get_today_check_folder()
    if not os.path.exists(folder):
        os.makedirs(folder)

    return folder

def get_today_check_folder():
    """Get the check folder for the current day"""

    today = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(DATA_CHECK_FOLDER, today)
    return folder

def get_daily_summary(balance: float):
    
    yesterday = datetime.now() - timedelta(days=1)
    
    # Get the transactions history for yesterday
    folder = os.path.join(DATA_CHECK_FOLDER, yesterday.strftime("%Y-%m-%d"))
    transactions_history = []
    filecount = 0
    if os.path.exists(folder):
        for file in os.listdir(folder):
            filecount += 1
            if file.endswith(".json"):
                with open(os.path.join(folder, file), "r") as f:
                    data = json.load(f)
                    if data is not None:
                        transactions_history.extend(data)
    
    #Get the number of processed and unprocessed transactions
    succesed_count = len([t for t in transactions_history if t.get("status") == "processed"])
    unprocessed_count = len([t for t in transactions_history if t.get("status") == "unprocessed"])

    # Send the notification with the transactions summary and the current balance
    msg = f"Daily summary for {yesterday.strftime('%Y-%m-%d')}:\n Checks Performed: {filecount}\n Transactions: {len(transactions_history)}\n Processed transactions: {succesed_count}\n Unprocessed transactions: {unprocessed_count}\n Current balance: {balance}"
    
    return msg

def get_weekly_summary(balance: float):
    # Get the transactions history for the last 7 days
    transactions_history = []
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        folder = os.path.join(DATA_CHECK_FOLDER, datetime.strftime(date, "%Y-%m-%d"))
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(".json"):
                    with open(os.path.join(folder, file), "r") as f:
                        data = json.load(f)
                        if data is not None:
                            transactions_history.extend(data)
    
    #Get the number of processed and unprocessed transactions
    succesed_count = len([t for t in transactions_history if t.get("status") == "processed"])
    unprocessed_count = len([t for t in transactions_history if t.get("status") == "unprocessed"])

    # Send the notification with the transactions summary and the current balance
    msg = f"Weekly summary for {datetime.strftime(datetime.now(), '%Y-%m-%d')}:\n Transactions: {len(transactions_history)}\n Processed transactions: {succesed_count}\n Unprocessed transactions: {unprocessed_count}\n Current balance: {balance}"
    
    return msg
    