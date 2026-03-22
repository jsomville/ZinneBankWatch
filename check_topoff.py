
from datetime import datetime, timedelta
import json
import os
import traceback

from getBankInfo import call_account_transactions, call_bank_account_details, call_get_access_token, get_account_id, get_bank_account_summary
from transaction_filter import filter_transactions
from setPayment import process_payment
from logger import log_this, config_logging

debug_this = False

last_day_to_check= int(os.getenv("LAST_DAYS_TO_CHECK", 1))
FILTER_DATE = datetime.now() - timedelta(days=last_day_to_check)

def save_unprocessed_transactions(unprocessed_transactions):

    path = "unprocessed_transactions"
    if not os.path.exists(path):
        os.makedirs(path)

    date_formatted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    user_file_path = os.path.join(path, f"{date_formatted}_unprocessed_transactions.json")
    with open(user_file_path, "w") as f:
        json.dump(unprocessed_transactions, f, indent=2, ensure_ascii=False)

def main():
    """Main function"""
    try:
        config_logging()
        
        log_this("info", "Bank watch started")
        
        #Get the access token for the bank API
        access_token = call_get_access_token()
        if (access_token):
        
            #get the bank information
            raw_account_list = call_bank_account_details(access_token)
            account_list = get_bank_account_summary(raw_account_list)
        
            #from the IBAN, get the bank accountid
            iban_ref = os.getenv("BANK_ACCOUNT_IBAN")
            account_id = get_account_id(account_list, iban_ref)
            
            #Check for Bank Account ID
            if (account_id is None):
                log_this("error", f"Account with IBAN {iban_ref} not found")
                raise ValueError(f"Account with IBAN {iban_ref} not found")
        
            #get the transactions for the account
            raw_transactions_list = call_account_transactions(access_token, account_id)
            
            #process the transactions
            transactions_list = filter_transactions(raw_transactions_list, FILTER_DATE)
            if len(transactions_list) > 0:
                
                log_this("info", f"There are {len(transactions_list)} transactions to process")
                
                unprocessed_transactions = []
                
                for transaction in transactions_list:
                    if debug_this:
                        print(f"Processing transaction {json.dumps(transaction, indent=2)}")
                    
                    try:
                        process_payment(
                            production_flag = True,
                            unique_number = transaction['id'],
                            amount = transaction['amount'],
                            account_number = transaction['description'],
                            transaction_dateTime = datetime.fromisoformat(transaction['date'])
                        )
                        
                        last_processed_transaction_id = transaction['id']
                    except Exception as error:
                        unprocessed_transactions.append(transaction)
                        
                        message = json.dumps({
                            "error": str(error),
                            "traceback": traceback.format_exc().splitlines()
                        }, indent=2)
                        log_this("error", f"Error processing transaction {transaction['id']}: {message}")
                
                if len(unprocessed_transactions) > 0:
                    #Report Transactions failed
                    log_this("error", f"{len(unprocessed_transactions)} transactions failed to process")
                    
                    save_unprocessed_transactions(unprocessed_transactions)
                else:
                    log_this("info", "All transactions processed successfully")
            else:
                log_this("info", "No new transactions to process")
        
        log_this("info", "Bank watch completed")

    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error in bank watch: {message}")

if __name__ == "__main__":
    main()