from datetime import datetime, timedelta, timezone
import json
import os
import traceback

from getBankInfo import (
    call_account_transactions,
    call_bank_account_details,
    call_get_access_token,
    get_account_detail_by_IBAN,
    get_bank_account_summary,
)
from transaction_filter import filter_transactions
from setPayment import get_unprocessed_reason, process_payment
from logger import log_this, config_logging
from send_signal_notification import send_signal_message

debug_this = False

LAST_DAY_TO_CHECK = int(os.getenv("LAST_DAYS_TO_CHECK", 1))
FILTER_DATE = datetime.now() - timedelta(days=LAST_DAY_TO_CHECK)
print(f"Filtering transactions from {FILTER_DATE.isoformat()}")

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

DATA_CHECK_FOLDER = os.path.join(DATA_FOLDER, "checks")
if not os.path.exists(DATA_CHECK_FOLDER):
    os.makedirs(DATA_CHECK_FOLDER)

LAST_CHECK_FILE = os.path.join(DATA_FOLDER, "last_check.json")

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
            if datetime.fromisoformat(t["date"]).date()
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


def save_transactions_history(transactions):
    """Save transactions to a file"""

    path = check_for_check_folder()

    date_formatted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    user_file_path = os.path.join(path, f"{date_formatted}.json")
    with open(user_file_path, "w") as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)


def manage_transactions(access_token, account):
    """Get the transactions for the account, filter them by date and process them"""

    # get the transactions for the account
    raw_transactions_list = call_account_transactions(access_token, account.get("id"))

    # Load previously processed transactions
    processed_transactions = load_transactions()

    # Filter transaction by date
    transactions_list = filter_transactions(
        raw_transactions_list, processed_transactions, FILTER_DATE
    )

    # Handle transactions
    if len(transactions_list) > 0:

        log_this("info", f"There are {len(transactions_list)} transactions to process")

        succeded_count = 0
        succeded_msg = ""
        failed_count = 0
        failed_msg = ""
        for transaction in transactions_list:
            if debug_this:
                print(f"Processing transaction {json.dumps(transaction, indent=2)}")

            try:
                process_payment(
                    production_flag=True,
                    unique_number=transaction["id"],
                    amount=transaction["amount"],
                    account_number=transaction["description"],
                    transaction_dateTime=datetime.fromisoformat(transaction["date"]),
                )
                transaction["status"] = "processed"
                succeded_count += 1
                succeded_msg += (
                    f" - {transaction['description']}/{transaction['amount']}\n"
                )

            except Exception as error:
                transaction["status"] = "unprocessed"
                transaction["reason"] = get_unprocessed_reason(str(error))
                failed_count += 1
                failed_msg += f" - {transaction['description']}/{transaction['amount']}: {transaction['reason']}\n"

            # Add to the list of processed transactions
            if processed_transactions is None:
                processed_transactions = []
            processed_transactions.append(transaction)

        # Save the transactions to a file
        save_transactions_history(transactions_list)
        save_transactions(processed_transactions)

        msg = ""
        if failed_count == 0:
            log_msg = "All transactions processed successfully"
            log_this("info", log_msg)

            msg = (
                log_msg
                + "\n"
                + succeded_msg
                + "\nCurrent balance : "
                + str(account.get("currentBalance"))
            )

        else:
            log_msg = f"{succeded_count} transactions processed successfully, {failed_count} transactions failed to process"
            log_this("warning", log_msg)

            if succeded_count == 0:
                msg = (
                    "Failed transactions:\n"
                    + failed_msg
                    + "\nCurrent balance : "
                    + str(account.get("currentBalance"))
                )
            else:
                msg = (
                    "Succeded transactions:\n"
                    + succeded_msg
                    + "\nFailed transactions:\n"
                    + failed_msg
                    + "\nCurrent balance : "
                    + str(account.get("currentBalance"))
                )

        send_notification(msg)

    else:
        msg = "No new transactions to process"
        log_this("info", msg)

        # Save the transaction history, is null
        save_transactions_history(None)

        # Save the processed transactions
        save_transactions(processed_transactions)

        # Send notification - No new transactions to process
        send_notification(msg)


def send_check_notification(transactions, balance):
    """Send a notification to the signal group with the number of transactions processed and the current balance"""
    try:
        if transactions is None:
            message = f"No transactions processed, current balance : {balance}"
        else:
            # Get the transactions details
            unprocessed_count = len(transactions.get("unprocessed_transactions", []))
            processed_count = len(transactions.get("processed_transactions", []))

            message = f"Processed transactions: {processed_count}, Unprocessed transactions: {unprocessed_count}, current balance : {balance}"

        send_notification(message)

    except Exception as error:
        message = json.dumps(
            {"error": str(error), "traceback": traceback.format_exc().splitlines()},
            indent=2,
        )
        log_this("error", f"Error sending check notification: {message}")


def send_notification(message):
    """Send a notification to the signal group"""
    try:
        environment = os.getenv("ENVIRONEMENT")
        identifyer = os.getenv("IDENTIFIER")
        msg_prefix = f"[{identifyer}] in {environment} : "

        # Get the destination group
        destination_group = os.getenv("SIGNAL_DESTINATION_GROUP")
        recipients = []
        if identifyer == "JSB-TST":
            # To prevent flodding the group with test messages
            destination_number = os.getenv("SIGNAL_SOURCE_NUMBER")
            recipients.append(destination_number)
        else:
            recipients.append(destination_group)

        send_signal_message(recipients, msg_prefix + message)

    except Exception as error:
        message = json.dumps(
            {"error": str(error), "traceback": traceback.format_exc().splitlines()},
            indent=2,
        )
        log_this("error", f"Error sending notification: {message}")


def check_authorisation_expiration(account_info):
    """Check if the authorization is expiring soon and send a notification if it is"""

    expiration = account_info.get("authorizationExpirationExpectedAt")
    expirationDate = datetime.fromisoformat(expiration)
    if expirationDate < datetime.now(timezone.utc) + timedelta(days=10):
        msg = f"Authorization is expiring soon on {expirationDate.isoformat()}"
        log_this("warning", msg)

        # Send notification
        send_notification(msg)


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


def make_daily_summary(datetime, last_check):
    """Make a daily summary of the transactions and send a notification"""

    # Get the transactions history for today
    folder = os.path.join(DATA_CHECK_FOLDER, datetime.strftime("%Y-%m-%d"))
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

    # Get the current balance from the last check
    balance = last_check.get("currentBalance") if last_check else "N/A"
    
    #Get the number of processed and unprocessed transactions
    succesed_count = len([t for t in transactions_history if t.get("status") == "processed"])
    unprocessed_count = len([t for t in transactions_history if t.get("status") == "unprocessed"])

    # Send the notification with the transactions summary and the current balance
    msg = f"Daily summary for {datetime.strftime('%Y-%m-%d')}:\n Checks Performed: {filecount}\n Transactions: {len(transactions_history)}\n Processed transactions: {succesed_count}\n Unprocessed transactions: {unprocessed_count}\n Current balance: {balance}"
    send_notification(msg)

def make_weekly_summary(datetime, last_check):
    """Make a weekly summary of the transactions and send a notification"""
    # This function can be implemented in the future to provide a weekly summary of the transactions and the account balance.
    first_day_of_week = datetime - timedelta(days=7)
    filecount = 0
    transactions_history = []
    for i in range(7):
        day = first_day_of_week + timedelta(days=i)
        folder = os.path.join(DATA_CHECK_FOLDER, day.strftime("%Y-%m-%d"))
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(".json"):
                    filecount += 1
                    with open(os.path.join(folder, file), "r") as f:
                        data = json.load(f)
                        if data is not None:
                            transactions_history.extend(data)
    
    #get the current balance from the last check
    balance = last_check.get("currentBalance") if last_check else "N/A"
    
    #Get the number of processed and unprocessed transactions
    succesed_count = len([t for t in transactions_history if t.get("status") == "processed"])
    unprocessed_count = len([t for t in transactions_history if t.get("status") == "unprocessed"])

    # Send the notification with the transactions summary and the current balance
    week_number = datetime.isocalendar()[1]
    msg = f"Weekly summary for week {week_number}\n Checks Performed: {filecount}\n Transactions: {len(transactions_history)}\n Processed transactions: {succesed_count}\n Unprocessed transactions: {unprocessed_count}\n Current balance: {balance}"
    send_notification(msg)                       
    
def main():
    """Main function"""
    try:
        config_logging()

        log_this("info", "Bank watch started")

        check_for_check_folder()
        
        last_check = load_last_check()
    
        # Get the access token for the bank API
        access_token = call_get_access_token()
        if access_token:

            # get the bank information
            raw_account_list = call_bank_account_details(access_token)
            account_list = get_bank_account_summary(raw_account_list)

            # from the IBAN, get the bank accountid
            iban_ref = os.getenv("BANK_ACCOUNT_IBAN")
            account = get_account_detail_by_IBAN(account_list, iban_ref)

            # Check the Authorisation and send a notification if bout to expire
            check_authorisation_expiration(account)

            # Check for Bank Account ID
            if account is None:
                log_this("error", f"Account with IBAN {iban_ref} not found")
                raise ValueError(f"Account with IBAN {iban_ref} not found")

            # Manage Transactions
            manage_transactions(access_token, account)

            #Make summary report
            if last_check is not None:
                last_check_date = datetime.fromisoformat(last_check.get("last_check"))
                if last_check_date.date() != datetime.now().date():
                    #This is a new day
                    
                    #Check if today is a sunday, if yes make a weekly summary, if not make a daily summary
                    if datetime.now().weekday() == 6:  # Sunday
                        make_weekly_summary(datetime.now(), last_check)
                    else:
                        make_daily_summary(last_check_date.date(), last_check)

            # Save the last Check Informations
            save_last_check(account)
        else:
            log_this(
                "error", "Failed to get access token, cannot proceed with bank watch"
            )

            # Send notification - Failed to get access token
            msg = "Failed to get myPunto access token, cannot proceed with bank watch"
            send_notification(msg)

        log_this("info", "Bank watch completed")

    except Exception as error:
        message = json.dumps(
            {"error": str(error), "traceback": traceback.format_exc().splitlines()},
            indent=2,
        )
        log_this("error", f"Error in bank watch: {message}")


if __name__ == "__main__":
    main()
