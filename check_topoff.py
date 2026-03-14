
import os

from getBankInfo import get_access_token, get_account_id, get_account_transactions, get_bank_account_details, process_transactions

def main():
    """Main function"""
    try:
        access_token = get_access_token()
        if (access_token):
        
            bank_detail = get_bank_account_details(access_token)
        
            bank_id = os.getenv("BANK_ACCOUNT_IBAN")
            account_id = get_account_id(bank_detail, bank_id)
        
            transactions = get_account_transactions(access_token, account_id)
            
            process_transactions(transactions)
        
        print("Bank watch completed successfully")
    except Exception as error:
        print(f"Error in bank watch: {error}")

if __name__ == "__main__":
    main()