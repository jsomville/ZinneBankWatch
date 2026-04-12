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

last_day_to_check = int(os.getenv("LAST_DAYS_TO_CHECK", 1))
FILTER_DATE = datetime.now() - timedelta(days=last_day_to_check)
print(f"Filtering transactions from {FILTER_DATE.isoformat()}")

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

LAST_CHECK_FILE = os.path.join(DATA_FOLDER, "last_check.json")


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


def manage_transactions(access_token, account):
    """Get the transactions for the account, filter them by date and process them"""

    # get the transactions for the account
    raw_transactions_list = call_account_transactions(access_token, account.get("id"))

    # Filter transaction by date
    transactions_list = filter_transactions(raw_transactions_list, FILTER_DATE)

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

        # Save the transactions to a file
        save_transactions(transactions_list)

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

        # Send notification - No new transactions to process
        send_notification(msg)


def save_transactions(transactions):
    """Save transactions to a file"""

    path = "transactions_history"
    if not os.path.exists(path):
        os.makedirs(path)

    date_formatted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    user_file_path = os.path.join(path, f"{date_formatted}.json")
    with open(user_file_path, "w") as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)


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
        if identifyer  == "JSB-TST":
            #To prevent flodding the group with test messages
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


def main():
    """Main function"""
    try:
        config_logging()

        log_this("info", "Bank watch started")

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

            # Check for the last synchronisation
            current_balance = account.get("currentBalance")
            last_check = load_last_check()
            if last_check:
                if last_check.get("currentBalance") != current_balance:
                    # Check if the balance has changed since the last check
                    manage_transactions(access_token, account)

                else:
                    msg = "Account balance has not changed"
                    log_this("info", msg)

                    # Send notification - Nothing to do
                    send_notification(msg)

            else:
                log_this("info", "No previous check found, this is the first check")

                manage_transactions(access_token, account)

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
