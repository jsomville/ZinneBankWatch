from datetime import datetime, timedelta
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

LAST_CHECK_FILE = "last_check.json"

def save_unprocessed_transactions(unprocessed_transactions):

    path = "unprocessed_transactions"
    if not os.path.exists(path):
        os.makedirs(path)

    date_formatted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    user_file_path = os.path.join(
        path, f"{date_formatted}_unprocessed_transactions.json"
    )
    with open(user_file_path, "w") as f:
        json.dump(unprocessed_transactions, f, indent=2, ensure_ascii=False)


def save_last_check(account_details):
    data = {
        "availableBalance": account_details.get("availableBalance"),
        "currentBalance": account_details.get("currentBalance"),  
        "account_number": account_details.get("iban"),
        "last_check": datetime.now().isoformat(),
    }

    user_file_path = LAST_CHECK_FILE
    with open(user_file_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_last_check():
    user_file_path = LAST_CHECK_FILE
    if os.path.exists(user_file_path):
        with open(user_file_path, "r") as f:
            data = json.load(f)
            return data
    return None


def manage_transactions(access_token, account):
    # get the transactions for the account
    raw_transactions_list = call_account_transactions(access_token, account.get("id"))
    
    #Filter transaction by date
    transactions_list = filter_transactions(raw_transactions_list, FILTER_DATE)
    print(f"Filtered transactions list : {json.dumps(transactions_list, indent=2)}")
    
    #Handle transactions
    if len(transactions_list) > 0:

        log_this("info", f"There are {len(transactions_list)} transactions to process")

        unprocessed_transactions = []
        processed_transactions = []
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
                processed_transactions.append(transaction)
                
            except Exception as error:
                transaction["status"] = "unprocessed"
                transaction["reason"] = get_unprocessed_reason(str(error))
                
                unprocessed_transactions.append(transaction)

                message = json.dumps(
                    {
                        "error": str(error),
                        "traceback": traceback.format_exc().splitlines(),
                    },
                    indent=2,
                )
                log_this(
                    "error",
                    f"Error processing transaction {transaction['id']}: {message}",
                )

        if len(unprocessed_transactions) > 0:
            # Report Transactions failed
            log_this(
                "error",
                f"{len(unprocessed_transactions)} transactions failed to process",
            )

            save_unprocessed_transactions(unprocessed_transactions)
        else:
            log_this("info", "All transactions processed successfully")
        
        transactions = {    
            "processed_transactions": processed_transactions,
            "unprocessed_transactions": unprocessed_transactions
        }
            
        return transactions
    else:
        log_this("info", "No new transactions to process")

def send_check_notification(transactions, balance):
    try:
        #Get the destination group
        destination_group = os.getenv("SIGNAL_DESTINATION_GROUP")
        recipients = []
        recipients.append(destination_group)
        
        environment = os.getenv("ENVIRONEMENT")
        identifyer = os.getenv("IDENTIFIER")
        
        if transactions is None:
            message = f"[{identifyer}] in {environment} : No transactions processed, current balance : {balance}"
        else:
            #Get the transactions details
            unprocessed_count = len(transactions.get("unprocessed_transactions", []))
            processed_count = len(transactions.get("processed_transactions", []))
            
            message = f"[{identifyer}] in {environment} : Processed transactions: {processed_count}, Unprocessed transactions: {unprocessed_count}, current balance : {balance}"
        
        send_signal_message(recipients, message)
    except Exception as error:
        message = json.dumps(
            {"error": str(error), "traceback": traceback.format_exc().splitlines()},
            indent=2,
        )
        log_this("error", f"Error sending check notification: {message}")

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
            # account_id = get_account_id(account_list, iban_ref)
            account = get_account_detail_by_IBAN(account_list, iban_ref)

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
                    transactions = manage_transactions(access_token, account)
                    
                    send_check_notification(transactions, current_balance)
                
                else:
                    log_this("info", "No balance change since last check, skipping transaction processing")

            else:
                log_this("info", "No previous check found, this is the first check")
                
                transactions = manage_transactions(access_token, account)
                
                send_check_notification(transactions, current_balance)
                
            #Save the last Check Informations
            save_last_check(account)

        log_this("info", "Bank watch completed")

    except Exception as error:
        message = json.dumps(
            {"error": str(error), "traceback": traceback.format_exc().splitlines()},
            indent=2,
        )
        log_this("error", f"Error in bank watch: {message}")


if __name__ == "__main__":
    main()
