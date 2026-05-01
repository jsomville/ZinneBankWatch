

from datetime import datetime, timedelta
import json

from transaction_filter import filter_transaction, filter_transactions
from transaction_helper import get_account_from_description, get_trans_euro, is_valid_description


def test_get_trans_euro():
    transaction = {
        "date": datetime(2024, 6, 1).isoformat(),
        "description": "Test Transaction",
        "amount": 123.45
    }
    expected_transeuro = "2024-06-01/Test Transaction/123.45"
    assert get_trans_euro(transaction) == expected_transeuro
    
    transaction = {
        "date": datetime(2024, 6, 1).isoformat(),
        "description": "",
        "amount": 123.45
    }
    expected_transeuro = "2024-06-01//123.45"
    assert get_trans_euro(transaction) == expected_transeuro
    
    transaction = {
        "date": datetime(2024, 6, 1).isoformat(),
        "description": "",
        "amount": 0
    }
    expected_transeuro = "2024-06-01//0.00"
    assert get_trans_euro(transaction) == expected_transeuro
    
    transaction = {
        "date": datetime(2024, 6, 1).isoformat(),
        "description": "Test",
        "amount": 1
    }
    expected_transeuro = "2024-06-01/Test/1.00"
    assert get_trans_euro(transaction) == expected_transeuro

def test_description_validation():
    assert is_valid_description("123456789012") == True
    assert is_valid_description("123_4567_89012") == True
    assert is_valid_description("123/4567/89012") == True
    assert is_valid_description("123.4567.89012") == True
    assert is_valid_description("123-4567-89012") == True
    assert is_valid_description("") == False
    assert is_valid_description("!@#$%^&*()") == False
    assert is_valid_description("1234567890") == False
    assert is_valid_description("1234567890123") == False
    assert is_valid_description("ABCDEFGHIJKL") == False
    assert is_valid_description("A23-4567-89012") == False

def test_get_account_from_description():
    assert get_account_from_description("123456789012") == "123-4567-89012"
    assert get_account_from_description("123_4567_89012") == "123-4567-89012"
    assert get_account_from_description("123/4567/89012") == "123-4567-89012"
    assert get_account_from_description("123.4567.89012") == "123-4567-89012"
    assert get_account_from_description("123-4567-89012") == "123-4567-89012"


def test_filter_transaction():
    # Implement tests for the filter_transactions function
    existing_transaction = "123456-123456789"
 
    processed_transactions = [
        {
            "id": "123456-123456789-456"
        },
        {
            "id": existing_transaction
        },
    ]
    
    #OK
    test_transaction = {
        "id": "123456-123456789-123",
        "date": datetime.now().isoformat(),
        "amount": 123.45,
        "currency": "EUR",
        "description": "Test Transaction",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == True
    
    #Not OK - already processed
    test_transaction = {
        "id": existing_transaction,
        "date": datetime.now().isoformat(),
        "amount": 123.45,
        "currency": "EUR",
        "description": "Test Transaction",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == False
    
    #Not OK - negative number
    test_transaction = {
        "id": "123456-123456789-123",
        "date": datetime.now().isoformat(),
        "amount": -1.1,
        "currency": "EUR",
        "description": "Test Transaction",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == False
    
    #Not OK - zero amount
    test_transaction = {
        "id": "123456-123456789-123",
        "date": datetime.now().isoformat(),
        "amount": 0.0,
        "currency": "EUR",
        "description": "Test Transaction",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == False
    
    #Not OK - date before filter date
    test_transaction = {
        "id": "123456-123456789-123",
        "date": (datetime.now() - timedelta(days=2)).isoformat(),
        "amount": 123.45,
        "currency": "EUR",
        "description": "Test Transaction",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == False
 
    #Ok empty description
    test_transaction = {
        "id": "123456-123456789-123",
        "date": datetime.now().isoformat(),
        "amount": 123.45,
        "currency": "EUR",
        "description": "",
        "counterpartName": "John Doe",
        "counterpartReference": "BE000"
    }
    filter_date = datetime.now() - timedelta(days=1)
    assert filter_transaction(test_transaction, processed_transactions, filter_date) == True

def test_filter_transactions():
    # Implement tests for the filter_transactions function
    existing_transaction = "123456-123456789"
 
    processed_transactions = [
        {
            "id": "123456-123456789-456"
        },
        {
            "id": existing_transaction
        },
    ]
    
    #OK tests
    raw_transactions = [
        {
            "id": "123456-123456789-123",
            "attributes": {
                "executionDate": datetime.now().isoformat(),
                "amount": 123.45,
                "currency": "EUR",
                "remittanceInformation": "Test Transaction",
                "counterpartName": "John Doe",
                "counterpartReference": "BE000"
            }
        },
    ]
    filter_date = datetime.now() - timedelta(days=1)
    filtered_transactions = filter_transactions(raw_transactions, processed_transactions, filter_date)
    assert len(filtered_transactions) == 1
    assert filtered_transactions[0]["id"] == "123456-123456789-123"
    assert filtered_transactions[0]["date"] == raw_transactions[0]["attributes"]["executionDate"]
    assert filtered_transactions[0]["amount"] == raw_transactions[0]["attributes"]["amount"]
    assert filtered_transactions[0]["currency"] == raw_transactions[0]["attributes"]["currency"]
    assert filtered_transactions[0]["description"] == raw_transactions[0]["attributes"]["remittanceInformation"]
    assert filtered_transactions[0]["counterpartName"] == raw_transactions[0]["attributes"]["counterpartName"]
    assert filtered_transactions[0]["counterpartReference"] == raw_transactions[0]["attributes"]["counterpartReference"]

    # OK date with Z 
    raw_transactions = [
        {
            "id": "123456-123456789-123",
            "attributes": {
                "executionDate": datetime.now().strftime("%Y-%m-%d") +"T23:00:00.000Z",
                "amount": 123.45,
                "currency": "EUR",
                "remittanceInformation": "Test Transaction",
                "counterpartName": "John Doe",
                "counterpartReference": "BE000"
            }
        },
    ]
    
    filter_date = datetime.now() - timedelta(days=1)
    filtered_transactions = filter_transactions(raw_transactions, processed_transactions, filter_date)
    assert len(filtered_transactions) == 1
    
    date = datetime.fromisoformat(raw_transactions[0]["attributes"]["executionDate"].replace("Z", "+00:00"))
    assert filtered_transactions[0]["date"] == date.isoformat()


def test_make_payment():
    # Implement tests for the make_payment function
    pass

if __name__ == "__main__":
    
    test_get_trans_euro()
    test_description_validation()
    test_get_account_from_description()
    test_filter_transaction()
    test_filter_transactions()
    test_make_payment()
    print("All tests passed!")