import yfinance as yf
from pprint import pprint
import traceback
from datetime import datetime, timedelta
from .date_tools import nearest_monday, get_most_recent_weekday, get_next_day, us_holidays, days_ago, days_from_date

class StockHistory:
    # The __init__ method initializes the object's attributes
    def __init__(self, start_date:str, end_date:str):
        # Expected Date Format: '%Y-%m-%d'
        self.date_format = "%Y-%m-%d"
        self.start_date = start_date
        self.end_date = end_date
        self.holidays = us_holidays()
        

        self.cache = {}
        self.ticker_map = {"FB": "META"}
        self.invalid_tickers = []

    def price(self, ticker: str, date_str: str=None):
        try:
            ticker = self.validate_ticker(ticker=ticker)
        except:
            return None

        if ticker not in self.cache.keys():
            #print(f"{ticker} has not been cached. Updating cache.")
            response = self.update_cache(ticker=ticker)
            if response == 500:
                #print(f"\nWARNING: Failed to retrieve stock data for '{ticker}'\n.")
                return None

        try:
            if not date_str:
                date_str = (datetime.now() - timedelta(days=1)).strftime(self.date_format)
            date = self.closest_weekday(date_str=date_str)
            price = self.cache[ticker][date]["Close"]
            price = round(price, 2)
            return price
        except Exception as e:
            #print(f"\nWARNING: Error retrieving price for '{ticker}' on '{date_str}'\n.")
            return None
        
    def update_cache(self, ticker: str):
        try:
            ticker = self.validate_ticker(ticker=ticker)
        except:
            return None

        ticker_history = self.stock_history(ticker=ticker)
        if not ticker_history:
            return 500
        ticker_data = {}
        for record in ticker_history:
            date = record["Date"]
            ticker_data[date] = record
        self.cache[ticker] = ticker_data
        
        #print(f"Cache updated with {ticker} data.")
        return 200

    def stock_history(self, ticker: str, start_date: str = None, end_date: str = None):
        try:
            ticker = self.validate_ticker(ticker=ticker)
        except:
            return None

        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date

        stock = yf.Ticker(ticker)

        try:
            hist = stock.history(start=start_date, end=end_date)
            hist = hist.reset_index()
            hist["Date"] = hist["Date"].dt.strftime(self.date_format)
            hist = hist.to_dict(orient="records")
        except Exception as e:
            #print(e)
            print(f"The ticker '{ticker}' is invalid: removing from cache")
            self.invalid_tickers.append(ticker)
            return None
        return hist

    def closest_weekday(self, date_str=None):
        # Parse the input date string
        if date_str:
            date_obj = datetime.strptime(date_str, self.date_format).date()
        else:
            # Get yesterday's closing price
            date_obj = datetime.now().date()

        # Get the weekday (0=Monday, 6=Sunday)
        weekday = date_obj.weekday()

        # Check if the date falls on a Saturday (5) or Sunday (6)
        if weekday == 5:
            # Adjust Saturday to last Friday
            adjusted_date = date_obj - timedelta(days=1)
        elif weekday == 6:
            # Adjust Sunday to last Friday
            adjusted_date = date_obj - timedelta(days=2)
        else:
            adjusted_date = date_obj

        if adjusted_date in self.holidays:
            #print(f"Date '{adjusted_date}' is a US Holiday.\n")
            weekday = adjusted_date.weekday()
            if weekday == 0:
                # if weekday is a monday and date is on a holiday
                adjusted_date = adjusted_date + timedelta(days=-3)
            else:
                adjusted_date = adjusted_date + timedelta(days=-1)

        # Return the adjusted date string in the same format
        return adjusted_date.strftime(self.date_format)

    def validate_ticker(self, ticker: str):
        ticker = ticker.upper()
        if ticker in self.invalid_tickers:
            raise Exception(f"The ticker '{ticker}' is not publicly listed.")

        if ticker in self.ticker_map.keys():
            ticker = self.ticker_map[ticker]
        return ticker
    


