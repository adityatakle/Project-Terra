def angel_log_info():
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
    try:
        response_json = json.loads(hi)  # Convert string to dictionary
        return json.loads(hi)  # ✅ Return parsed JSON
    except json.JSONDecodeError:
        print("Error decoding JSON response.")
        return None
    

angel_log = angel_log_info()


def angel_quote(token, exchange):
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

    try:
        angel_log =  json.loads(hi)  # ✅ Return parsed JSON
    except json.JSONDecodeError:
        print("Error decoding JSON response.")
        

    token = int(token)
    conn = http.client.HTTPSConnection("apiconnect.angelone.in")

    try:
        # Convert payload to JSON and encode it to bytes
        payload = json.dumps({
            "mode": "LTP",
            "exchangeTokens": {
                exchange.upper(): [token]
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
                    "token": quote.get("symbolToken", int(token)),
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
