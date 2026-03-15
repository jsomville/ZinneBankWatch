from datetime import datetime

import os
import json
import re
import base64
import traceback
import requests
from dotenv import load_dotenv
from logger import log_this, config_logging

# Load environment variables from .env file
load_dotenv()

pattern = r'^\d{3}-\d{4}-\d{5}$'
pattern_fulldigit = r'^\d{12}$'

debug_this = False
debug_transactions = True

def get_access_token():
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
    

def get_bank_account_details(access_token):
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
    
def get_account_transactions(access_token, account_id):
    """Get transactions for a specific bank account"""
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
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get transactions: {response.status_code} {response.text}")
        
        data = response.json()
        
        if debug_transactions:
            print(json.dumps(data, indent=2))
            
        return data
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error getting transactions: {message}")
        raise

def get_account_id(bank_details, iban):
    """Get account ID from bank details using IBAN"""
    log_this("info", f"Finding account ID for IBAN {iban}...")
    try:
        for account in bank_details.get("data", []):
            if account.get("attributes", {}).get("reference") == iban:
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

def process_transactions(transactions):
    """Process transactions and extract relevant information"""
    try:
        processed = []
        counter = 0
        for transaction in transactions.get("data", []):
            
            processed_transaction = process_transaction(transaction)
            if processed_transaction["status"] == "success":
                processed.append(processed_transaction)
                
            if debug_transactions:
                print(f"Processed transaction: {json.dumps(processed_transaction, indent=2)}")
                
            counter += 1
        
        return processed
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error processing transactions: {message}")
        raise

def process_transaction(transaction):
    """Process a single transaction and extract relevant information"""
    try:
        attributes = transaction.get("attributes", {})
        
        transaction_result = {
            "status": "",
        }
        
        #Check Id
        id = transaction.get("id")
        if id is None:
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Missing transaction ID"
            return transaction_result
        transaction_result["id"] = id
        
        #Check date
        date_str = attributes.get("executionDate")
        if date_str is None:
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Missing date"
            return transaction_result
        try:
            date_json = json.dumps(date_str)
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            log_this("error", f"Invalid date format: {date_str}")
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Invalid date format"
            return transaction_result
        transaction_result["date"] = date.isoformat()
        
        #Check Amount
        amount = attributes.get("amount")
        if amount is None or amount <= 0:
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Invalid amount"
            return transaction_result
        transaction_result["amount"] = amount
        
        #Check Currency
        currency = attributes.get("currency")
        if currency != "EUR":
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Invalid currency"
            return transaction_result
        transaction_result["currency"] = currency
        

        
        #Check description
        description = ""
        description_temp = attributes.get("remittanceInformation", "")
        if (description_temp is None):
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Missing remittance information"
            return transaction_result
        #Remove non digit characters
        cleaned_description_temp = re.sub(r'\D', '', description_temp)
        if len(cleaned_description_temp) != 12:
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Invalid remittance information"
            return transaction_result
        description = f"{cleaned_description_temp[:3]}-{cleaned_description_temp[3:7]}-{cleaned_description_temp[7:]}"
        transaction_result["description"] = description
        
        #Set transaction succeded
        transaction_result["status"] = "success"
        transaction_result["field.reftranseuro"]= f"{date.date()}/{description}/{amount:.2f}"
        transaction_result["field.sourceEuro"]= "Virement Bancaire"
        
        return transaction_result
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error processing transaction: {message}")
        raise
    
def test_process_transaction(transaction_data, testNumber, expected_result):
    """Test the process_transaction function with given data and expected result"""
    try:
        result = process_transaction(transaction_data)
        if result["status"] == "success" and expected_result == True:
            print(f"Test {testNumber} passed")
            return True
        
        if result["status"] == "failed" and expected_result == False:
            print(f"Test {testNumber} passed")
            return True
        
        if result["status"] == "failed" and expected_result == True:
            print(f"Test {testNumber} failed: Expected success, got {result}")
            return False
        
        if result["status"] == "success" and expected_result == False:
            print(f"Test {testNumber} failed: Expected failure, got {result}")
            return False

    except Exception as error:
        print(f"Error in test_process_transaction: {error}")

def execute_test_cases():
    print("getBankInfo - Main - Testing process")
    test_ok = True
    test_count = 0
    
    #Test - OK
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123-4567-89012",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, True)
    if not r:
        test_ok = False

    
    # Test - OK with full digit remittance information
    test_count+=1
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123456789012",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, True)
    if not r:
        test_ok = False
        
    # Test - OK with full digit with slash
    test_count+=1
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123/4567/89012",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, True)
    if not r:
        test_ok = False
        
    # Test - OK with full digit with underscore
    test_count+=1
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123_4567_89012",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, True)
    if not r:
        test_ok = False
    
    # Test - OK with full digit with space
    test_count+=1
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123 4567 89012",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, True)
    if not r:
        test_ok = False
    
    #Test - Not ok missing remitance
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False
    
    #Test - Not ok remotance format
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "12-123-154556",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False
        
    #Test - Not ok
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "A12-123-154556",
            "executionDate": "2024-06-01"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False
    
    #Test - Not ok negative amount
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": -100.0,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": "2024-06-01T23:00:00.000Z"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False

    #Test - Not ok date only
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 0,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": "2024-06-01"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False
    
    #Test - Not ok date + time no TZ
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 0,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": "2024-06-01T23:00:00"
        }
    }
    r = test_process_transaction(test_data, test_count, False)
    if not r:
        test_ok = False

    if test_ok:
        print("getBankInfo - Tests completed successfully")
    else:
        print("getBankInfo - Tests completed with errors")

def main():
    """Main function"""
    try:
        config_logging()
        
        execute_test_cases()
        
        
    except Exception as error:
        print(f"getBankInfo - Error: {error}")

if __name__ == "__main__":
    main()
