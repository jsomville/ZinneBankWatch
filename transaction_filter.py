from dotenv import load_dotenv, parser
from logger import log_this, config_logging
import json
import traceback
import re
from datetime import date, datetime, timedelta, timezone

load_dotenv()

debug_this = False

def filter_transactions(transactions, processed_transactions, date_from):
    """Process transactions and extract relevant information"""
    try:
        processed = []
        counter = 0
        for transaction in transactions.get("data", []):
            
            #Filter out already processed transactions
            if processed_transactions is not None:
                if any(pt.get("id") == transaction.get("id") for pt in processed_transactions):
                    if debug_this:
                        print(f"Skipping already processed transaction: {transaction.get('id')}")
                    continue
            
            #Filter transaction based on date and filter
            processed_transaction = filter_transaction(transaction, date_from)
            if processed_transaction["status"] == "success":
                processed.append(processed_transaction)
                
            if debug_this:
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

def filter_transaction(transaction, date_from):
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
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            transaction_result["date"] = date.isoformat()
        except ValueError:
            log_this("error", f"Invalid date format: {date_str}")
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Invalid date format"
            return transaction_result
        
        transaction_date = datetime.fromisoformat(transaction_result["date"])
        if transaction_date and transaction_date.date() < date_from.date():
            transaction_result["status"] = "failed"
            transaction_result["reason"] = "Transaction date is before the specified date_from"
            return transaction_result
        
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
    
def test_filter_transaction(transaction_data, testNumber, test_name, filter_date, expected_result):
    """Test the filter_transaction function with given data and expected result"""
    try:
        result = filter_transaction(transaction_data, filter_date)
        if result["status"] == "success" and expected_result == True:
            print(f"Test {testNumber} passed - {test_name} ")
            return True
        
        if result["status"] == "failed" and expected_result == False:
            print(f"Test {testNumber} passed - {test_name} ")
            return True
        
        if result["status"] == "failed" and expected_result == True:
            print(f"Test {testNumber} - {test_name} : failed: Expected success, got {result}")
            return False
        
        if result["status"] == "success" and expected_result == False:
            print(f"Test {testNumber} - {test_name} : failed: Expected failure, got {result}")
            return False

    except Exception as error:
        print(f"Error in test_process_transaction: {error}")

def execute_test_cases():
    print("getBankInfo - Main - Testing process")
    test_ok = True
    test_count = 0
    
    filterdate = datetime.now() - timedelta(days=1)
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    #Test - OK
    test_name = "OK with valid data"
    test_count+=1
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123-4567-89012",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name,filterdate, True)
    if not r:
        test_ok = False

    
    # Test - OK with full digit remittance information
    test_name = "OK with full digit remittance information"
    test_count+=1
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123456789012",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
        
    # Test - OK with full digit with slash
    test_count+=1
    test_name = "OK with full digit with slash"
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123/4567/89012",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
        
    # Test - OK with full digit with underscore
    test_count+=1
    test_name = "OK with full digit with underscore"
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123_4567_89012",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
    
    # Test - OK with full digit with space
    test_count+=1
    test_name = "OK with full digit with space"
    test_data = { 
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "123 4567 89012",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
    
    #Test - Not ok missing remitance
    test_count+=1
    test_name = "Not ok missing remitance"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, False)
    if not r:
        test_ok = False
    
    #Test - Not ok remittance format
    test_count+=1
    test_name = "Not ok remittance format"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "12-123-154556",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, False)
    if not r:
        test_ok = False
        
    #Test - Not ok remittance format with letters
    test_count+=1
    test_name = "Not ok remittance format with letters"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 100.0,
            "currency": "EUR",
            "remittanceInformation": "A12-123-154556",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, False)
    if not r:
        test_ok = False
    
    #Test - Not ok negative amount
    test_count+=1
    test_name = "Not ok negative amount"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": -100.0,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": yesterday.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, False)
    if not r:
        test_ok = False

    #Test - date only
    test_count+=1
    test_name = "Date only"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 10,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": yesterday.date().isoformat()
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
        
    #Test - Not ok date + time only
    test_count+=1
    test_name = "Date + time"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 10,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": yesterday.strftime("%Y-%m-%dT%H:%M:%S")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
    
     #Test - Not ok date + time only
    test_count+=1
    test_name = "Date time with space"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 10,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": yesterday.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
    
    #Test - Not ok date + time no TZ
    test_count+=1
    test_name = "Datetime no TZ"
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 10,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": yesterday.isoformat(timespec="milliseconds")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, True)
    if not r:
        test_ok = False
    
    #Test - Not ok date + time no TZ
    test_count+=1
    test_name = "Too late"
    too_late = datetime.now(timezone.utc) - timedelta(days=2)
    test_data = {
        "id": "12345",
        "attributes": {
            "amount": 10,
            "currency": "EUR",
            "remittanceInformation": "112-123-154556",
            "executionDate": too_late.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        }
    }
    r = test_filter_transaction(test_data, test_count, test_name, filterdate, False)
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