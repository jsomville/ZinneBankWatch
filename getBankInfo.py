import os
import json
import base64
import traceback
import requests
from dotenv import load_dotenv, parser
from logger import log_this, config_logging

# Load environment variables from .env file
load_dotenv()

pattern = r'^\d{3}-\d{4}-\d{5}$'
pattern_fulldigit = r'^\d{12}$'

debug_this = False

def call_get_access_token():
    """Authenticate with the MyPonto OAuth2 API"""
    log_this("info", "Logging in...")
    try:
        client_id = os.getenv("MY_PONTO_ID")
        client_secret = os.getenv("MY_PONTO_SECRET")
        my_ponto_url = os.getenv("MY_PONTO_URL")
        
        if not client_id or not client_secret:
            raise ValueError("Missing MY_PONTO_ID or MY_PONTO_SECRET in environment variables")
        
        # Create Basic Auth header
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        response = requests.post(
            f"{my_ponto_url}/oauth2/token",
            headers=headers,
            data={"grant_type": "client_credentials"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.status_code} {response.text}")
        
        data = response.json()
        
        if debug_this:
            print(f"Access Token: {data.get('access_token')}")
            
        return data
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Login error: {message}")
        raise
    

def call_bank_account_details(access_token):
    """Get bank account details"""
    log_this("info", "Getting bank account details...")
    try:
        my_ponto_url = os.getenv("MY_PONTO_URL")
        
        if not access_token:
            raise ValueError("Missing access token")
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.get('access_token')}"
        }
        
        response = requests.get(
            f"{my_ponto_url}/accounts",
            headers=headers,
            data={"grant_type": "client_credentials"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.status_code} {response.text}")
        
        data = response.json()
        
        if debug_this:
            print(json.dumps(data, indent=2))
            
        return data
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error getting bank account details: {message}")
        raise
    
def get_bank_account_summary(bank_accounts_detail):
    """Get a summary of the bank account details"""
    log_this("info", "Getting bank account summary...")
    try:
        summary = []
        for account in bank_accounts_detail.get("data", []):
            attributes = account.get("attributes", {})
            synchronisation = account.get("meta", {})
            latest_synchronisation = synchronisation.get("latestSynchronization", {})
            sync_attributes = latest_synchronisation.get("attributes", {})
            
            summary.append({
                "id": account.get("id"),
                "description": attributes.get("description"),
                "iban": attributes.get("reference"),
                "subtype": attributes.get("subtype"),
                "currency": attributes.get("currency"),
                "availableBalance": attributes.get("availableBalance"),
                "currentBalance": attributes.get("currentBalance"),
                "authorizationExpirationExpectedAt": attributes.get("authorizationExpirationExpectedAt"),
                "currentBalanceReferenceDate": attributes.get("currentBalanceReferenceDate"),
                "currentBalanceVariationObservedAt": attributes.get("currentBalanceVariationObservedAt"),
                "synchronizedAt": synchronisation.get("synchronizedAt"),
                "resourceId": sync_attributes.get("resourceId"),
                "synchronisationId": latest_synchronisation.get("id"),
            })
            
        log_this("info", f"Retrieved {len(summary)} bank accounts")
        #log_this("info", f"Retrieved = {json.dumps(summary, indent=2)}")
        return summary
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error getting bank account summary: {message}")
        raise   

def call_account_transactions(access_token, account_id):
    """Get transactions for a specific bank account ordered by transaction date descending, max 10 transactions"""
    log_this("info", f"Getting transactions for account {account_id}...")
    try:
        if not access_token:
            raise ValueError("Missing access token")
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.get('access_token')}"
        }
        
        response = requests.get(
            f"https://api.myponto.com/accounts/{account_id}/transactions",
            headers=headers,
            params={
                "page[limit]": 50
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get transactions: {response.status_code} {response.text}")
        
        data = response.json()
        
        raw_transaction_list = data.get("data", [])
        log_this("info", f"Retrieved {len(raw_transaction_list)} transactions")
        #log_this("info", f"Retrieved transactions = {json.dumps(raw_transaction_list, indent=2)}")
        
        if debug_this:
            print(json.dumps(data, indent=2))
            
        return data
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error getting transactions: {message}")
        raise

def get_account_id(account_list, iban):
    """Get account ID from bank details using IBAN"""
    log_this("info", f"Finding account ID for IBAN {iban}...")
    try:
        for account in account_list:
            if account.get("iban") == iban:
                if debug_this:
                    print(f"Found account ID: {account.get('id')}")
                return account.get("id")
            
        raise ValueError(f"No account found with IBAN {iban}")
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error finding account ID:: {message}")
        raise

def get_account_detail_by_IBAN(account_list, iban):
    """Get account ID from bank details using IBAN"""
    log_this("info", f"Finding account ID for IBAN {iban}...")
    try:
        for account in account_list:
            if account.get("iban") == iban:
                if debug_this:
                    print(f"Found account ID: {account.get('id')}")
                return account
            
        raise ValueError(f"No account found with IBAN {iban}")
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error finding account ID:: {message}")
        raise


def main():
    """Main function"""
    try:
        config_logging()
        
        access_token = call_get_access_token()
        if (access_token):
    
            #get the bank information
            raw_account_list = call_bank_account_details(access_token)
            account_list = get_bank_account_summary(raw_account_list)
        
            #from the IBAN, get the bank accountid
            iban_ref = os.getenv("BANK_ACCOUNT_IBAN")
            account_id = get_account_id(account_list, iban_ref)
            
            if (account_id is None):
                log_this("error", f"Account with IBAN {iban_ref} not found")
                raise ValueError(f"Account with IBAN {iban_ref} not found")
            
            #get the transactions for the account
            raw_transactions_payload = call_account_transactions(access_token, account_id)    
        
    except Exception as error:
        print(f"getBankInfo - Error: {error}")


if __name__ == "__main__":
    main()
