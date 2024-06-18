from pprint import pprint
import time
import requests
from bs4 import BeautifulSoup
import copy
import re

from src.util import load_json, write_json
from src.stockmarket import StockHistory
from src.date_tools import format_date, days_ago, sort_by_date

# Start a session to automatically handle cookies
session = requests.Session()

# Setup the headers as per the API requirements
headers = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Host": "efdsearch.senate.gov",
    "Origin": "https://efdsearch.senate.gov",
    "Referer": "https://efdsearch.senate.gov/search/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Modxe": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "X-CSRFToken": "",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "X-Requested-With": "XMLHttpRequest",
}

def option_details(asset_name: str):
    # Define the regex pattern to match the option type, strike price, and expiration date
    pattern = r"Option Type: (\w+).*?Strike price:\$(\d+\.\d{2}).*?Expires:(\d{2}/\d{2}/\d{4})"
    # Search for the pattern in the input string
    match = re.search(pattern, asset_name)
    if match:
        # Extract the option type, strike price, and expiration date
        option_type = match.group(1).lower()
        strike_price = float(match.group(2))
        expiration_date = format_date(date_str=match.group(3))

        details = {
            "option_type": option_type,
            "option_exp_date": expiration_date,
            "strike_price": strike_price
        }
        return details
    else:
        return None
    
def get_doc_id(doc_url:str):
    segments = doc_url.split('/')
    segments = [item for item in segments if item]
    doc_id = segments[-1]
    return doc_id

def update_token():
    global session
    global headers
    # Make the initial GET request
    get_url = "https://efdsearch.senate.gov/search/"
    response = session.get(get_url, headers=headers)

    # Parse CSRF token using BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    csrf_token = soup.find("input", {"name": "csrfmiddlewaretoken"}).get("value", "")
    headers["X-CSRFToken"] = csrf_token
    return csrf_token

def agree_terms():
    global headers
    global session

    update_token()
    url = "https://efdsearch.senate.gov/search/"
    response = session.get(url, headers=headers)
    print(response.status_code)
    html_content = response.text
    # print(html_content, '\n')

    soup = BeautifulSoup(html_content, "html.parser")
    csrf_token = soup.find("input", attrs={"name": "csrfmiddlewaretoken"})["value"]
    form_data = {"prohibition_agreement": "1", "csrfmiddlewaretoken": csrf_token}

    print(csrf_token)
    headers["X-CSRFToken"] = csrf_token

    print("submitting token")
    response = session.post(
        "https://efdsearch.senate.gov/search/home/", data=form_data, headers=headers
    )
    print(response.status_code)
    time.sleep(2)


def search_documents():
    global session
    global headers

    start = 0
    draw = 1
    page_results = 25

    disclosure_links = []

    disclosures = load_json(path="./data/parsed_disclosures/senate.json")['disclosures']
    existing_records = [disc['doc_id'] for disc in disclosures]

    page = 1
    while True:
        payload = {
            "draw": draw,
            "columns": [
                {
                    "data": 0,
                    "name": "",
                    "searchable": True,
                    "orderable": True,
                    "search": {"value": "", "regex": False},
                },
                # Add other columns as necessary
            ],
            "order": [{"column": 1, "dir": "asc"}, {"column": 0, "dir": "asc"}],
            "start": start,
            "length": page_results,
            "search": {"value": "", "regex": False},
            "report_types": "[11]",
            "filer_types": "[1]",
            "submitted_start_date": "01/01/2012 00:00:00",
            "submitted_end_date": "",
            "candidate_state": "",
            "senator_state": "",
            "office_id": "",
            "first_name": "",
            "last_name": "",
        }

        post_url = "https://efdsearch.senate.gov/search/report/data/"
        response = session.post(post_url, headers=headers, data=payload)

        print(f"Parsing Results Page: {page}, Status Code: {response.status_code}")
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        json_data = response.json()

        data = json_data["data"]
        max_results = json_data["recordsTotal"]

        for row in data:
            a_tag = row[3]
            soup = BeautifulSoup(a_tag, "html.parser")
            endpoint = soup.find("a")["href"]
            disclosure_url = f"https://efdsearch.senate.gov{endpoint}"
            notification_date = format_date(date_str=row[4])
            
            
            doc_id = get_doc_id(doc_url=endpoint)
            if doc_id in existing_records:
                # Skip record if it has already been collected and parsed.
                continue
            
            row_data = {
                "first_name": row[0],
                "last_name": row[1],
                "doc_id": doc_id,
                "url": disclosure_url,
                "notification_date": notification_date
            }

            disclosure_links.append(row_data)

        start += page_results
        draw += 1

        if len(disclosure_links) >= max_results or len(data) == 0:
            break

        time.sleep(2)

    return disclosure_links


def get_financial_data(disclosure):
    global headers
    global session

    response = session.get(disclosure["url"], headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # Attempt to find the table
    table = soup.find("table", class_="table-striped")

    if table:
        # Extract the column headers
        col_names = [th.get_text(strip=True) for th in table.find_all("th")]

        # Extract rows
        data = []
        for row in table.find("tbody").find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            record = dict(zip(col_names, cells))
            record["days_ago"] = days_ago(date_str=record["Transaction Date"])
            record["first_name"] = disclosure["first_name"]
            record["last_name"] = disclosure["last_name"]
            record["doc_id"] = disclosure["doc_id"]
            record["notification_date"] = disclosure["notification_date"]
            del record["#"]
            data.append(record)

        return data
    else:
        return None


def get_transaction_amount(amount):
    amounts = amount.split("-")
    for i, _ in enumerate(amounts):
        amounts[i] = amounts[i].replace(",", "")
        amounts[i] = amounts[i].replace("$", "")
        amounts[i] = amounts[i].strip()

    low = amounts[0]
    high = amounts[1]
    return int(low), int(high)



if __name__ == "__main__":
    agree_terms()
    update_token()
    disclosure_links = search_documents()

    existing_disclosures = load_json(path="./data/parsed_disclosures/senate.json")["disclosures"]

    disclosures = []
    for i, _ in enumerate(disclosure_links):
        
        try:
            data = get_financial_data(disclosure=disclosure_links[i])
            disclosures.extend(data)
            print(f"Parsing Document: {i+1}/{len(disclosure_links)}")
        except:
            name = f"{disclosure_links[i]['first_name']} {disclosure_links[i]['last_name']}"
            url = disclosure_links[i]['url']
            print(f"\nWARNING: {i+1}/{len(disclosure_links)} Failed to parse document:\nName:{name}\nURL: {url}\n")
            pass

    print(f"{len(disclosures)} disclosures collected.")

    stock_tracker = StockHistory(start_date="2012-01-01")
    senate_trades = []
    for i, _ in enumerate(disclosures):
        print(f"Processing Disclosure: {i}/{len(disclosures)}")
        if "Stock" not in disclosures[i]["Asset Type"]:
            continue

        if len(disclosures[i]["Asset Name"]) > 20:
            asset_name = disclosures[i]["Asset Name"][:20]
        else:
            asset_name = disclosures[i]["Asset Name"]

        low, high = get_transaction_amount(amount=disclosures[i]["Amount"])
        disclosures[i]["transaction_amount_low"] = low
        disclosures[i]["transaction_amount_high"] = high

        ticker = disclosures[i]["Ticker"]
        if not ticker or "--" in ticker:
            continue

        try:
            transaction_date = disclosures[i]["Transaction Date"]
            transaction_date = format_date(date_str=transaction_date)
            price = stock_tracker.price(
                ticker=disclosures[i]["Ticker"], date_str=transaction_date
            )
            if not price:
                print(
                    f"\nNo price data available for Ticker.\nTicker'{disclosures[i]['Ticker']}'\nDate: {transaction_date}\n\n"
                )
                continue
            else:
                disclosures[i]["stock_price"] = price
                senate_trades.append(disclosures[i])
        except Exception as e:
            print(
                f"\nERROR: Retrieving ticker '{disclosures[i]['Ticker']}' price data."
            )
            print(e, "\n")

    disclosures = []
    for disclosure in senate_trades:
        if 'sale' in disclosure['Type'].lower():
            transaction_type = 'sale'
        else:
            transaction_type = 'purchase'

        if disclosure['Asset Type'] == 'Stock':
            asset_code = 'ST'
            options_data = {
                "option_type": None,
                "option_exp_date": None,
                "strike_price": None,
            }
            option_activity = None
        elif disclosure['Asset Type'] == 'Stock Option':
            asset_code = 'OP'
            options_data = option_details(asset_name=disclosure['Asset Name'])
            option_activity = transaction_type
            if not options_data:
                # Do not record options data if details are not found.
                continue

        if disclosure['Comment'] == '--' or disclosure['Comment'] is None:
            description = None
        else:
            description = disclosure['Comment']

        record = {
            "asset_name": disclosure['Asset Name'],
            "transaction": transaction_type,
            "share_count": None,
            "options_count": None,
            "option_type": options_data["option_type"],
            "option_activity": option_activity,
            "option_exp_date": options_data["option_exp_date"],
            "strike_price": options_data["strike_price"],
            "ticker": disclosure['Ticker'],
            "transaction_date": format_date(disclosure['Transaction Date']),
            "notification_date": disclosure['notification_date'],
            "asset_value_low": disclosure['transaction_amount_low'],
            "asset_value_high": disclosure['transaction_amount_high'],
            "description": description,
            "asset_code": asset_code,
            "doc_id": disclosure["doc_id"],
            "first_name": disclosure['first_name'],
            "last_name": disclosure['last_name'],
            "asset_type": disclosure['Asset Type'],
            "stock_price": disclosure['stock_price'],
            "governing_body": "SENATE",
        }

        if record['ticker']:
            print(f'Owner: {record["first_name"]} { record["last_name"]}')
            print(f"Ticker: {record['ticker']}")
            print(f"Transaction: {record['transaction']}")
            print(f"Price: ${record['stock_price']}")
            print(f"Date: {record['transaction_date']}\n")
        disclosures.append(record)

    
    existing_disclosures.extend(disclosures)
    # sort the data from least recent to most recent.
    existing_disclosures = sort_by_date(disclosures=existing_disclosures)
    print(f"\nALERT: Successfully collected and parsed {len(disclosures)} new disclosures.")
    print(f"ALERT: The dataset now has {len(existing_disclosures)} disclosure records.\n")

    save_data = {"disclosures": existing_disclosures}
    write_json(data=save_data, path="./data/parsed_disclosures/senate.json")
    print(f"- - DATA WAS SAVED TO JSON - -\n")


