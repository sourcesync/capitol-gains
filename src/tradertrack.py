from .stockmarket import StockHistory
from .date_tools import days_from_date, days_ago
from datetime import datetime, timedelta
from tqdm.auto import tqdm
from IPython.display import clear_output

def calculate_significance(samples: list) -> float:
    significance = len(samples) / 10
    if significance > 1:
        significance = 1
    return significance


class Trader:
    def __init__(self, name: str):
        self.name = name
        self.purchase_gains_1yr = []
        self.sale_gains_1yr = []
        self.purchase_score = 0
        self.sale_score = 0


class TraderTracker:
    def __init__(self, disclosures, stock_history=None):
        self.disclosures = disclosures
        if stock_history:
            self.stock_history = stock_history
        else:
            self.stock_history = StockHistory(start_date="2012-01-01", end_date=datetime.now().date().strftime("%Y-%m-%d"))
        self.tracker = {}
        self.initialize_tracker()
        self.calculate_performance_history()

    def initialize_tracker(self):
        traders = [self.full_name(disclosure) for disclosure in self.disclosures]
        for trader in traders:
            self.tracker[trader] = Trader(name=trader)

    def trader_performance(self, name: str):
        try:
            purchase = self.tracker[name].purchase_score
            sale = self.tracker[name].sale_score
        except KeyError:
            print(f"Warning: Could not get confidence scores for {name}")
            return None

        performance = {
            "purchase": purchase,
            "sale": sale
        }
        return performance

    def calculate_performance_history(self):
        dates = [datetime.strptime(disclosure['transaction_date'], '%Y-%m-%d') for disclosure in self.disclosures]
        year = max(dates).year
        congress_members = list(self.tracker.keys())
        for i,trader in enumerate(congress_members):
            trader_disclosures = [disclosure for disclosure in self.disclosures if self.full_name(disclosure) == trader]
            print(f"\n{year} Trader ({i+1}/{len(congress_members)}): {trader}")
            for disclosure in tqdm(trader_disclosures):
                future_price = self.get_future_gains(disclosure=disclosure)
                gains = future_price['gains']
                if not gains:
                    continue

                if disclosure['transaction'] == 'purchase' and disclosure['asset_code'] == 'ST':
                    self.tracker[trader].purchase_gains_1yr.append(gains)
                elif disclosure['transaction'] == 'sale' and disclosure['asset_code'] == 'ST':
                    gains = 1 - gains
                    self.tracker[trader].sale_gains_1yr.append(gains)
                elif disclosure['transaction'] == 'purchase' and disclosure['asset_code'] == 'OP':
                    if disclosure['option_type'] == 'put':
                        gains = 1 - gains
                        self.tracker[trader].sale_gains_1yr.append(gains)
                    elif disclosure['option_type'] == 'call':
                        self.tracker[trader].purchase_gains_1yr.append(gains)
                elif disclosure['transaction'] == 'sale' and disclosure['asset_code'] == 'OP':
                    if disclosure['option_type'] == 'put':
                        self.tracker[trader].purchase_gains_1yr.append(gains)
                    elif disclosure['option_type'] == 'call':
                        gains = 1 - gains
                        self.tracker[trader].sale_gains_1yr.append(gains)

            purchases = self.tracker[trader].purchase_gains_1yr
            sales = self.tracker[trader].sale_gains_1yr
            if purchases:
                purchase_score = sum(purchases) / len(purchases)
                significance = calculate_significance(samples=purchases)
                self.tracker[trader].purchase_score = purchase_score * significance
            else:
                self.tracker[trader].purchase_score = 0
            if sales:
                sale_score = sum(sales) / len(sales)
                significance = calculate_significance(samples=sales)
                self.tracker[trader].sale_score = sale_score * significance
            else:
                self.tracker[trader].sale_score = 0

            clear_output()

    def full_name(self, disclosure):
        first_name = disclosure['first_name']
        last_name = disclosure['last_name']
        full_name = f"{first_name} {last_name}"
        return full_name

    def get_future_gains(self, disclosure, days_in_future=360):
        num_days_ago = days_ago(date_str=disclosure['transaction_date'], date_format='%Y-%m-%d')
        if num_days_ago < days_in_future:
            return {
                "gains": None,
                "future_date": None,
                "future_price": None
            }

        future_date = days_from_date(date_str=disclosure['transaction_date'], days=days_in_future)
        future_price = self.stock_history.price(ticker=disclosure['ticker'], date_str=future_date)

        if future_price is None:
            return {
                "gains": None,
                "future_date": None,
                "future_price": None
            }

        price_delta = round((future_price / disclosure['stock_price']), 2)
        return {
            "gains": price_delta,
            "future_date": future_date,
            "future_price": future_price
        }

    def show_results(self):
        results = [self.tracker[trader] for trader in self.tracker.keys()]
        top_buyers = sorted(results, key=lambda x: x.purchase_score, reverse=True)
        top_sellers = sorted(results, key=lambda x: x.sale_score, reverse=True)

        results_str = '- - TOP BUYERS - -\n'
        for i, buyer in enumerate(top_buyers[:int(len(top_buyers) / 2)]):
            results_str += f"Rank: {i + 1}\n"
            results_str += f"Name: {buyer.name}\n"
            results_str += f"Purchase Score: {buyer.purchase_score} ({len(buyer.purchase_gains_1yr)} purchases)\n"
            results_str += f"Sale Score: {buyer.sale_score} ({len(buyer.sale_gains_1yr)} sales)\n\n"

        results_str += '- - TOP SELLERS - -\n'
        for seller in top_sellers[:int(len(top_sellers) / 2)]:
            results_str += f"Name: {seller.name}\n"
            results_str += f"Sale Score: {seller.sale_score} ({len(seller.sale_gains_1yr)} sales)\n"
            results_str += f"Purchase Score: {seller.purchase_score} ({len(seller.purchase_gains_1yr)} purchases)\n\n"

        print(results_str)


def normalize(data):
    purchase_scores = [data[key].purchase_score for key in data.keys()]
    sale_scores = [data[key].sale_score for key in data.keys()]

    min_max = {
        "purchase": {
            "min": min(purchase_scores),
            "max": max(purchase_scores)
        },
        "sale": {
            "min": min(sale_scores),
            "max": max(sale_scores)
        }
    }

    for key in data.keys():
        if data[key].purchase_score >= 0:
            score = data[key].purchase_score / min_max['purchase']['max']
            data[key].purchase_score = round(score, 2)
        else:
            score = data[key].purchase_score / min_max['purchase']['min']
            score = score * -1
            data[key].purchase_score = round(score, 2)

        if data[key].sale_score >= 0:
            score = data[key].sale_score / min_max['sale']['max']
            data[key].sale_score = round(score, 2)
        else:
            score = data[key].sale_score / min_max['sale']['min']
            score = score * -1
            data[key].sale_score = round(score, 2)

    return data

def show_delta(price_delta, disclosure, future_date, future_price):
    if disclosure['asset_code'] == 'OP' and disclosure['option_type'] in ['put', 'call']:
        print(f"Ticker: {disclosure['ticker']} ({disclosure['transaction'].upper()})")
        print(f"[OP] '{disclosure['option_type'].upper()}'")
    else:
        return
        #print('[ST] - - -')
    print(f"{disclosure['transaction_date']}: ${disclosure['stock_price']}")
    print(f"{future_date}: ${future_price}")
    print(f"Price Delta: {round(price_delta,2)}")
    print('')
