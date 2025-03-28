import requests
from dotenv import load_dotenv
from flask import redirect, render_template, session
from functools import wraps
import os
from datetime import datetime
import pytz
import mimetypes
import http.client
import pyotp
from logzero import logger
import json

def configure():
    load_dotenv()

configure()
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

def angel_quote(tokens, exchange):
    conn = http.client.HTTPSConnection("apiconnect.angelone.in")
    CLIENT_KEY = os.getenv("ANGEL_CLIENT_KEY")
    CLIENT_PIN = int(os.getenv("ANGEL_CLIENT_PIN"))

    TOTP_CODE = None 
    try:
        token = os.getenv("ANGEL_TOTP_SECRET")
        TOTP_CODE = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e
     
    payload = f"{{\n\"clientcode\":\"{CLIENT_KEY}\",\n\"password\":\"{CLIENT_PIN}\"\n,\n\"totp\":\"{TOTP_CODE}\"\n}}"

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '000.000.0.00',
        'X-ClientPublicIP': '000.000.00.000',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': os.getenv("ANGEL_API_KEY")
    }
    conn.request( "POST", "/rest/auth/angelbroking/user/v1/loginByPassword", payload, headers )

    res = conn.getresponse()
    hi = res.read()

    
    angel_log =  json.loads(hi)  # ✅ Return parsed JSON
        

    
    conn = http.client.HTTPSConnection("apiconnect.angelone.in")

    try:
        # Convert payload to JSON and encode it to bytes
        payload = json.dumps({
            "mode": "LTP",
            "exchangeTokens": {
                exchange.upper(): [tokens]
            }
        }).encode('utf-8')  # <-- Fix: Encode as bytes

        headers = {
            'X-PrivateKey': os.getenv("ANGEL_API_KEY"),
            'Accept': 'application/json',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '000.000.0.00',
            'X-ClientPublicIP': '000.000.00.000',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-UserType': 'USER',
            'Authorization': f"Bearer {angel_log['data']['jwtToken']}",  # Ensure this exists
            'Content-Type': 'application/json'
        }

        # Send request
        conn.request("POST", "/rest/secure/angelbroking/market/v1/quote/", payload, headers)
        
        res = conn.getresponse()
        data = res.read()
        try:
            # Convert JSON response to a dictionary
            response_json = json.loads(data)

            # Extract the quote data safely
            quotes = response_json.get("data", {}).get("fetched", [])

            if quotes:  # Check if list is not empty
                quote = quotes[0]  # Get the first quote from the list
                return {
                    "symbol": quote.get("tradingSymbol"),
                    "token": quote.get("symbolToken", int(tokens)),
                    "price": float(quote.get("ltp"))
                }
            else:
                return None
        except json.JSONDecodeError:
            print("Error decoding JSON response.")
            return None
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None

def coin(id):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={id.lower()}"

    try:
        headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": os.getenv("CRYPTO_API_KEY")
            }

        response = requests.get(url, headers=headers)

        response.raise_for_status()  # Raise an error for HTTP error responses
        data = response.json()

        # Check if the returned data is a non-empty list
        if not data or len(data) == 0:
            return None

        quote = data[0]
        return {
            "id": quote.get("id", id.lower()),
            "name": quote.get("name"),
            "current_price": quote.get("current_price")
        }
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None


def lookup(symbol):
    """Look up quote for symbol."""
    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol.upper()}?apikey={os.getenv('NASDAQ_API_KEY')}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP error responses
        data = response.json()

        # Check if the returned data is a non-empty list
        if not data or len(data) == 0:
            return None

        quote = data[0]
        return {
            "name": quote.get("name"),
            "price": quote.get("price"),
            "symbol": quote.get("symbol", symbol.upper())
        }
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None


def usd_nasdaq(value):
    if value is None:
        return f"Error getting value"
    return f"${value:,.2f}"


def inr(value):
    return f"\u20B9{value}"

def usd_coin(value):
    return f"${value}"