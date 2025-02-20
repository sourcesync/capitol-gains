# Capitol Gains

## Description
Capitol Gains is a a suite of tools for downloading, parsing, and analyzing US Congress stock market trades dating back to 2012. Due to the 2012 STOCK Act, members of US Congress are required by law to disclose their stock trades within 45 days of a transaction worth over $1,000. 

This data is publically available for the House of Representatives at [House of Representative Finanacial Disclosure Reports](https://disclosures-clerk.house.gov/FinancialDisclosure) and for the Senate at [US Senate Select Committee on Ethics](https://efdsearch.senate.gov/search/home/).

## Installation
1. Clone the repository to your computer.
2. Create a Python virtual environment and install dependencies from the `requirements.txt` file:
    - **Create Virtual Environment:** `python3 -m venv venv`
    - **Activate Virtual Environment:** `source venv/bin/activate`
    - **Install Python Dependencies:** `pip3 install -r requirements.txt`

## Usage
The code is broken up into a few different tools for collecting and analyzing the Congress stock trading data:
- **house_crawler.py:**
    - This script is used to download and parse the most up to date and available stock trades from the US House of Representatives. The data is saved in json format inside of the './data/parsed_disclosures/' directory as 'house.json'.
    - **Run:** `python3 senate_crawler.py`
        - Data is saved to ./data/parsed_disclosures/house.json
- **senate_crawler.py:**
    - This script is used to download and parse the most up to date and available stock trades from the US Senate. The data is saved in json format inside of the './data/parsed_disclosures/' directory as 'senate.json'.
    - **Run:** `python3 senate_crawler.py`
        - Data is saved to ./data/parsed_disclosures/senate.json
- **src/scoring.py:**
    -  This script has tools for ranking stocks based on congress stock trades / transaction metrics. 
- **src/tradertrack.py:**
    - This script has tools for tracking the trading performance of individual members of congress.
    - Specifically, this tool is used to track the average 1-year return on investment by individual members of congress based on their trading history.
- **src/stockmarket.py:**
    - This script has tools for retrieving historical stock prices.
- **xg_boost.ipynb:**
    - This notebook has code for running and testing the XGBoost and hard-coded scoring algorithm on test data.

