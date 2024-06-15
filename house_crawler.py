import zipfile
import io
from datetime import datetime
import time
import traceback
import os

import yfinance as yf
import xml.etree.ElementTree as ET
import requests
import pdfplumber
from pprint import pprint

from src.util import load_json, write_json, extract_json
from src.stockmarket import StockHistory
from src.ai_tools import chatgpt
from src.date_tools import sort_by_date
from src.parse_house_data import parse_house_doc
import re


asset_types = load_json(path="./data/asset_types.json")
def jsonify_disclosure(text):
    with open("./prompts/disclosures.txt", "r") as file:
        prompt = file.read()

    prompt = prompt.replace("FINANCIAL_DISCLOSURE", text)
    print("GPT: Converting text data to json...")
    response = chatgpt(prompt=prompt)
    json_data = extract_json(response)
    return json_data


def get_financial_disclosures(year):
    url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"

    # Send a GET request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Use io.BytesIO for in-memory bytes buffer
        zip_file_bytes = io.BytesIO(response.content)

        # Open the zip file
        with zipfile.ZipFile(zip_file_bytes, "r") as zip_ref:
            # Extract all the contents into the directory
            zip_ref.extractall("./data/clerk_house")
        print(f"{year} Files successfully downloaded and extracted.")
    else:
        print(f"{year} Failed to download the file. Status code:", response.status_code)

# Function to convert XML element to dictionary
def xml_to_dict(element):
    member_dict = {}
    for child in element:
        if child.text:
            member_dict[child.tag] = child.text.strip()
        else:
            # If there is no text and no sub-elements, assign an empty string
            member_dict[child.tag] = ""
    return member_dict


def check_disclosure_recorded(disclosures: list[dict], failures:list[str], doc_id: str):
    """Checks if disclosure has already been recorded

    Args:
        disclosures (list[dict]): List of disclosures
        doc_id (str): The document ID number for the disclosure to check
    """
    # Skip record if data has already been extracted.
    disclosure_exists = False
    completed_doc_ids = [disclosure["doc_id"] for disclosure in disclosures]
    completed_doc_ids.extend(failures)
    if doc_id in completed_doc_ids:
        return True
    else:
        return False


# Read XML from a file
def read_xml_file(file_path):
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Parse each member and store in a list
    members = []
    for member in root.findall("Member"):
        members.append(xml_to_dict(member))

    return members


def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text()

    return text


def check_valid_pdf(path):
    with open(path, "rb") as file:
        # Read the entire contents of the file into a string
        file_contents = file.read()

    if b"Type /Pages" in file_contents:
        return True
    else:
        return False


def get_document(year, doc_id):
    path = f"./data/documents/{doc_id}.pdf"

    # https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2023/30019781.pdf
    # https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2023/20023083.pdf
    # Download the pdf if it does not already exist
    if not os.path.exists(path):
        url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code == 200:
            with open(path, "wb") as file:
                print(f"Downloading document {year} Doc ID #{doc_id}...")
                file.write(response.content)
        else:
            if os.path.exists(path):
                os.remove(path)
            # Handle the case where the PDF could not be downloaded
            print(f"\nDocument {year} Doc ID #{doc_id} does not exist.")
            print(f"Server responded with status code: {response.status_code}\n")
            return None, path

    # Extract text from the PDF file if it exists and is not a scanned doc.
    if check_valid_pdf(path=path):
        text = extract_text_from_pdf(file_path=path)
        return text, path
    else:
        print(f"\nInvalid PDF: {year} Doc ID #{doc_id} is a scanned PDF.")
        if os.path.exists(path):
            print(f"Deleting invalid PDF: {year} Doc ID #{doc_id}.")
            os.remove(path)
        return None, path


if __name__ == "__main__":
    # Initialize stocks history tracker.
    stock_tracker = StockHistory(start_date="2012-01-01", end_date="2024-06-01")

    parsed_disclosures = load_json(path="./data/parsed_disclosures/house.json")['disclosures']
    failures = load_json(path="./data/parsed_disclosures/failures.json")['failures']

    new_disclosures = []

    # Assign years to collect data for.
    print('Starting data collection...')


    years = range(2019, 2024)#[2024]
    for year in years:
        document_path = f"./data/clerk_house/{year}FD.xml"
        if not os.path.exists(document_path) or (year == datetime.now().year):
            print(f"Downloading clerk house disclosures for year {year}.")
            get_financial_disclosures(year=year)
        xml_data = read_xml_file(file_path=document_path)

        # Count the number of periodic disclosures in the the XML data
        periodic_disclosures = [record for record in xml_data if record["FilingType"] == "P"]

        # Only collect FilingType 'P' for Periodic Transaction Reports.
        for i,record in enumerate(periodic_disclosures):
            doc_id = record["DocID"]
            print(f"Extracting data for Year {year}, DocID #{doc_id}. ({i}/{len(periodic_disclosures)})")

            # Skip record if data has already been extracted for document ID
            if check_disclosure_recorded(disclosures=parsed_disclosures, failures=failures, doc_id=doc_id):
                print(f"Disclosure already extracted for DocID #{doc_id}. ({i}/{len(periodic_disclosures)})")
                continue

            # Extract raw text from the disclosure PDF document
            text, pdf_path = get_document(year, doc_id)
            
            if text is None:
                # Skip if pdf file is invalid or does not exist.
                print(f"Failed to extract text from PDF document #{doc_id}.")
                if os.path.exists(pdf_path):
                    print(f"Deleting invalid PDF: {year} Doc ID #{doc_id}.")
                    os.remove(pdf_path)
                print(f"Skipping document #{doc_id}.\n")
                failures.append(doc_id)

                continue

            elif "[ST]" not in text and "[OP]" not in text:
                # Financial disclosure is not for stocks or options (skip).
                print(f"Document is not a disclosure for stocks or options.")
                if os.path.exists(pdf_path):
                    print(f"Deleting invalid PDF: {year} Doc ID #{doc_id}.")
                    os.remove(pdf_path)
                print(f"Skipping document #{doc_id}.\n")
                failures.append(doc_id)

                continue

            # Parse the disclosure data from the disclosure document text
            disclosure_data = parse_house_doc(text=text)
            if not disclosure_data['disclosures']:
                # Skip to next document if failed to extract stocks data from text.
                print(f"WARNING: Failed to extract json data from PDF document #{doc_id}.")
                if os.path.exists(pdf_path):
                    print(f"Deleting invalid PDF: {year} Doc ID #{doc_id}.")
                    os.remove(pdf_path)
                print(f"Skipping document #{doc_id}.\n")
                failures.append(doc_id)
                continue
            else:
                print(f"\n - - DISCLOSURE DATA WAS EXTRACTED - -")

            # Process the disclosure data
            for disclosure in disclosure_data["disclosures"]:
                # Add additional fields to disclosure record
                disclosure["doc_id"] = doc_id
                disclosure["first_name"] = record["First"]
                disclosure["last_name"] = record["Last"]

                if disclosure["ticker"] == "FB":
                    disclosure["ticker"] = "META"

                # Correct the asset_code 
                if (disclosure["option_type"] == "call" and disclosure["asset_code"] == "ST"):
                    disclosure["asset_code"] == "OP"

                # Assign number of shares if options_count field is not None
                if (disclosure["options_count"] is not None and disclosure["share_count"] is None):
                    disclosure["share_count"] = 100 * disclosure["options_count"]

                # Assign the asset_type field label to the disclosure record
                if disclosure["asset_code"] in asset_types.keys():
                    disclosure["asset_type"] = asset_types[disclosure["asset_code"]]
                else:
                    disclosure["asset_type"] = None


                # If asset is a stock or option, assign the share price at date of transaction.
                if disclosure["ticker"]:
                    print(f"ALERT: Getting price for '{disclosure['ticker']}'.")
                    price = stock_tracker.price(ticker=disclosure["ticker"], date_str=disclosure["transaction_date"])
                    if not price:
                        print(f"WARNING: Price retrieval failed for '{disclosure['ticker']}'.")  
                        disclosure['ticker'] = None
                else:
                    price = None

                disclosure["stock_price"] = price
                disclosure["governing_body"] = "HOUSE"

                if disclosure['ticker']:
                    print(f'Owner: {disclosure["first_name"]}{ disclosure["last_name"]}')
                    print(f"Asset: {disclosure['asset_type']}")
                    print(f"Ticker: {disclosure['ticker']}")
                    print(f"Price: ${disclosure['stock_price']}")
                    print(f"Date: {disclosure['transaction_date']}\n")
                    new_disclosures.append(disclosure)

    # Sort the parsed disclosures by date (earliest to latest)
    print(f"\n- - PARSING COMPLETE - -")
    print(f"{len(new_disclosures)} new transactions have been extracted.")
    parsed_disclosures.extend(new_disclosures)
    parsed_disclosures = sort_by_date(disclosures=parsed_disclosures)
    print(f"Total Transactions: {len(parsed_disclosures)}\n")

    save_path = "./data/parsed_disclosures/house.json"
    save_data = {'disclosures': parsed_disclosures}
    write_json(data=save_data, path=save_path)
    print(f"Data saved to '{save_path}'.")

    # Record failed documents
    write_json(data={'failures': failures}, path=f"./data/parsed_disclosures/failures.json")
