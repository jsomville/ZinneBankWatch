from dotenv import load_dotenv, parser
from logger import log_this, config_logging
import json
import traceback
import re
from datetime import datetime

load_dotenv()

debug_this = False
debug_transactions = False

def get_filtered_transactions(transactions):
    """Process transactions and extract relevant information"""
    try:
        processed = []
        counter = 0
        for transaction in transactions.get("data", []):
            
            processed_transaction = filter_transaction(transaction)
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

def filter_transaction(transaction):
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
    
def test_filter_transaction(transaction_data, testNumber, expected_result):
    """Test the filter_transaction function with given data and expected result"""
    try:
        result = filter_transaction(transaction_data)
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
    r = test_filter_transaction(test_data, test_count, True)
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
    r = test_filter_transaction(test_data, test_count, True)
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
    r = test_filter_transaction(test_data, test_count, True)
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
    r = test_filter_transaction(test_data, test_count, True)
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
    r = test_filter_transaction(test_data, test_count, True)
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
    r = test_filter_transaction(test_data, test_count, False)
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
    r = test_filter_transaction(test_data, test_count, False)
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
    r = test_filter_transaction(test_data, test_count, False)
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
    r = test_filter_transaction(test_data, test_count, False)
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
    r = test_filter_transaction(test_data, test_count, False)
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
    r = test_filter_transaction(test_data, test_count, False)
    if not r:
        test_ok = False

    if test_ok:
        print("transaction_filter - Tests completed successfully")
    else:
        print("transaction_filter - Tests completed with errors")

def main():
    """Main function"""
    try:
        config_logging()
        
        execute_test_cases()
        
    except Exception as error:
        print(f"transaction_filter - Error: {error}")

if __name__ == "__main__":
    main()