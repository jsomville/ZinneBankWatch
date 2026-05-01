from dotenv import load_dotenv, parser
from logger import log_this, config_logging
import json
import traceback
import re
from datetime import datetime

load_dotenv()

debug_this = False

def filter_transactions(raw_transactions, processed_transactions, date_from):
    """Process transactions and extract relevant information"""
    try:
        filtered_transactions = []

        for raw_transaction in raw_transactions:
            
            #Map raw_transaction into transaction
            date_str = raw_transaction.get("attributes", {}).get("executionDate")
            transaction_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            transaction = {
                "id": raw_transaction.get("id"),
                "date": transaction_date.isoformat(),
                "amount": raw_transaction.get("attributes", {}).get("amount"),
                "currency": raw_transaction.get("attributes", {}).get("currency"),
                "description": raw_transaction.get("attributes", {}).get("remittanceInformation"),
                "counterpartName" : raw_transaction.get("attributes", {}).get("counterpartName"),
                "counterpartReference" : raw_transaction.get("attributes", {}).get("counterpartReference")
            }
            
            result = filter_transaction(transaction, processed_transactions, date_from)
            if not result:
                continue
            
            filtered_transactions.append(transaction)
        
        return filtered_transactions
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error processing transactions: {message}")
        raise

def filter_transaction(transaction, processed_transactions, date_from: datetime):
    
    #Filter out already processed transactions
    if processed_transactions is not None:
        if any(pt.get("id") == transaction["id"] for pt in processed_transactions):
            return False
    
    #Filter out transaction based on amount
    if transaction["amount"] <= 0:
        return False
    
    #Filter out transaction based on date filter
    date = transaction["date"]
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace("Z", "+00:00"))
    if date.date() <= date_from.date():   
        return False
    
    return True