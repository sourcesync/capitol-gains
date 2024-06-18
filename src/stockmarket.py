import yfinance as yf
from pprint import pprint
import traceback
from datetime import datetime, timedelta
from bisect import bisect_left

from .date_tools import nearest_monday, get_most_recent_weekday, get_next_day, us_holidays, days_ago, days_from_date
from .logger import logger

class StockHistory:
    # The __init__ method initializes the object's attributes
    def __init__(self, start_date: str, end_date: str=None):
        # Expected Date Format: '%Y-%m-%d'
        self.date_format = "%Y-%m-%d"
        self.start_date = start_date
        if end_date is None:
            self.end_date = (datetime.now() - timedelta(days=1)).strftime(self.date_format)
        else:
            self.end_date = end_date
        self.holidays = us_holidays()

        self.cache = {}
        self.ticker_map = {"FB": "META", "BRK.B": "BRK-B", "BRKB": "BRK-B"}
        self.invalid_tickers = []

    def price(self, ticker: str, date_str: str = None):
        try:
            ticker = self.validate_ticker(ticker=ticker)
        except:
            # Skip if the ticker is invalid
            return None

        if ticker not in self.cache.keys():
            # Update the stock history cache with new ticker.
            response = self.update_cache(ticker=ticker)
            if response == 500:
                # Return None no data is available for the ticker
                return None

        try:
            if not date_str:
                # Set default date to yesterday if date is not provided.
                date_str = (datetime.now() - timedelta(days=1)).strftime(self.date_format)

            date = self.closest_weekday(date_str=date_str)
            date_obj = datetime.strptime(date, self.date_format)

            # Check if the exact date is in the cache
            if date in self.cache[ticker]:
                nearest_date = date_obj
            else:
                # Get the nearest available date for the stock price.
                nearest_date = self.find_nearest_date(self.cache[ticker].keys(), date_obj)
                if nearest_date is None:
                    logger.warning(f"WARNING: No available date within two weeks for '{ticker}' on '{date_str}'.")
                    return None

            #pprint(self.cache[ticker][nearest_date.strftime(self.date_format)])
            price = self.cache[ticker][nearest_date.strftime(self.date_format)]["Close"]
            price = round(price, 2)
            return price
        except Exception as e:
            logger.warning(f"\nWARNING: Error retrieving price for '{ticker}' on '{date_str}'.")
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

        # Sort the ticker data by date
        sorted_ticker_data = dict(sorted(ticker_data.items(), key=lambda item: datetime.strptime(item[0], self.date_format)))

        self.cache[ticker] = sorted_ticker_data
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
            logger.error(f"BAD TICKER: No data exists for '{ticker}' between dates {start_date} and {end_date}. Flagging as invalid ticker.")
            self.invalid_tickers.append(ticker)
            return None
        return hist

    def closest_weekday(self, date_str=None):
        if date_str:
            date_obj = datetime.strptime(date_str, self.date_format).date()
        else:
            date_obj = datetime.now().date()

        weekday = date_obj.weekday()

        if weekday == 5:
            adjusted_date = date_obj - timedelta(days=1)
        elif weekday == 6:
            adjusted_date = date_obj - timedelta(days=2)
        else:
            adjusted_date = date_obj

        if adjusted_date in self.holidays:
            weekday = adjusted_date.weekday()
            if weekday == 0:
                adjusted_date = adjusted_date + timedelta(days=-3)
            else:
                adjusted_date = adjusted_date + timedelta(days=-1)

        return adjusted_date.strftime(self.date_format)

    def validate_ticker(self, ticker: str):
        ticker = ticker.upper()
        if ticker in self.invalid_tickers:
            raise Exception(f"The ticker '{ticker}' is not publicly listed.")

        if ticker in self.ticker_map.keys():
            ticker = self.ticker_map[ticker]
        return ticker
        

    def find_nearest_date(self, date_keys, target_date):
        date_list = [datetime.strptime(date, self.date_format) for date in date_keys]
        pos = bisect_left(date_list, target_date)
        
        two_weeks = timedelta(weeks=2)
        
        if pos == 0:
            nearest_date = date_list[0]
        elif pos == len(date_list):
            nearest_date = date_list[-1]
        else:
            before = date_list[pos - 1]
            after = date_list[pos]
            if after - target_date < target_date - before:
                nearest_date = after
            else:
                nearest_date = before
        
        if abs(nearest_date - target_date) <= two_weeks:
            return nearest_date
        else:
            return None
