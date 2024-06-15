import re

from src.date_tools import format_date


def validator(text: str) -> bool:
    """This function validates that the input string is in the correct format to be 
    pared by the extract function.

    Args:
        text (str): Input string to be validated    

    Returns:
        bool: True if the input string is in the correct format, False otherwise
    """
    pattern = re.compile(r'^[\w\s,&-/.]+ \([\w]+\) \[ST\] [PS] \d{2}/\d{2}/\d{4} \d{2}/\d{2}/\d{4} \$[\d,]+ - \$[\d,]+$')
    if pattern.match(text):
        return True
    else:
        return False
    
def extract(data: str) -> dict:
    """This function extracts the relevant data from the input text and 
    returns a dictionary of the extracted data.

    Args:
        data (str): Input text to be parsed

    Returns:
        dict: Dictionary of the extracted data
    """

    dollars = data.split("$")
    value_low = int(''.join(char for char in dollars[-2] if char.isdigit()))
    value_high = int(''.join(char for char in dollars[-1] if char.isdigit()))
    
    data = dollars[0]
    if " P " in data:
        transaction_type = "purchase"
        data_split = data.split(" P ")
        dates = data_split[-1]
    elif " S " in data:
        transaction_type = "sale"
        data_split = data.split(" S ")
        dates = data_split[-1]
        
    transaction_date = format_date(date_str=dates.split()[0].strip())
    notification_date = format_date(date_str=dates.split()[1].strip())
        
    data = data_split[0]
    data = data.strip()
    
    ticker = data.split()[-2]
    ticker_symbol = ticker.replace("(", "")
    ticker_symbol = ticker_symbol.replace(")", "")
    ticker_symbol = ticker_symbol.strip()
    
    name = data.split(ticker)[0]
    
    ticker = ticker_symbol.upper()
    
    record = {
        "asset_name": name,
        "transaction": transaction_type,
        "share_count": None,
        "options_count": None,
        "option_type": None,
        "option_activity": None,
        "option_exp_date": None,
        "strike_price": None,
        "ticker": ticker,
        "transaction_date": transaction_date,
        "notification_date": notification_date,
        "asset_value_low": value_low,
        "asset_value_high": value_high,
        "description": None,
        "asset_code": "ST",
        "doc_id": None,
        "first_name": None,
        "last_name": None,
        "asset_type": "Stock",
        "stock_price": None,
        "governing_body": "HOUSE",
    }
    return record
    
def clean_string(text:str) -> str:
    """This function cleans the text by removing unwanted characters and spaces.

    Args:
        text (str): Input strings to be cleaned

    Returns:
        str: The cleaned text
    """
    # Regex pattern to match "S" or "P" followed by any string and then a date in MM/DD/YYYY format
    pattern = re.compile(r'([SP])\s+.*?(\d{2}/\d{2}/\d{4})')
    # Replace the matched string with "S" or "P" followed by the date
    cleaned_text = re.sub(pattern, r'\1 \2', text)
    return cleaned_text

def parse_house_doc(text:str) -> dict:
    """This function parses the text extracted from a house disclosure document and 
    returns a dictionary of the extracted data.

    Args:
        text (str): Input text extracted from a house disclosure pdf document

    Returns:
        dict: Extracted disclosure data from the input text
    """
    null_char = "\x00"
    fs_new = f"F{null_char*5} S{null_char*5}: New"
    so = f"S{null_char*9} O{null_char}:"
    d_str = f"D{null_char*10}:"
    
    # Create empty list to store parsed records
    parsed_records = []

    lines = text.splitlines()
    for i,line in enumerate(lines):
        if "[ST]" in line:
            format = None
            data = ""
            section = lines[i-2: i+2]
            if section[1].strip() == "$200?" and "$" == section[-1][0]:
                format = 1
                data = f"{section[2]} {section[3]}"
            elif section[2] == "[ST]":
                format = 2
                data = f"{section[1]} {section[2]}"
                
            elif section[0] == fs_new and section[3] == fs_new and "(" in section[2] and "$" == section[1].split()[-1][0]:
                format = 17
                data = f"{section[1]} {section[2]}"
                
            elif section[0] == fs_new and section[3][:len(fs_new)] == fs_new:
                format = 3
                data = section[2]
                
            elif section[0][:len(so)] == so and section[3][:len(fs_new)]  == fs_new:
                format = 4
                data = f"{section[1]} {section[2]}"
                
            elif section[1] == "$200?" and section[3] == fs_new:
                format = 5
                data = section[2]
                
            elif section[0] == "$200?" and section[3] == fs_new:
                format = 6
                data = f"{section[1]} {section[2]}"
                
            elif section[0] == fs_new and section[3][0] == "$":
                format = 7
                data = f"{section[2]} {section[3]}"
            
            elif section[0] == fs_new and section[3] == "Type Date Gains >":
                format = 8
                data = section[2]
                
            elif section[1] == fs_new and section[3] == fs_new:
                format = 9
                data = section[2]
                
            elif section[0][:len(d_str)] == d_str and section[3] == fs_new:
                format = 10
                data = f"{section[1]} {section[2]}"
            
            elif section[1] == fs_new and "$" == section[3][0]:
                format = 11
                data = f"{section[2]} {section[3]}"
                
            elif section[0][:len(so)] == so and section[3] == "Type Date Gains >":
                format = 12
                data = f"{section[2]} {section[3]}"
                
            elif section[2][-1] == "-" and section[3][0] == "$":
                format = 13
                data = f"{section[2]} {section[3]}"
                
            elif "$" in section[2].split(" - ")[-1]:
                format = 14
                data = section[2]
                
            elif "$" in section[1].split(" - ")[-1]:
                format = 15
                data = f"{section[1]} {section[2]}"
                
            elif "$" in section[0].split(" - ")[-1]:
                format = 16
                data = f"{section[0]} {section[2]}"
                
            data = data.replace("ID Owner Asset Transaction Date Notification Amount Cap.", "")
            if data[:3] == "JT ":
                data = data[3:]
                
            if data[:3] == "SP ":
                data = data[3:]
                
            if " SP " in data:
                data = data.split(" SP ")[-1]
            
            words = data.split(" ")
            try:
                if words[-1] == "[ST]" and words[-2][0] == "(" and words[-2][-1] == ")":
                    new_str = f" {words[-2]} [ST]"
                    data = data.replace(new_str, "")
                    if " P " in data:
                        data = data.replace(" P ", f" {words[-2]} [ST] P ")
                    elif " S " in data:
                        data = data.replace(" S ", f" {words[-2]} [ST] S ")
                    elif " E " in data:
                        data = data.replace(" E ", f" {words[-2]} [ST] E ")
            except:
                pass
                
            words = data.split(" ")
            try:
                if words[-1] == "[ST]":
                    data = data.replace("[ST]", "")
                    if " P " in data:
                        data = data.replace(" P ", f" [ST] P ")
                    elif " S " in data:
                        data = data.replace(" S ", f" [ST] S ")
            except:
                pass
            
            words = data.split(" ")
            try:
                if words[-2] == "[ST]" and words[-3][0] == "(" and words[-3][-1] == ")":
                    new_str = f" {words[-3]} [ST]"
                    data = data.replace(new_str, "")
                    if " P " in data:
                        data = data.replace(" P ", f" {words[-3]} [ST] P ")
                    elif " S " in data:
                        data = data.replace(" S ", f" {words[-3]} [ST] S ")
            except:
                pass
            
            
            data = data.strip()
            
            try:
                last_dash = data.split(" - ")[-1].split(" ")
                substring = ""
                for item in last_dash:
                    if "$" not in item:
                        data = data.replace(item, "")
                        substring = f"{substring} {item}"
                        
                if substring:
                    data = data.replace(substring, "")
                    substring = f"{substring} ("
                    data = data.replace("(", substring) 
            except: 
                pass
            
            if data[:3] == "DC ":
                data = data.replace("DC ", "")

            # Final cleaning of the data
            data = data.replace("-", " -")
            data = data.replace("[ST]P", "[ST] P ")
            data = data.replace("$", " $")
            data = data.replace("(partial)", "")
            data = data.replace("Common Stock", "")
            data = data.replace("Stock", "")
            data = data.replace(" Class A ", " ")
            data = data.replace(so, "")
            data = data.replace(" Corporation -", " ")
            
            data = re.sub(r'\s+', ' ', data)
                
            try:
                words = data.split("[ST]")[-1]
                tick = words.split()[0]
                if tick[0] == "(" and tick[-1] == ")":
                    data = data.replace(f"[ST] {tick}", f"{tick} [ST]")
            except:
                pass
            
            data = clean_string(data)
            data = data.strip()
            
            if format:
                valid = validator(data)
                if valid:
                    parsed_data = extract(data)
                    parsed_records.append(parsed_data)
    
    parsed_records = {"disclosures": parsed_records}
    return parsed_records