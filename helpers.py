import requests
import time
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
import logging
import sqlite3

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
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File to cache the token
TOKEN_CACHE_FILE = "angel_token_cache.json"
# Token validity duration in seconds (24 hours)
TOKEN_VALIDITY_SECONDS = 24 * 60 * 60

def load_cached_token():
    """
    Loads the cached token from file if it exists and is not expired.
    """
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r") as f:
                cache = json.load(f)
            expiry = cache.get("expiry", 0)
            if time.time() < expiry:
                logger.info("Loaded valid cached token.")
                return cache.get("login_response")
            else:
                logger.info("Cached token has expired.")
        except Exception as e:
            logger.error("Error loading cached token: %s", e)
    return None

def save_cached_token(login_response):
    """
    Saves the login response along with an expiry timestamp.
    """
    cache = {
        "login_response": login_response,
        "expiry": time.time() + TOKEN_VALIDITY_SECONDS
    }
    try:
        with open(TOKEN_CACHE_FILE, "w") as f:
            json.dump(cache, f)
        logger.info("Cached token saved successfully.")
    except Exception as e:
        logger.error("Error saving cached token: %s", e)

def angel_login():
    """
    Logs in to AngelOne API. If a cached token exists and is valid (not expired),
    it returns that token. Otherwise, it performs a new login and caches the result.
    """
    # Check for cached token first
    cached_response = load_cached_token()
    if cached_response is not None:
        return cached_response

    conn = http.client.HTTPSConnection("apiconnect.angelone.in")
    CLIENT_KEY = os.getenv("ANGEL_CLIENT_KEY")
    CLIENT_PIN = os.getenv("ANGEL_CLIENT_PIN")  # keep as string for JSON formatting

    # Generate TOTP code using your secret
    try:
        token = os.getenv("ANGEL_TOTP_SECRET")
        TOTP_CODE = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e

    payload = f"""{{
        "clientcode": "{CLIENT_KEY}",
        "password": "{CLIENT_PIN}",
        "totp": "{TOTP_CODE}"
    }}"""

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

    conn.request("POST", "/rest/auth/angelbroking/user/v1/loginByPassword", payload, headers)
    res = conn.getresponse()
    logger.info("Login API status: %s %s", res.status, res.reason)
    response_data = res.read().decode("utf-8")
    logger.info("Raw response from Angel API: %r", response_data)

    if res.status != 200:
        logger.error("API returned non-200 status code")
        raise Exception(f"Login failed with status {res.status}: {response_data}")

    try:
        login_response = json.loads(response_data)
    except json.JSONDecodeError as e:
        logger.error("Could not decode login response: %s", e)
        raise e

    # Save the new token to cache
    save_cached_token(login_response)
    return login_response

def angel_quote(tokens, exchange):
    """
    Fetches a quote using the AngelOne API. Uses the cached JWT token from angel_login.
    """
    login_response = angel_login()
    jwt_token = login_response.get("data", {}).get("jwtToken")
    if not jwt_token:
        logger.error("JWT token not found in login response.")
        raise Exception("Missing JWT token.")

    conn = http.client.HTTPSConnection("apiconnect.angelone.in")
    
    try:
        payload = json.dumps({
            "mode": "LTP",
            "exchangeTokens": {
                exchange.upper(): [tokens]
            }
        }).encode('utf-8')  # Ensure payload is bytes

        headers = {
            'X-PrivateKey': os.getenv("ANGEL_API_KEY"),
            'Accept': 'application/json',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '000.000.0.00',
            'X-ClientPublicIP': '000.000.00.000',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-UserType': 'USER',
            'Authorization': f"Bearer {jwt_token}",
            'Content-Type': 'application/json'
        }

        conn.request("POST", "/rest/secure/angelbroking/market/v1/quote/", payload, headers)
        res = conn.getresponse()
        data = res.read()
        try:
            response_json = json.loads(data)
            quotes = response_json.get("data", {}).get("fetched", [])
            if quotes:
                quote = quotes[0]
                return {
                    "symbol": quote.get("tradingSymbol"),
                    "token": quote.get("symbolToken", int(tokens)),
                    "price": float(quote.get("ltp"))
                }
            else:
                logger.info("No quote data received.")
                return None
        except json.JSONDecodeError:
            logger.error("Error decoding JSON response.")
            return None
    except Exception as e:
        logger.error("Error fetching quote: %s", e)
        raise e

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


def options_greek_ism(name, expirydate):
    login_response = angel_login()
    jwt_token = login_response.get("data", {}).get("jwtToken")
    if not jwt_token:
        logger.error("JWT token not found in login response.")
        raise Exception("Missing JWT token.")
    
    # API URL for option Greek
    url = "https://apiconnect.angelone.in/rest/secure/angelbroking/marketData/v1/optionGreek"
    
    try:
        # Fetch JSON data
        headers = {
            'X-PrivateKey': os.getenv("ANGEL_API_KEY"),
            'Accept': 'application/json',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '000.000.0.00',
            'X-ClientPublicIP': '000.000.00.000',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-UserType': 'USER',
            'Authorization': f"Bearer {jwt_token}",  # Ensure this exists
            'Content-Type': 'application/json'
        }
        body = {"name":name, "expirydate":expirydate}
    
        response = requests.post(url, json=body, headers=headers).json()
    
        return response["data"]

    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None

'''
# DO NOT UNCOMMENT OR DELETE THIS CODE 
# UNCOMMENT TO UPDATE THE DATABASE ONLY AFTER A DAY MINIMUM OF LAST UPDATED
# LAST UPDATED - "April 3rd, 2025 12:32:00 am"
# ITS UPDATES FUCKING DATABASE

def instruments_list_ism():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Get the directory of the current file (app.py)
        basedir = os.path.abspath(os.path.dirname(__file__))

    # Define the database directory
        db_dir = os.path.join(basedir, "database")
        data_db_path = os.path.join(db_dir, "instruments_ism.db")

        # Ensure the directory exists
        os.makedirs(os.path.dirname(data_db_path), exist_ok=True)

        conn = sqlite3.connect(data_db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrip_master (
            token TEXT NOT NULL,
            symbol TEXT,
            name TEXT,
            expiry TEXT,
            strike TEXT,
            lotsize INTEGER,
            instrument TEXT,
            exch_seg TEXT NOT NULL,
            tick_size REAL
        )
        """)
        # Create table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrip_NSE (
            token TEXT NOT NULL,
            symbol TEXT,
            name TEXT,
            expiry TEXT,
            strike TEXT,
            lotsize INTEGER,
            instrument TEXT,
            exch_seg TEXT NOT NULL,
            tick_size REAL
        )
        """)
        # Insert data
        for item in data:
            cursor.execute("""
            INSERT OR REPLACE INTO scrip_master (token, symbol, name, expiry, strike, lotsize, instrument, exch_seg, tick_size) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get("token"), 
                item.get("symbol"), 
                item.get("name"), 
                item.get("expiry"), 
                item.get("strike"), 
                item.get("lotsize"), 
                item.get("instrument"), 
                item.get("exch_seg"), 
                item.get("tick_size")
            ))

        for item in data:
            if item.get("exch_seg") == "NSE":
                cursor.execute("""
                INSERT OR REPLACE INTO scrip_NSE (token, symbol, name, expiry, strike, lotsize, instrument, exch_seg, tick_size) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("token"), 
                    item.get("symbol"), 
                    item.get("name"), 
                    item.get("expiry"), 
                    item.get("strike"), 
                    item.get("lotsize"), 
                    item.get("instrument"), 
                    item.get("exch_seg"), 
                    item.get("tick_size")
                    ))

        conn.commit()
        conn.close()

    else:
        print(f"Error fetching data: {response.status_code}")
        return None

'''

def usd_nasdaq(value):
    if value is None:
        return f"Error getting value"
    return f"${value:,.2f}"


def inr(value):
    return f"\u20B9{value:,.2f}"

def usd_coin(value):
    return f"${value:,.2f}"