import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone
from helpers import login_required, lookup, usd_nasdaq, coin, usd_coin, angel_quote, inr

# Configure application
app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=True)

# Custom filter
app.jinja_env.filters["usd_nasdaq"] = usd_nasdaq
app.jinja_env.filters["usd_coin"] = usd_coin
app.jinja_env.filters["inr"] = inr

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Get the directory of the current file (app.py)
basedir = os.path.abspath(os.path.dirname(__file__))

# Define the database directory
db_dir = os.path.join(basedir, "database")

# Define database file paths explicitly
users_db_path = os.path.join(db_dir, "users.db")
nasdaq_db_path = os.path.join(db_dir, "nasdaq.db")
crypto_db_path = os.path.join(db_dir, "crypto.db")
angel_db_path = os.path.join(db_dir, "angel.db")

# Create database connections
users_db = SQL(f"sqlite:///{users_db_path}")
nasdaq_db = SQL(f"sqlite:///{nasdaq_db_path}")
crypto_db = SQL(f"sqlite:///{crypto_db_path}")
angel_db = SQL(f"sqlite:///{angel_db_path}")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

EXCHANGE = "NSE"

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        # declare variable to display message.
        message = None

        # Ensure username and password was submitted 
        if not username or not password:
            message = "Enter both Field"
            return render_template("register.html", messagelogy = message)
        
        # Ensure password and confirm password matches.
        if password != confirmation:
            message = "Password and Confirm password dont match"
            return render_template("register.html", apology = message)
        
        # Execute query to get all usernames from users table.
        existing_user = users_db.execute("SELECT username FROM users WHERE username = ?", username)
        
        # Ensure username does not exist already.
        if existing_user:
            message = "Username already taken"
            return render_template("register.html", apology = message)
        
        # Hash the password
        hash = generate_password_hash(str(password), method='scrypt', salt_length=16)
        
        # current time
        now_utc = datetime.now(timezone.utc)

        # Execute query to add cerdentials to users table.
        users_db.execute("INSERT INTO users (username, hash, created_at) VALUES (?,?,?)", username, hash, now_utc)

        # Redirect user to login page. 
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        message = None
        # Ensure username was submitted
        if not request.form.get("username"):
            message = "Must provide username"
            return render_template("login.html", apology = message)
        
        # Ensure password was submitted
        elif not request.form.get("password"):
            message = "Must provide password"
            return render_template("login.html", apology = message)
            
        # Query database for username
        rows = users_db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            message = "invalid username and/or password"
            return render_template("login.html", apology = message)
        
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
        

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/")
@login_required
def index():
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("index.html")


@app.route("/about_me")
@login_required
def about_me():
    # User reached route via GET (as by clicking a link)
    return render_template("about_me.html")

@app.route("/buy_angel", methods=["GET", "POST"])
@login_required
def buy_angel():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        token = request.form.get("token")
        shares = request.form.get("shares")
        # Convert symbol to upper case
        token = int(token)
        
        # declare variable to display message.
        message = None 

        # Query users table and load angel wallet money in variable.
        wallet = users_db.execute("SELECT angel_cash FROM users WHERE id = ?", session["user_id"])
        wallet = wallet[0]["angel_cash"]

        # Ensure token and shares are submitted and shares input is a digit.
        if not token or not shares :
            message = "ENTER BOTH FIELDS"
            return render_template("buy_angel.html", apology = message)
        # Ensure shares input is a digit.
        if not shares.isdigit():
            message = "SHARES COUNT SHOULD BE A DIGIT"
            return render_template("buy_angel.html", apology = message)

        # Convert string to integer.
        shares = int(shares)

        # Ensure shares count is positive value
        if shares <= 0:
            message = "INVALID SHARES INPUT"
            return render_template("buy_angel.html", apology = message)
        
        # Get info about symbol
        find = angel_quote(token, EXCHANGE)

        # Ensure token is valid.  
        if find is None:
            message = "INVALID TOKEN"
            return render_template("buy_angel.html", apology = message)
        
        # Get price of token and calculate total price and store it in a variable.
        price = float(find["price"])
        total_price = price * shares

        # Ensure user has money to do transaction.
        if wallet < total_price:
            message = "NOT ENOUGH MONEY"
            return render_template("buy_angel.html", apology = message)

        now_utc = datetime.now(timezone.utc)
        
        # Query portfolio table and store tokens in variable.
        port = angel_db.execute("SELECT token FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_tokens = {row["token"] for row in port}
        
        # If already exist then update the count of shares and update it in portfolio table. 
        if token in existing_tokens:
            exist = angel_db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND token = ?",
                               session["user_id"], token)
            if exist:
                # Ensure shares are treated as integers
                new_shares = int(exist[0]["shares"]) + shares
                angel_db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND token = ?",
                           new_shares, session["user_id"], token)
        
        # If does not exist then make a new entry and store in portfolio table. 
        else:
            angel_db.execute("INSERT INTO portfolio (user_id, token, shares) VALUES (?, ?, ?)",
                       session["user_id"], token, shares)
        
        # Insert transaction in buy and history tables. 
        angel_db.execute("INSERT INTO buy (user_id, token, shares, price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], token, shares, price, now_utc)
        angel_db.execute("INSERT INTO history (user_id, token, shares, price, timestamp, type) VALUES (?,?,?,?,?,'BUY')",
                   session["user_id"], token, shares, price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET angel_cash = ? WHERE id = ?",
                   wallet - total_price, session["user_id"])
        
        # Redirect user to portfolio page
        return redirect("/angel")
    
    # User reached route via GET (as by clicking a link)
    return render_template("buy_angel.html")


@app.route("/buy_coin", methods=["GET", "POST"])
@login_required
def buy_coin():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Store input and store in variables.
        id = request.form.get("id")
        coins = request.form.get("coins")
        # convert id to lower case.
        id = id.lower().strip()
        
        # declare variable to display message.
        message = None
        
        # Query users table Load crypto wallet money in variable.
        wallet = users_db.execute("SELECT crypto_cash FROM users WHERE id = ?", session["user_id"])
        wallet = wallet[0]["crypto_cash"]

        # Ensure id and coins are submitted.
        if not id or not coins:
            message = "ENTER BOTH FIELDS"
            return render_template("buy_coin.html", apology = message)
        # Ensure coins input is a digit
        if not coins.isdigit():
            message = "COINS COUNT SHOULD BE A DIGIT"
            return render_template("buy_coin.html", apology = message)
        
        # Convert string to integer.
        coins = int(coins)

        # Ensure coins count is positive value
        if coins <= 0:
            message = "INVALID COINS INPUT"
            return render_template("buy_coin.html", apology = message)

        # Get info about id.
        find = coin(id)
        # Ensure coin is valid.
        if find is None:
            message = "INVALID COIN"
            return render_template("buy_coin.html", apology = message)
        
        # Get price of symbol and calculate total price and store it in a variable.
        price = find["current_price"]
        total_price = price * coins

        # Ensure user has money to do transaction.
        if wallet < total_price:
            message = "NOT ENOUGH MONEY"
            return render_template("buy_coin.html", apology = message)

        now_utc = datetime.now(timezone.utc)
        
        # Query portfolio table and store coin id in variable.
        port = crypto_db.execute("SELECT coin_id FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_id = {row["coin_id"] for row in port}
        
        # If already exist then update the count of coins and update it in portfolio table. 
        
        if id in existing_id:
            exist = crypto_db.execute("SELECT coins FROM portfolio WHERE user_id = ? AND coin_id = ?",
                               session["user_id"], id)
            if exist:
                # Ensure coins are treated as integers
                new_coins = int(exist[0]["coins"]) + coins
                crypto_db.execute("UPDATE portfolio SET coins = ? WHERE user_id = ? AND coin_id = ?", new_coins, session["user_id"], id)
        
        # If does not exist then make a new entry and store in portfolio table. 
        else:
            crypto_db.execute("INSERT INTO portfolio (user_id, coin_id , coins ) VALUES (?, ?, ?)", session["user_id"], id, coins)
        
        # Insert transaction in buy and history tables. 
        crypto_db.execute("INSERT INTO buy (user_id, coin_id , coins , price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], id, coins, price, now_utc)
        crypto_db.execute("INSERT INTO history (user_id, coin_id, coins , price, timestamp, type) VALUES (?,?,?,?,?,'BUY')",
                   session["user_id"], id, coins, price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET crypto_cash = ? WHERE id = ?",
                   wallet - total_price, session["user_id"])

        # Redirect user to portfolio page
        return redirect("/coin")
    
    # User reached route via GET (as by clicking a link)
    return render_template("buy_coin.html")


@app.route("/buy_nasdaq", methods=["GET", "POST"])
@login_required
def buy_nasdaq():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # Convert symbol to upper case
        symbol = symbol.upper()
        
        # declare variable to display message.
        message = None 

        # Query users table and load nasdaq wallet money in variable.
        wallet = users_db.execute("SELECT nasdaq_cash FROM users WHERE id = ?", session["user_id"])
        wallet = wallet[0]["nasdaq_cash"]

        # Ensure symbol and shares are submitted and shares input is a digit.
        if not symbol or not shares :
            message = "ENTER BOTH FIELDS"
            return render_template("buy_nasdaq.html", apology = message)
        # Ensure shares input is a digit.
        if not shares.isdigit():
            message = "SHARES COUNT SHOULD BE A DIGIT"
            return render_template("buy_nasdaq.html", apology = message)

        # Convert string to integer.
        shares = int(shares)

        # Ensure shares count is positive value
        if shares <= 0:
            message = "INVALID SHARES INPUT"
            return render_template("buy_nasdaq.html", apology = message)
        
        # Get info about symbol
        find = lookup(symbol)

        # Ensure symbol is valid.  
        if find is None:
            message = "INVALID SYMBOL"
            return render_template("buy_nasdaq.html", apology = message)
        
        # Get price of symbol and calculate total price and store it in a variable.
        price = float(find["price"])
        total_price = price * shares

        # Ensure user has money to do transaction.
        if wallet < total_price:
            message = "NOT ENOUGH MONEY"
            return render_template("buy_nasdaq.html", apology = message)

        now_utc = datetime.now(timezone.utc)
        
        # Query portfolio table and store symbols in variable.
        port = nasdaq_db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_symbols = {row["symbol"] for row in port}
        
        # If already exist then update the count of shares and update it in portfolio table. 
        if symbol in existing_symbols:
            exist = nasdaq_db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?",
                               session["user_id"], symbol)
            if exist:
                # Ensure shares are treated as integers
                new_shares = int(exist[0]["shares"]) + shares
                nasdaq_db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                           new_shares, session["user_id"], symbol)
        
        # If does not exist then make a new entry and store in portfolio table. 
        else:
            nasdaq_db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES (?, ?, ?)",
                       session["user_id"], symbol, shares)
        
        # Insert transaction in buy and history tables. 
        nasdaq_db.execute("INSERT INTO buy (user_id, symbol, shares, price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], symbol, shares, price, now_utc)
        nasdaq_db.execute("INSERT INTO history (user_id, symbol, shares, price, timestamp, type) VALUES (?,?,?,?,?,'BUY')",
                   session["user_id"], symbol, shares, price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET nasdaq_cash = ? WHERE id = ?",
                   wallet - total_price, session["user_id"])
        
        # Redirect user to portfolio page
        return redirect("/nasdaq")
    
    # User reached route via GET (as by clicking a link)
    return render_template("buy_nasdaq.html")


@app.route("/history_angel")
@login_required
def history_angel():
    """Show history of transactions"""
    # Execute query to get data from history table.
    history = angel_db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY timestamp DESC", session["user_id"])
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("history_angel.html", history=history)


@app.route("/history_coin")
@login_required
def history_coin():
    """Show history of transactions"""
    # Execute query to get data from history table.
    history = crypto_db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY timestamp DESC", session["user_id"])

    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("history_coin.html", history=history)


@app.route("/history_nasdaq")
@login_required
def history_nasdaq():
    """Show history of transactions"""
    # Execute query to get data from history table.
    history = nasdaq_db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY timestamp DESC", session["user_id"])
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("history_nasdaq.html", history=history)


@app.route("/angel")
@login_required
def index_angel():
    # Execute query to get token and shares from portfolio table. 
    tokens_all = angel_db.execute(
        "SELECT token, shares FROM portfolio WHERE user_id = ? GROUP BY token", session["user_id"])

    # Get current price of tokens from portfolio table.
    current_price = {}
    for tokens in tokens_all:
        find = angel_quote(tokens["token"], EXCHANGE)
        current_price[tokens["token"]] = float(find["price"])

    # Execute query from users table to get angel cash of user. 
    wallet = users_db.execute("SELECT angel_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["angel_cash"]
    value = sum(current_price[tokens["token"]] * int(tokens["token"]) for tokens in tokens_all)
    value += wallet
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("index_angel.html", stocks_all=tokens_all, current_price=current_price, value=value, wallet=wallet)


@app.route("/coin")
@login_required
def index_coin():
    # Execute query to get coin id and coins from portfolio table.
    coins_all = crypto_db.execute("SELECT coin_id, coins FROM portfolio WHERE user_id = ? GROUP BY coin_id", session["user_id"])

    # Get current price of coin id from portfolio table.
    current_price = {}
    for coins in coins_all:
        find = coin(coins["coin_id"])
        current_price[coins["coin_id"]] = float(find["current_price"])

    # Execute query from users table to get nasdaq cash of user.
    wallet = users_db.execute("SELECT crypto_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["crypto_cash"]
    value = sum(current_price[coins["coin_id"]] * (coins["coins"]) for coins in coins_all)
    value += wallet

    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("index_coin.html", coins_all=coins_all, current_price=current_price, value=value, wallet=wallet)


@app.route("/nasdaq")
@login_required
def index_nasdaq():
    # Execute query to get symbol and shares from portfolio table. 
    stocks_all = nasdaq_db.execute(
        "SELECT symbol, shares FROM portfolio WHERE user_id = ? GROUP BY symbol", session["user_id"])

    # Get current price of symbols from portfolio table.
    current_price = {}
    for stock in stocks_all:
        find = lookup(stock["symbol"])
        current_price[stock["symbol"]] = float(find["price"])

    # Execute query from users table to get nasdaq cash of user. 
    wallet = users_db.execute("SELECT nasdaq_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["nasdaq_cash"]
    value = sum(current_price[stock["symbol"]] * int(stock["shares"]) for stock in stocks_all)
    value += wallet
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("index_nasdaq.html", stocks_all=stocks_all, current_price=current_price, value=value, wallet=wallet)


@app.route("/quote_angel", methods=["GET", "POST"])
@login_required
def quote_angel():
    """Get token data."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Store token in variable
        quote = int(request.form.get("token").strip())
        
        # declare message variable as None for default
        message = None

        # Ensure token is not empty
        if not quote:
            message = "quote field empty"
            return render_template("quote_token.html", apology=message)
        
        # get info about token
        find = angel_quote(quote, EXCHANGE)

        # Give user message if the token is invalid.
        if find is None:
            message = "Wrong quote token id"
            return render_template("quote_angel.html", apology = message)
        
        # Return information of token.
        if find is not None:
            return render_template("quote_angel.html", find=find)
        
    # User reached route via GET (as by clicking a link)
    return render_template("quote_angel.html", find=None)


@app.route("/quote_coin", methods=["GET", "POST"])
@login_required
def quote_coin():
    """Get coin data."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Store symbol in variable
        quote = request.form.get("id").lower().strip()
        
        # declare message variable as None for default
        message = None

        # Ensure id is not empty
        if not quote:
            message = "quote field empty"
            return render_template("quote_coin.html", apology=message)
        
        # get info about id
        find = coin(quote)

        # Give user message if the id is invalid.
        if find is None:
            message = "Wrong quote id"
            return render_template("quote_coin.html", apology = message)
        
        # Return information of id.
        if find is not None:
            return render_template("quote_coin.html", find=find)
        
    # User reached route via GET (as by clicking a link)
    return render_template("quote_coin.html", find=None)


@app.route("/quote_nasdaq", methods=["GET", "POST"])
@login_required
def quote_nasdaq():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Store symbol input in variable
        quote = request.form.get("symbol")

        # declare message variable as None for default
        message = None
        
        # Ensure symbol is not empty
        if not quote:
            message = "quote field empty"
            return render_template("quote_nasdaq.html", apology = message)
        
        # get info about symbol
        find = lookup(quote)
        
        # Give user message if the symbol is invalid.
        if find is None:
            message = "wrong quote symbol"
            return render_template("quote_nasdaq.html", apology = message)
        
        # Return information of symbol
        if find is not None:
            return render_template("quote_nasdaq.html", find=find)
    
    # User reached route via GET (as by clicking a link)
    return render_template("quote_nasdaq.html", find=None)


@app.route("/sell_angel", methods=["GET", "POST"])
@login_required
def sell_angel():
    # Execute query from buy table to get tokens and sum of shares of user.
    stocks_all = angel_db.execute(
        "SELECT token, SUM(shares) AS s FROM buy WHERE user_id = ? GROUP BY token", session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        token = request.form.get("token")
        shares = request.form.get("shares")

        # declare variable to display message.
        message = None

        # Ensure token and shares are submitted and shares input is a digit.
        if not token or not shares:
            message = "ENTER BOTH FIELDS"
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        # Ensure shares input is a digit.
        if not shares.isdigit():
            message = "SHARES COUNT SHOULD BE A DIGIT"
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        
        # Convert string to integer.
        shares = int(shares)

        # Ensure shares count is positive value
        if shares <= 0 :
            message = "INVALID SHARES INPUT"
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        
        # Get current price of coin id from portfolio table.
        current_price = {}
        for stock in stocks_all:
            stock_lookup = angel_quote(stock["token"], EXCHANGE)
            if stock_lookup is None:
                continue
            current_price[stock["token"]] = float(stock_lookup["price"])

        # Ensure user owns stock
        if token not in current_price:
            message = "You do not own this stock."
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        
        # Query portfolio table and store tokens in variable.
        port = angel_db.execute("SELECT token FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_tokens = {row["token"] for row in port}
        
        # Ensure token exist already
        if token not in existing_tokens:
            message = "You do not own any shares of this stock."
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        
        # Execute query on portfolio table to get number of shares of token.
        exist = angel_db.execute(
            "SELECT shares FROM portfolio WHERE user_id = ? AND token = ?", session["user_id"], token)
        # Ensure share input number less than or equal to they own.
        if not exist or int(exist[0]["shares"]) < shares:
            message = "QUANTITY MORE THAN YOU OWN"
            return render_template("sell_angel.html", apology = message, stocks_all=stocks_all)
        
        # Store share number in variable
        cur = int(exist[0]["shares"])
        # Update portfolio table shares column value if shares sold less than already own if equal then delete the token from portfolio.
        if cur - shares > 0:
            new_shares = cur - shares
            angel_db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND token = ?", new_shares, session["user_id"], token)
        elif cur - shares == 0:
            angel_db.execute("DELETE FROM portfolio WHERE user_id = ? AND token = ?", session["user_id"], token)
        # Get current price of shares and calculate total value.
        current_sale_price = current_price[token]
        total_sale_value = current_sale_price * shares

        # Current time
        now_utc = datetime.now(timezone.utc)
        
        # Insert transaction in sell and history table.
        angel_db.execute("INSERT INTO sell (user_id, token, shares, price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], token, shares, current_sale_price, now_utc)
        angel_db.execute("INSERT INTO history (user_id, token, shares, price, timestamp, type) VALUES (?,?,?,?,?,'SELL')",
                   session["user_id"], token, shares, current_sale_price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET nasdaq_cash = nasdaq_cash + ? WHERE id = ?",
                   total_sale_value, session["user_id"])
        
        # Redirect user to portfolio page
        return redirect("/angel")
    
    # User reached route via GET (as by clicking a link)
    return render_template("sell_angel.html", stocks_all=stocks_all)


@app.route("/sell_coin", methods=["GET", "POST"])
@login_required
def sell_coin():
    # Execute query from buy table to get symbols and sum of shares of user.
    coins_all = crypto_db.execute(
        "SELECT coin_id, SUM(coins) AS s FROM buy WHERE user_id = ? GROUP BY coin_id", session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        id = request.form.get("id")
        coins = request.form.get("coins")

        # declare variable to display message.
        message = None

        # Ensure symbol and shares are submitted and shares input is a digit.
        if not id or not coins:
            message = "ENTER BOTH FIELDS"
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)
        # Ensure coins input is a digit.
        if not coins.isdigit():
            message = "SHARES COUNT SHOULD BE A DIGIT"
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)

        # Convert string to integer.
        coins = int(coins)
        
        # Ensure coins count is positive value
        if coins <= 0:
            message = "INVALID SHARES INPUT"
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)

        # Get current price of coin id from portfolio table.
        current_price = {}
        for coin_row in coins_all:
            find = coin(coin_row["coin_id"])
            if find is None:
                continue
            current_price[coin_row["coin_id"]] = float(find["current_price"])

        # Ensure user owns stock
        if id not in current_price:
            message = "You do not own this coin."
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)
        
        # Query portfolio table and store coin id in variable.
        port = crypto_db.execute("SELECT coin_id FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_id = {row["coin_id"] for row in port}

        # Ensure symbol exist already
        if id not in existing_id:
            message = "You do not own any shares of this stock."
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)
        
        # Execute query on portfolio table to get number of shares of symbol.
        exist = crypto_db.execute(
            "SELECT coins FROM portfolio WHERE user_id = ? AND coin_id = ?", session["user_id"], id)
        # Ensure share input number less than or equal to they own.
        if not exist or int(exist[0]["coins"]) < coins:
            message = "Quantity more than you own."
            return render_template("sell_coin.html", apology = message, coins_all=coins_all)

        # Store share number in variable
        cur = int(exist[0]["coins"])
        # Update portfolio table shares column value if shares sold less than already own if equal then delete the symbol from portfolio.
        if cur - coins > 0:
            new_coins = cur - coins
            crypto_db.execute("UPDATE portfolio SET coins = ? WHERE user_id = ? AND coin_id = ?",
                       new_coins, session["user_id"], id)
        elif cur - coins == 0:
            crypto_db.execute("DELETE FROM portfolio WHERE user_id = ? AND coin_id = ?",
                       session["user_id"], id)

        # Get current price of shares and calculate total value.
        current_sale_price = current_price[id]
        total_sale_value = current_sale_price * coins

        # Current time
        now_utc = datetime.now(timezone.utc)

        # Insert transaction in sell and history table.
        crypto_db.execute("INSERT INTO sell (user_id, coin_id, coins, price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], id, coins, current_sale_price, now_utc)
        crypto_db.execute("INSERT INTO history (user_id, coin_id, coins, price, timestamp, type) VALUES (?,?,?,?,?,'SELL')",
                   session["user_id"], id, coins, current_sale_price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET crypto_cash = crypto_cash + ? WHERE id = ?",
                   total_sale_value, session["user_id"])

        # Redirect user to portfolio page
        return redirect("/coin")
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("sell_coin.html", coins_all=coins_all)


@app.route("/sell_nasdaq", methods=["GET", "POST"])
@login_required
def sell_nasdaq():
    # Execute query from buy table to get symbols and sum of shares of user.
    stocks_all = nasdaq_db.execute(
        "SELECT symbol, SUM(shares) AS s FROM buy WHERE user_id = ? GROUP BY symbol", session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input and store in variable.
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # declare variable to display message.
        message = None

        # Ensure symbol and shares are submitted and shares input is a digit.
        if not symbol or not shares:
            message = "ENTER BOTH FIELDS"
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        # Ensure shares input is a digit.
        if not shares.isdigit():
            message = "SHARES COUNT SHOULD BE A DIGIT"
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        
        # Convert string to integer.
        shares = int(shares)

        # Ensure shares count is positive value
        if shares <= 0:
            message = "INVALID SHARES INPUT"
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        
        # Get current price of coin id from portfolio table.
        current_price = {}
        for stock in stocks_all:
            stock_lookup = lookup(stock["symbol"])
            if stock_lookup is None:
                continue
            current_price[stock["symbol"]] = float(stock_lookup["price"])

        # Ensure user owns stock
        if symbol not in current_price:
            message = "You do not own this stock."
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        
        # Query portfolio table and store symbols in variable.
        port = nasdaq_db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
        existing_symbols = {row["symbol"] for row in port}
        
        # Ensure symbol exist already
        if symbol not in existing_symbols:
            message = "You do not own any shares of this stock."
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        
        # Execute query on portfolio table to get number of shares of symbol.
        exist = nasdaq_db.execute(
            "SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        # Ensure share input number less than or equal to they own.
        if not exist or int(exist[0]["shares"]) < shares:
            message = "QUANTITY MORE THAN YOU OWN"
            return render_template("sell_nasdaq.html", apology = message, stocks_all=stocks_all)
        
        # Store share number in variable
        cur = int(exist[0]["shares"])
        # Update portfolio table shares column value if shares sold less than already own if equal then delete the symbol from portfolio.
        if cur - shares > 0:
            new_shares = cur - shares
            nasdaq_db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                       new_shares, session["user_id"], symbol)
        elif cur - shares == 0:
            nasdaq_db.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?",
                       session["user_id"], symbol)
        # Get current price of shares and calculate total value.
        current_sale_price = current_price[symbol]
        total_sale_value = current_sale_price * shares

        # Current time
        now_utc = datetime.now(timezone.utc)
        
        # Insert transaction in sell and history table.
        nasdaq_db.execute("INSERT INTO sell (user_id, symbol, shares, price, timestamp) VALUES (?,?,?,?,?)",
                   session["user_id"], symbol, shares, current_sale_price, now_utc)
        nasdaq_db.execute("INSERT INTO history (user_id, symbol, shares, price, timestamp, type) VALUES (?,?,?,?,?,'SELL')",
                   session["user_id"], symbol, shares, current_sale_price, now_utc)
        # Update wallet money in users table.
        users_db.execute("UPDATE users SET nasdaq_cash = nasdaq_cash + ? WHERE id = ?",
                   total_sale_value, session["user_id"])
        
        # Redirect user to portfolio page
        return redirect("/nasdaq")
    
    # User reached route via GET (as by clicking a link)
    return render_template("sell_nasdaq.html", stocks_all=stocks_all)


@app.route("/wallet_angel", methods=["GET", "POST"])
@login_required 
def wallet_angel():
    # Load wallet money of user to display.
    wallet = users_db.execute("SELECT angel_cash FROM users WHERE id = ?", session["user_id"])
    current_balance = wallet[0]["angel_cash"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input from user.
        amount = request.form.get("amount")
        message = None
        # Check if user value is a number
        if not amount:
            message = "FIELD EMPTY"
            return render_template("wallet_angel.html", current_balance = current_balance, apology = message)
        
        try:
            amount = int(amount)
        except ValueError:
            message = "ENTER NUMERIC VALUE"
            return render_template("wallet_angel.html", current_balance = current_balance, apology = message)

        # Convert user value from str to int.    
        amount= int(amount)

        # Check if value is positive integer.
        if amount <= 0:
            message = "ENTER POSITIVE VALUE"
            return render_template("wallet_angel.html", current_balance = current_balance, apology = message)
        
        # Execute query to update wallet of user.
        users_db.execute("UPDATE users SET nasdaq_cash = ? WHERE id = ?", amount + current_balance, session["user_id"])
        
        # redirect to portfolio
        return redirect("/angel")
    
    # User reached route via GET (as by clicking a link) and current wallet amount is shown.
    return render_template("wallet_angel.html", current_balance = current_balance)


@app.route("/wallet_coin", methods=["GET", "POST"])
@login_required
def wallet_coin():
    # Load wallet money of user to display.
    wallet = users_db.execute("SELECT crypto_cash FROM users WHERE id = ?", session["user_id"])
    current_balance = wallet[0]["crypto_cash"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input from user.
        amount = request.form.get("amount")
        message = None    
        # Check if user value is a number
        if not amount:
            message = "FIELD EMPTY"
            return render_template("wallet_coin.html", current_balance = current_balance, apology = message)
        try:
            amount = int(amount)
        except ValueError:
            message = "ENTER NUMERIC VALUE"
            return render_template("wallet_coin.html", current_balance = current_balance, apology = message)
            
        # Convert user value from str to int.
        amount= int(amount)

        # Check if value is positive integer.
        if amount <= 0:
            message = "FIELD EMPTY"
            return render_template("wallet_coin.html", current_balance = current_balance, apology = message)
            
        # Execute query to update wallet of user.
        users_db.execute("UPDATE users SET crypto_cash = ? WHERE id = ?", amount + current_balance, session["user_id"])

        # redirect to portfolio
        return redirect("/coin")
    
    # User reached route via GET (as by clicking a link) and current wallet amount is shown.
    return render_template("wallet_coin.html", current_balance = current_balance)    


@app.route("/wallet_nasdaq", methods=["GET", "POST"])
@login_required
def wallet_nasdaq():
    # Load wallet money of user to display.
    wallet = users_db.execute("SELECT nasdaq_cash FROM users WHERE id = ?", session["user_id"])
    current_balance = wallet[0]["nasdaq_cash"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get input from user.
        amount = request.form.get("amount")
        message = None
        # Check if user value is a number
        if not amount:
            message = "FIELD EMPTY"
            return render_template("wallet_nasdaq.html", current_balance = current_balance, apology = message)
        
        try:
            amount = int(amount)
        except ValueError:
            message = "ENTER NUMERIC VALUE"
            return render_template("wallet_nasdaq.html", current_balance = current_balance, apology = message)

        # Convert user value from str to int.    
        amount= int(amount)

        # Check if value is positive integer.
        if amount <= 0:
            message = "ENTER POSITIVE VALUE"
            return render_template("wallet_nasdaq.html", current_balance = current_balance, apology = message)
        
        # Execute query to update wallet of user.
        users_db.execute("UPDATE users SET nasdaq_cash = ? WHERE id = ?", amount + current_balance, session["user_id"])
        
        # redirect to portfolio
        return redirect("/nasdaq")
    
    # User reached route via GET (as by clicking a link) and current wallet amount is shown.
    return render_template("wallet_nasdaq.html", current_balance = current_balance)


@app.route("/watchlist_angel", methods=["GET", "POST"])
@login_required
def watchlist_angel():
    # Load wallet from users table.
    wallet = users_db.execute("SELECT angel_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["angel_cash"]
    
    # Load watchlist from table
    stocks_all = angel_db.execute("SELECT token, token FROM watchlist WHERE user_id = ? ORDER BY token ASC", session["user_id"])
    current_price = {}
    for stock in stocks_all:
        fin = angel_quote(stock["token"], EXCHANGE)
        current_price[stock["token"]] = float(fin["price"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Load token from user input and convert to from string to integer. 
        token = request.form.get("token")
        token = int(token)
    
        # Declare message variable as None for default
        message = None
        
        # Ensure token is not empty
        if not token:
            message = "FIELD EMPTY"
            return render_template("watchlist_angel.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )
        
        # Get info of token
        find = angel_quote(token, EXCHANGE)

        # Give user message if the token is invalid.
        if find is None:
            message = "ENTER VALID STOCK SYMBOL"
            return render_template("watchlist_angel.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )

        # Query portfolio table and store tokens in variable.
        port = angel_db.execute("SELECT token FROM watchlist WHERE user_id = ?", session["user_id"])
        existing_tokens = {int(row["token"]) for row in port}

        # Insert info about token if it does not already exist.
        if token not in existing_tokens:
            angel_db.execute("INSERT INTO watchlist (user_id, token, symbol) VALUES (?,?,?)", session["user_id"], find["token"], find["symbol"])
        # Shows message if it already exist.
        if token in existing_tokens:
            message = "ALREADY EXIST IN WATCHLIST"
            return render_template("watchlist_angel.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )
    
    # Query watchlist from table. 
    stocks_all = angel_db.execute("SELECT token, symbol FROM watchlist WHERE user_id = ? ORDER BY symbol ASC", session["user_id"])
    current_price = {}
    for stock in stocks_all:
        fin = angel_quote(stock["token"], EXCHANGE)
        current_price[stock["token"]] = float(fin["price"])
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("watchlist_angel.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet)


@app.route("/watchlist_coin", methods=["GET", "POST"])
@login_required
def watchlist_coin():
    # Load wallet from users table.
    wallet = users_db.execute("SELECT crypto_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["crypto_cash"]
        
    # Load watchlist from table
    coins_all = crypto_db.execute("SELECT id, name FROM watchlist WHERE user_id = ? ORDER BY name ASC", session["user_id"])
    current_price = {}
    for stock in coins_all:
        fin = coin(stock["id"])
        current_price[stock["id"]] = float(fin["current_price"])
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Load symbol from user input and store in captial case 
        id = request.form.get("id").lower().strip()
        
        # Declare message variable as None for default        
        message = None

        # Ensure symbol is not empty
        if not id:
            message = "FIELD EMPTY"
            return render_template("watchlist_coin.html",coins_all = coins_all, current_price = current_price, wallet = wallet, apology = message )

        # Get info of id
        find = coin(id)

        # Give user message if the id is invalid.
        if find is None:
            message = "ENTER VALID CRYPTO ID"
            return render_template("watchlist_coin.html",coins_all = coins_all, current_price = current_price, wallet = wallet, apology = message )

        # Query portfolio table and store id in variable.
        port = crypto_db.execute("SELECT id FROM watchlist WHERE user_id = ?", session["user_id"])
        existing_id = {row["id"] for row in port}

        # Insert info about symbol if it does not already exist.
        if id not in existing_id:
            crypto_db.execute("INSERT INTO watchlist (user_id, id, name) VALUES (?,?,?)", session["user_id"], find["id"], find["name"])
        # Shows message if it already exist.
        if id in existing_id:
            message = "ALREADY EXIST IN WATCHLIST"
            return render_template("watchlist_coin.html",coins_all = coins_all, current_price = current_price, wallet = wallet, apology = message )
    
    # Query watchlist from table.
    coins_all = crypto_db.execute("SELECT id, name FROM watchlist WHERE user_id = ? ORDER BY name ASC", session["user_id"])
    current_price = {}
    for stock in coins_all:
        fin = coin(stock["id"])
        current_price[stock["id"]] = float(fin["current_price"])
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("watchlist_coin.html",coins_all = coins_all, current_price = current_price, wallet = wallet)


@app.route("/watchlist_nasdaq", methods=["GET", "POST"])
@login_required
def watchlist_nasdaq():
    # Load wallet from users table.
    wallet = users_db.execute("SELECT nasdaq_cash FROM users WHERE id = ?", session["user_id"])
    wallet = wallet[0]["nasdaq_cash"]
    
    # Load watchlist from table
    stocks_all = nasdaq_db.execute("SELECT symbol, name FROM watchlist WHERE user_id = ? ORDER BY name ASC", session["user_id"])
    current_price = {}
    for stock in stocks_all:
        fin = lookup(stock["symbol"])
        current_price[stock["symbol"]] = float(fin["price"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Load symbol from user input and store in captial case 
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
    
        # Declare message variable as None for default
        message = None
        
        # Ensure symbol is not empty
        if not symbol:
            message = "FIELD EMPTY"
            return render_template("watchlist_nasdaq.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )
        
        # Get info of symbol
        find = lookup(symbol)

        # Give user message if the symbol is invalid.
        if find is None:
            message = "ENTER VALID STOCK SYMBOL"
            return render_template("watchlist_nasdaq.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )

        # Query portfolio table and store symbols in variable.
        port = nasdaq_db.execute("SELECT symbol FROM watchlist WHERE user_id = ?", session["user_id"])
        existing_symbols = {row["symbol"] for row in port}

        # Insert info about symbol if it does not already exist.
        if symbol not in existing_symbols:
            nasdaq_db.execute("INSERT INTO watchlist (user_id, symbol, name) VALUES (?,?,?)", session["user_id"], find["symbol"], find["name"])
        # Shows message if it already exist.
        if symbol in existing_symbols:
            message = "ALREADY EXIST IN WATCHLIST"
            return render_template("watchlist_nasdaq.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet, apology = message )
    
    # Query watchlist from table. 
    stocks_all = nasdaq_db.execute("SELECT symbol, name FROM watchlist WHERE user_id = ? ORDER BY name ASC", session["user_id"])
    current_price = {}
    for stock in stocks_all:
        fin = lookup(stock["symbol"])
        current_price[stock["symbol"]] = float(fin["price"])
    
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("watchlist_nasdaq.html",stocks_all = stocks_all, current_price = current_price, wallet = wallet)
        

