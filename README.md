# Zinne Bank Watch
sets of python scripts

The "getBankingInfo.py" allow to watch the bank account using the myPonto service and retrieve transactions. 

The "setPayment.py" allow to top off an account in the cyclos SPE

The "check_topoff.py" allow to create the full sequence (get banking transaction then setPayments). 

Note:
  - If you run "getBankingInfo.py" or "setPayment.py" individually, it will execute some unit tests and edge cases.
  - The first time the "setPayment.py" is run it takes some time as it create a local copy of the accounts in user_list.json.
  - Once a transaction has been commited, the last Id is saved in a local file

TO CHECK:
  - Transaction order is wrong --> we might need to invert it to process older transaction first and then the newest

## create a virtual env

```back
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
```

## Env File
Create a .env file containign the following

```json
MY_PONTO_ID="YOUR_ID"
MY_PONTO_SECRET="YOUR_SECRET"
MY_PONTO_URL="https://api.myponto.com"

BANK_ACCOUNT_IBAN="YOUR_BANK_ACCOUNT"

CURRENCY="YOUR_CURRENCY"

LAST_DAYS_TO_CHECK = 1

SPE_URL="https:URL"
SPE_ACCESS_KEY="YOUR_API_KEY"

SIGNAL_URL="http:URL"
SIGNAL_SOURCE_NUMBER="+32123456789"
SIGNAL_DESTINATION_GROUP="group.KEY"
```
