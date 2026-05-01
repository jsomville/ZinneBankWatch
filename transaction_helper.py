
from datetime import datetime
import re


def get_trans_euro(transaction : any) -> str:
    """Get transaction amount in euros"""

    date = transaction["date"]
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace("Z", "+00:00"))

    return f"{date.strftime('%Y-%m-%d')}/{transaction['description']}/{transaction['amount']:.2f}"

def is_valid_description(description: str) -> bool:
    """Validate the description"""
    
    #Empty String
    if not description:
         return False

    #Remove special characters
    desc_temp = re.sub(r'[.,\-_\/]', '', description)
    if not desc_temp:
        return False
    if len(desc_temp) != 12:
        return False
    #is all numbers
    if not re.match(r'^\d{12}', desc_temp):
        return False
    
    return True

def get_account_from_description(description: str) -> str:
    """Extract account number from description"""
    #Remove special characters
    desc_temp = re.sub(r'[.,\-_\/]', '', description)
    
    return f"{desc_temp[:3]}-{desc_temp[3:7]}-{desc_temp[7:]}"