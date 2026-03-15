# Zinne Bank Watch
sets of python scripts

The "getBankingInfo.py" allow to watch the bank account using the myPonto service and retrieve transactions. 

The "setPayment.py" allow to top off an account in the cyclos SPE

## Env File
Create a .env file containign the following

```json
MY_PONTO_ID="YOUR_ID"
MY_PONTO_SECRET="YOUR_SECRET"
MY_PONTO_URL="https://api.myponto.com"

BANK_ACCOUNT_IBAN="YOUR_BANK_ACCOUNT"

CURRENCY="YOUR_CURRENCY"

SPE_URL="https:URL"
SPE_ACCESS_KEY="YOUR_API_KEY"
```
