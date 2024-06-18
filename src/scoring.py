from pprint import pprint
from datetime import datetime, timedelta
import copy
import statistics
import json

from tqdm.auto import tqdm
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .date_tools import days_ago, days_from_date
from .tradertrack import TraderTracker
from .stockmarket import StockHistory
from .util import write_json
from .models.models import model_predict
from .stats import normalize

def load_json_metrics():
    file_path = "./data/training_data/trading_metrics.json"
    with open(file_path, 'r') as file:
        data = json.load(file)
        
    df = pd.DataFrame(data['scoring_metrics'])
    stock_history = StockHistory(start_date="2012-01-01", end_date=datetime.now().date().strftime("%Y-%m-%d"))
    deltas = []
    
    for i,row in tqdm(df.iterrows(), total=len(df)):
        date = row['date']
        future_date = days_from_date(date_str=date, days=365)
        current_price = stock_history.price(ticker=row['ticker'], date_str=date)
        future_price = stock_history.price(ticker=row['ticker'], date_str=future_date)
        if future_price and current_price:
            price_change = future_price / current_price
            price_change = round(price_change, 2)
            deltas.append(price_change)
        else:
            deltas.append(None)

    df['price_change'] = deltas
    # Remove any rows that do not have price_change
    df = df.dropna(subset=['price_change']).reset_index(drop=True)
    df.to_csv('./data/disclosures/stock_metrics.csv', index=False)
    return df

def calculate_score(disclosure: dict):
    """
    This function evaluates the score of a stock based on the following factors that are provided in the disclosure:

    purchase_volume: the normalized volume of the stock that was purchased
    purchase_speculation: the normalized speculation score of the stock that was purchased. The speculation score is based on the moneyness of the option and the sentiment of the transaction.
    purchase_count: the normalized count (number of times) shares of the stock was purchased
    purchase_count_individual: the normalized count of individuals that purchased the stock
    purchase_days_ago: the normalized days ago that the stock was purchased (float value randing 0-1, higher score for more recent purchases)
    purchase_confidence: the confidence level of the purchase (this is based on the trader's historical performance when they purchased stocks in the past, the higher the confidence means that when the trader buys a stock it is more likely to go up in value)
    sale_volume: the normalized volume of the stock that was sold
    sale_speculation: the normalized speculation score of the stock that was sold. The speculation score is based on the moneyness of the option and the sentiment of the transaction.
    sale_count: the normalized count (number of times) shares of the stock was sold
    sale_count_individual: the normalized count of individuals that sold the stock
    sale_days_ago: the normalized days ago that the stock was sold (float value randing 0-1, higher score for more recent sales)
    sale_confidence: the confidence level of the sale (this is based on the trader's historical performance when they sold stocks in the past, the higher the sell score for a trader means when they sell a stock it is more likely to go down in value)

    Note: The purchase and sale scores are calculated separately and then the net score is calculated by subtracting the sale score from the purchase score.

    """
    weights = {
        "adjusted_purchase_volume": 2,
        "purchase_speculation": 1,
        "purchase_count": 1,
        "purchase_count_individual": 1,
        "purchase_days_ago": 1,
        "purchase_confidence": 1,
        "adjusted_sale_volume": 2,
        "sale_speculation": 1,
        "sale_count": 1,
        "sale_count_individual": 1,
        "sale_days_ago": 1,
        "sale_confidence": 1
    }
    pprint(disclosure, '\n')

    purchase_keys = ["adjusted_purchase_volume", "purchase_speculation", "purchase_count", "purchase_count_individual"]
    sale_keys = ["adjusted_sale_volume", "sale_speculation", "sale_count", "sale_count_individual"]

    purchase_values = [disclosure[key]*weights[key] for key in purchase_keys if disclosure[key] is not None]
    sale_values = [disclosure[key]*weights[key] for key in sale_keys if disclosure[key] is not None]

    # Calculate purchase score indicating how much the stock was bought. 
    purchase_score = sum(purchase_values) if purchase_values else 0
    if disclosure["purchase_days_ago"]:
        # Adds time decay to the score (more recent purchases are weighted higher)
        purchase_score = purchase_score * disclosure["purchase_days_ago"]

    # Calculate purchase score indicating how much the stock was sold. 
    sale_score = sum(sale_values) if sale_values else 0
    if disclosure["sale_days_ago"]:
        # Adds time decay to the score (more recent sales are weighted higher)
        sale_score = sale_score * disclosure["sale_days_ago"] 

    # Multiply the purchase and sale scores by the confidence levels.
    purchase_score = purchase_score * disclosure['purchase_confidence']
    sale_score = sale_score * disclosure['sale_confidence']

    # Calculate the net score by subtracting the sale score from the purchase score.
    score = purchase_score - sale_score
    return round(score, 2)

def option_moneyness(stock_price: float, strike_price: float, option_type: str) -> str:
    """Determine the moneyness of an option based on the stock price and strike price.
    Moneynees is a term used to describe the relationship between the stock price and the 
    strike price of an option. Enums: ITM (In The Money), ATM (At The Money), OTM (Out of The Money)

    Args:
        stock_price (float): The price of the stock when the option was transacted.
        strike_price (float): The strike price of the option.
        option_type (str): The type of option. Enums: 'call', 'put'

    Returns:
        str: The moneyness of the option. Enums: 'ITM', 'ATM', 'OTM'
    """
    price_ratio = strike_price / stock_price
    if price_ratio == 1.0:
        return "ATM"
    if price_ratio < 1.0:
        return "ITM" if option_type == 'call' else "OTM"
    if price_ratio > 1.0:
        return "OTM" if option_type == 'call' else "ITM"

def option_sentiment(stock_price:float, strike_price:float, option_type:str, transaction:str) -> int:
    """
    Determine the sentiment of an option transaction based on the stock price, 
    strike price, option type, and transaction type.
    - Positive score indicates bullish sentiment 
    - Negative score indicates bearish sentiment

    Args:
        stock_price (float): The price of the stock when the option was transacted.
        strike_price (float): The strike price of the option.
        option_type (str): The type of option. Enums: 'call', 'put'
        transaction (str): The type of transaction. Enums: 'purchase', 'sale'

    Returns:
        int: Score indicating the sentiment of the option transaction. 
    """
    sentiment_map = {
        "call": {
            "purchase": {"ITM": 25, "ATM": 50, "OTM": 100},
            "sale": {"ITM": -25, "ATM": -10, "OTM": -10}
        },
        "put": {
            "purchase": {"ITM": -25, "ATM": -50, "OTM": -100},
            "sale": {"ITM": 10, "ATM": 25, "OTM": 25}
        }
    }
    moneyness = option_moneyness(stock_price, strike_price, option_type)
    sentiment = sentiment_map[option_type][transaction][moneyness]
    return sentiment

def full_name(disclosure):
    return f"{disclosure['first_name']} {disclosure['last_name']}"

def normalize_asset_values(disclosures: list[dict]) -> list[dict]:
    """Normalize the asset values in the disclosures list on an individual senator basis.

    Args:
        disclosures (list[dict]): List of parsed disclosure records
    Returns:
        list[dict]: List of discourse records with normalized asset values based on individual senator's spending.
    """
    # Get the list of unique congress member names in the disclosures
    senators = [full_name(disclosure) for disclosure in disclosures]
    senators = list(set(senators))

    for senator in senators:
        # Get disclosures for the individual congress member
        individual_disclosures = [disclosure for disclosure in disclosures if full_name(disclosure) == senator]
        # Get the approximate asset values for the senator's disclosures based on the average of the low and high values.
        asset_values = [((disclosure['asset_value_low'] + disclosure['asset_value_high']) / 2) for disclosure in individual_disclosures]

        # Get the min and max asset values for the senator
        if asset_values:
            min_val = min(asset_values)
            max_val = max(asset_values)
        else:
            min_val = 0
            max_val = 0

        # Normalize the asset values for the senator using min-max normalization
        for i, disclosure in enumerate(disclosures):
            if full_name(disclosure) == senator:
                if min_val == max_val:
                    # If the senator always spends the same amount, set the adjusted value to 1
                    disclosures[i]['adjusted_value'] = 1
                else:
                    # Calculate the normalized asset value
                    approx_value = (disclosure['asset_value_low'] + disclosure['asset_value_high']) / 2
                    normalized_value = (approx_value - min_val) / (max_val - min_val)
                    # Add 1 to the normalized value so the value is between 1 and 2
                    normalized_value += 1
                    disclosures[i]['adjusted_value'] = normalized_value

    return disclosures

class AssetTracker:
    """The AssetTracker class is used to analyze the performance of congress members in the stock market.
    """
    def __init__(self):
        self.stock_history = StockHistory(start_date="2012-01-01")

    def analysis(self, disclosures: list, end_date: datetime):
        """Analyze the performance of congress members in the stock market.

        Args:
            disclosures (list): List of disclosure records
            end_date (datetime): The end date for the analysis

        Returns:
            _type_: List of stock trading activity metrics.
        """

        print("- - GETTING TRADER PERFORMANCE - -")
        # Evaluate the performance of each congress member in the stock market prior to end_date.
        test_disclosures = []
        for disclosure in disclosures:
            # Filter out disclosures that are not within the time window.
            transaction_date = datetime.strptime(disclosure['transaction_date'], "%Y-%m-%d")
            if transaction_date <= end_date:
                test_disclosures.append(disclosure)

        trade_tracker = TraderTracker(disclosures=test_disclosures, stock_history=self.stock_history)
        trade_tracker.show_results()
        self.stock_history = trade_tracker.stock_history
        print("- - DONE - -\n")

        # Normalize the asset values in the disclosures list based on individual senator's spending.
        disclosures = normalize_asset_values(disclosures=test_disclosures)

        # Filter out disclosures that are not within the time window.
        start_date = end_date - timedelta(days=120)
        period_disclosures = []
        for disclosure in disclosures:
            transaction_date = datetime.strptime(disclosure['transaction_date'], "%Y-%m-%d")
            if start_date <= transaction_date <= end_date:
                period_disclosures.append(disclosure)

        # Initialize the metrics tracker for each individual stock that was transacted within period.
        tracker = {}
        stocks = list(set([disclosure['ticker'] for disclosure in disclosures]))
        for stock in stocks:
            tracker[stock] = {
                'ticker': stock,
                'adjusted_purchase_volume': 0,
                'estimated_purchase_volume': 0,
                'purchase_speculation': 0,
                'purchase_count': 0,
                'purchase_count_individual': 0,
                'purchase_days_ago': [],
                'purchase_owner': [],
                'purchase_confidence': [],
                'adjusted_sale_volume': 0,
                'estimated_sale_volume': 0,
                'sale_speculation': 0,
                'sale_count': 0,
                'sale_count_individual': 0,
                'sale_days_ago': [],
                'sale_owner': [],
                'sale_confidence': [],
                'date': end_date.strftime("%Y-%m-%d")
            }

        # Calculate trading metrics for each stock within trading window.
        for disclosure in disclosures:
            # Skip disclosure if it is not within the time window or if it is not a stock / option.
            transaction_date = datetime.strptime(disclosure['transaction_date'], "%Y-%m-%d")
            valid_date = (start_date <= transaction_date <= end_date)
            if (valid_date == False) or (disclosure['asset_code'] not in ["ST", "OP"]) or (disclosure["option_type"] == 'short'):
                continue

            # Estimate the transaction volume.
            owner = f"{disclosure['first_name']} {disclosure['last_name']}"

            # Retrieve the trader's individual stock trading performance.
            owner_confidence = trade_tracker.trader_performance(name=owner)

            # Calculate the estimated volume of the transaction.
            estimated_volume = (disclosure['asset_value_high'] + disclosure['asset_value_low']) / 2
            estimated_volume = round(estimated_volume, 2)

            # Get the number of days ago the transaction occurred.
            transaction_date = disclosure['transaction_date']
            transaction_days_ago = days_ago(transaction_date, date_format='%Y-%m-%d') - (datetime.now() - end_date).days

            # Process record if trader's asset is a stock.
            if disclosure['asset_code'] == "ST":
                if disclosure['transaction'] == "purchase":
                    tracker[disclosure['ticker']]['adjusted_purchase_volume'] += disclosure['adjusted_value']
                    tracker[disclosure['ticker']]['estimated_purchase_volume'] += estimated_volume
                    tracker[disclosure['ticker']]['purchase_count'] += 1
                    tracker[disclosure['ticker']]['purchase_owner'].append(owner)
                    tracker[disclosure['ticker']]['purchase_days_ago'].append(transaction_days_ago)
                    if owner_confidence:
                        tracker[disclosure['ticker']]['purchase_confidence'].append(owner_confidence['purchase'])
                else:
                    tracker[disclosure['ticker']]['adjusted_sale_volume'] += disclosure['adjusted_value']
                    tracker[disclosure['ticker']]['estimated_sale_volume'] += estimated_volume
                    tracker[disclosure['ticker']]['sale_count'] += 1
                    tracker[disclosure['ticker']]['sale_owner'].append(owner)
                    tracker[disclosure['ticker']]['sale_days_ago'].append(transaction_days_ago)
                    if owner_confidence:
                        tracker[disclosure['ticker']]['sale_confidence'].append(owner_confidence['sale'])
                    
            # Process record if trader's asset is a stock option.
            elif disclosure['asset_code'] == "OP":
                stock_price = disclosure['stock_price']
                strike_price = disclosure['strike_price']
                option_type = disclosure['option_type']
                speculation_score = option_sentiment(stock_price, strike_price, option_type, disclosure['transaction'])

                if speculation_score < 0:
                    # Owner is betting against the stock price falling
                    tracker[disclosure['ticker']]['adjusted_sale_volume'] += disclosure['adjusted_value']
                    tracker[disclosure['ticker']]['estimated_sale_volume'] += estimated_volume
                    tracker[disclosure['ticker']]['sale_count'] += 1
                    tracker[disclosure['ticker']]['sale_speculation'] += abs(speculation_score)
                    tracker[disclosure['ticker']]['sale_days_ago'].append(transaction_days_ago)
                    if owner_confidence:
                        tracker[disclosure['ticker']]['sale_confidence'].append(owner_confidence['sale'])
                else:
                    # Owner is betting on the stock price growing
                    tracker[disclosure['ticker']]['adjusted_purchase_volume'] += disclosure['adjusted_value']
                    tracker[disclosure['ticker']]['estimated_purchase_volume'] += estimated_volume
                    tracker[disclosure['ticker']]['purchase_count'] += 1
                    tracker[disclosure['ticker']]['purchase_speculation'] += abs(speculation_score)
                    tracker[disclosure['ticker']]['purchase_days_ago'].append(transaction_days_ago)
                    if owner_confidence:
                        tracker[disclosure['ticker']]['purchase_confidence'].append(owner_confidence['purchase'])
        

        # Process tracker data.
        results = list(tracker.values())
        for i, result in enumerate(results):
            if result['purchase_days_ago']:
                # Get average number of days ago the stock was purchased
                purchase_days_ago = statistics.mean(result['purchase_days_ago'])
                results[i]['purchase_days_ago'] = round(purchase_days_ago, 2)
            else:
                results[i]['purchase_days_ago'] = None

            
            if result['sale_days_ago']:
                # Get the average days ago that the stock was sold
                sale_days_ago = statistics.mean(result['sale_days_ago'])
                results[i]['sale_days_ago'] = round(sale_days_ago, 2)
            else:
                results[i]['sale_days_ago'] = None

            # Set purchase and sale confidence levels
            results[i]['purchase_confidence'] = max(results[i]['purchase_confidence']) if results[i]['purchase_confidence'] else 0
            results[i]['sale_confidence'] = max(results[i]['sale_confidence']) if results[i]['sale_confidence'] else 0

            # Identify congress people who transacted the stock / option asset.
            results[i]['purchase_owner'] = list(set(result['purchase_owner']))
            results[i]['sale_owner'] = list(set(result['sale_owner']))
            
            # Calculate total number of individuals that transacted the stock / option asset.
            results[i]['purchase_count_individual'] = len(results[i]['purchase_owner'])
            results[i]['sale_count_individual'] = len(results[i]['sale_owner'])
            results[i]['volume_net'] = results[i]['estimated_purchase_volume'] - results[i]['estimated_sale_volume'] 

        final_results = [result for result in results if result['purchase_owner'] or result['sale_owner']]

        return final_results

def rank_stocks(disclosures:list, end_date:datetime, mode:str='run', refresh_train: bool=False):
    asset_tracker = AssetTracker()

    if refresh_train:
        trading_metrics = []
        # Collect data for training the model
        date = datetime(2013, 1, 1)
        while date < (datetime.now() - timedelta(days=372)):
            print(f"Collecting data for {end_date.strftime('%Y-%m-%d')}")
            results = asset_tracker.analysis(copy.deepcopy(disclosures), date)

            # Normalize data to weigh different factors evenly.
            normalized_data = normalize(disclosures=copy.deepcopy(results))
            for i, _ in enumerate(normalized_data):
                results[i]['score'] = calculate_score(disclosure=normalized_data[i])

            trading_metrics.extend(results)
            date = date + timedelta(days=60)
        
        df = pd.DataFrame(trading_metrics)
        stock_history = asset_tracker.stock_history
        deltas = []
        
        # Add price deltas to the dataframe
        for i,row in tqdm(df.iterrows(), total=len(df)):
            date = row['date']
            future_date = days_from_date(date_str=date, days=365)
            current_price = stock_history.price(ticker=row['ticker'], date_str=date)
            future_price = stock_history.price(ticker=row['ticker'], date_str=future_date)

            try:
                price_change = future_price / current_price
                price_change = round(price_change, 2)
                deltas.append(price_change)
            except:
                deltas.append(None)

        # Remove any None values from the deltas
        df['price_change'] = deltas
        df = df.dropna(subset=['price_change']).reset_index(drop=True)

        df['sale_days_ago'] = df['sale_days_ago'].fillna(-1)
        df['purchase_days_ago'] = df['purchase_days_ago'].fillna(-1)
        
        save_path = './data/training_data/stock_metrics.csv'
        df.to_csv(save_path, index=False)
        print(f"Data was saved to '{save_path}'.")

    if mode == 'train':
        # Load the training data and split it into features and target
        df = pd.read_csv('./data/training_data/stock_metrics.csv') 

        # df['date'] = pd.to_datetime(df['date'])
        # end_date = pd.Timestamp('2023-01-01')
        # df = df[df['date'] < end_date]

        # Define features and target
        x = df.drop(columns=['date', 'purchase_owner', 'sale_owner', 'sale_speculation', 'purchase_speculation', 'price_change'])
        y = df['price_change']

        # Split the data into training and testing sets
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

        tickers = x_test['ticker']

        x_train = x_train.drop(columns=['ticker'])
        x_test = x_test.drop(columns=['ticker'])

        # Initialize the model
        gbr = GradientBoostingRegressor(random_state=42)

        # Fit the model to the training data
        gbr.fit(x_train, y_train)

        # Make predictions on the test set
        y_pred = gbr.predict(x_test)

        # Calculate Mean Squared Error
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        print(f"Mean Absolute Error: {mae}")
        print(f"Mean Squared Error: {mse}")

        predictions = x_test
        predictions['ticker'] = tickers
        predictions['prediction_growth'] = y_pred
        predictions['actual_growth'] = y_test

        predictions = predictions.sort_values(by='prediction_growth', ascending=False)
        predictions = predictions.reset_index()

        top_ten = predictions.head(10)
        for i,item in top_ten.iterrows():
            print(f"Rank {i+1}: {item['ticker']}")
            print(f"Prediction: {round(item['prediction_growth'], 2)}")
            print(f"Actual: {item['actual_growth']}")
            print('')

        save = input(f"The MAE is {round(mae, 2)}. Do you want to save the model? (y/n): ")
        if save.strip() == 'y':
            model_path = './src/models/pretrained_models/gradient_boosting_regressor.joblib'
            joblib.dump(gbr, model_path)
            print(f"Model saved to '{model_path}'")


    elif mode == 'run':
        # Calculating trading metrics for each stock.
        results = asset_tracker.analysis(copy.deepcopy(disclosures), end_date)

        # Normalize data to weigh different factors evenly.
        normalized_data = normalize(disclosures=copy.deepcopy(results))
        for i, _ in enumerate(normalized_data):
            results[i]['score'] = calculate_score(disclosure=normalized_data[i])

        # predictions = model_predict(records=copy.deepcopy(results))

        # for i, prediction in enumerate(predictions):
        #     results[i]['prediction'] = prediction

        # Rank top stocks by score.
        top_buys = sorted(results, key=lambda x: x["score"], reverse=True)
        top_sells = sorted(results, key=lambda x: x["score"], reverse=False)

        print('- - TOP BUYS OVERALL - -')
        for stock in top_buys[:5]:
            print(f"Ticker: {stock['ticker']}")
            #print(f"Prediction: {stock['prediction']}")
            print(f"Score: {stock['score']}")
            print(f"Purchase Confidence: {stock['purchase_confidence']}")
            print(f"Purchase Volume: ${stock['estimated_purchase_volume']}")
            print(f"Sale Volume: ${stock['estimated_sale_volume']}")
            print(f"Buyers: {stock['purchase_owner']}")
            print('')
        print('')

        print('- - TOP SELLS OVERALL - -')
        for stock in top_sells[:5]:
            print(f"Ticker: {stock['ticker']}")
            #print(f"Prediction: {stock['prediction']}")
            print(f"Score: {stock['score']}")
            print(f"Sale Confidence: {stock['sale_confidence']}")
            print(f"Purchase Volume: ${stock['estimated_purchase_volume']}")
            print(f"Sale Volume: ${stock['estimated_sale_volume']}")
            print(f"Sellers: {stock['sale_owner']}")
            print('')
        print('')

        return {
            "buy": top_buys,
            "sell": top_sells
        }
