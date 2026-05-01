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
from transaction_helper import (
    get_account_from_description,
    get_trans_euro,
    is_valid_description,
)

from file_helper import (
    get_daily_summary,
    get_weekly_summary,
    load_last_check,
    save_last_check,
    save_transactions,
    load_transactions,
    save_transactions_history,
    check_for_check_folder,
)

debug_this = False

LAST_DAY_TO_CHECK = int(os.getenv("LAST_DAYS_TO_CHECK", 1))
FILTER_DATE = datetime.now() - timedelta(days=LAST_DAY_TO_CHECK)

WEEK_DAY_TO_SEND_SUMMARY = 4  # 0: Monday, 1: Tuesday, 2: Wednesday, 3: Thursday, 4: Friday, 5: Saturday, 6: Sunday

def manage_transactions(access_token, account):
    """Get the transactions for the account, filter them by date and process them"""

    # get the transactions for the account
    data = call_account_transactions(access_token, account.get("id"))
    raw_transactions_list = data.get("data", [])

    # Load previously processed transactions
    processed_transactions = load_transactions()

    # Filter transaction by date
    transactions_list = filter_transactions(
        raw_transactions_list, processed_transactions, FILTER_DATE
    )

    production_flag = False

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

            is_valid = is_valid_description(transaction["description"])
            if not is_valid:
                # We cannot extract a valid account number from the description, we consider this transaction as unprocessed and we add a reason to it
                transaction["status"] = "unprocessed"
                transaction["reason"] = (
                    "Invalid description, cannot extract account number"
                )
                failed_count += 1
                failed_msg += (
                    f" - {transaction['reason']} - {transaction['description']}\n"
                )
            else:

                # Normalize the description to extract the account number
                account_number = get_account_from_description(
                    transaction["description"]
                )

                # Normalize the description to extract the euro amount
                transaction["description"] = account_number

                # Get the unique key to validate
                transeuro = get_trans_euro(transaction)

                try:
                    process_payment(
                        unique_number=transaction["id"],
                        amount=transaction["amount"],
                        account_number=account_number,
                        transeuro=transeuro,
                    )
                    transaction["status"] = "processed"
                    succeded_count += 1
                    succeded_msg += f" - {transeuro}\n"

                except Exception as error:
                    transaction["status"] = "unprocessed"
                    transaction["reason"] = get_unprocessed_reason(str(error))
                    failed_count += 1
                    failed_msg += f" - {transeuro} : {transaction['reason']}\n"

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
        #send_notification(msg)


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
    if expirationDate < datetime.now(timezone.utc) + timedelta(days=15):
        msg = f"Authorization is expiring soon on {expirationDate.isoformat()}"
        log_this("warning", msg)

        # Send notification
        send_notification(msg)


def make_daily_summary(balance: float):
    """Make a daily summary of the transactions and send a notification"""
    log_this("info", "Making daily summary")
    
    msg = get_daily_summary(balance)
    send_notification(msg)


def make_weekly_summary(balance: float):
    """Make a weekly summary of the transactions and send a notification"""
    log_this("info", "Making weekly summary")
    msg = get_weekly_summary(balance)
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

            # Make summary report
            if last_check is not None:
                last_check_date = datetime.fromisoformat(last_check.get("last_check"))
                if last_check_date.date() != datetime.now().date():
                    # This is a new day
                    new_balance = account.get("currentBalance") if account else "N/A"

                    make_daily_summary(new_balance)

                    # Check if today is a sunday, if yes make a weekly summary, if not make a daily summary
                    if datetime.now().weekday() == WEEK_DAY_TO_SEND_SUMMARY: 
                        make_weekly_summary(new_balance)
                        

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
