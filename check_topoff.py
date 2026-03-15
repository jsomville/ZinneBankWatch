
from datetime import datetime
import json
import os
import traceback

from getBankInfo import get_access_token, get_account_id, get_account_transactions, get_bank_account_details, process_transactions
from setPayment import process_payment
from logger import log_this, config_logging

debug_this = False

last_processed_transaction_id_file = "last_processed_transaction_id.txt"

def filter_transactions(transactions, last_processed_transaction_id):
    if last_processed_transaction_id is None:
        return transactions
    else:
        transaction_to_process = []
        for transaction in transactions:
            #Is this by order DESC ?
            if transaction['id'] == last_processed_transaction_id:
                break
            else:
                transaction_to_process.append(transaction)
    
    if debug_this:
        print(f"Filtered Transactions from {len(transactions)} to {len(transaction_to_process)}")         
    
    return transaction_to_process

def save_unprocessed_transactions(unprocessed_transactions):

    path = "unprocessed_transactions"
    if not os.path.exists(path):
        os.makedirs(path)

    date_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_file_path = os.path.join(path, f"{date_formatted}_unprocessed_transactions.json")
    with open(user_file_path, "w") as f:
        json.dump(unprocessed_transactions, f, indent=2, ensure_ascii=False)

def main():
    """Main function"""
    try:
        config_logging()
        
        log_this("info", "Bank watch started")
        
        access_token = get_access_token()
        if (access_token):
        
            #get the bank information
            bank_detail = get_bank_account_details(access_token)
        
            #from the IBAN, get the bank accountid
            bank_id = os.getenv("BANK_ACCOUNT_IBAN")
            account_id = get_account_id(bank_detail, bank_id)
        
            #get the transactions for the account
            transactions = get_account_transactions(access_token, account_id)
        
            #get last processed Transaction ID from file if exists
            if last_processed_transaction_id_file in os.listdir():
                with open(last_processed_transaction_id_file, "r") as f:
                    last_processed_transaction_id = f.read()
            else:
                last_processed_transaction_id = None
            log_this("info", f"Last processed transaction id: {last_processed_transaction_id}")
            
            #process the transactionns
            transactions = process_transactions(transactions)
            transactions_to_process = filter_transactions(transactions, last_processed_transaction_id)
            if len(transactions_to_process) > 0:
                
                log_this("info", f"There are {len(transactions_to_process)} transactions to process")
                
                unprocessed_transactions = []
                
                for transaction in transactions_to_process:
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
                    
                #Save last processed transaction id to file
                if last_processed_transaction_id:
                    with open(last_processed_transaction_id_file, "w") as f:
                        f.write(last_processed_transaction_id)
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