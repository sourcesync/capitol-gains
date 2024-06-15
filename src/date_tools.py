from datetime import datetime, timedelta, date
import holidays

def new_years_dates(years:list[int]):
    dates = []
    for year in years:
        new_year = date(year, 1, 1)
        dates.append(new_year)
    
    return dates

def get_thanksgiving_dates(years:list[int]):
    dates = []
    for year in years:
        nov_first = date(year, 11, 1)
        first_thursday = nov_first + timedelta(days=(3 - nov_first.weekday() + 7) % 7)
        thanksgiving = first_thursday + timedelta(weeks=3)
        dates.append(thanksgiving)
    
    return dates

def good_friday_dates(years:list[int]):
    """Calculate the date of Easter for a given year using the algorithm."""
    good_fridays = []
    for year in years:
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        
        date = datetime(year, month, day).date() - timedelta(days=2)
        good_fridays.append(date)

    return good_fridays

def us_holidays():
    years = range(2012, datetime.now().year +1)
    us_holidays = holidays.US(years=years)
    dates = [date for date in us_holidays.keys()]

    good_fridays = good_friday_dates(years=years)
    thanksgivings = get_thanksgiving_dates(years=years)
    new_years = new_years_dates(years=years)
    
    dates.extend(good_fridays)
    dates.extend(thanksgivings)
    dates.extend(new_years)

    close_dates = []
    for date in dates:
        close_dates.append(date + timedelta(days=1))
        close_dates.append(date - timedelta(days=1))
    
    dates.extend(close_dates)
    return dates


def nearest_monday(date_str, date_format="%Y-%m-%d"):
    # Parse the input date string
    date_obj = datetime.strptime(date_str, date_format).date()

    # Get the weekday (0=Monday, 6=Sunday)
    weekday = date_obj.weekday()

    # Check if the date falls on a Saturday (5) or Sunday (6)
    if weekday == 5:  # Saturday
        # Adjust Saturday to Friday
        adjusted_date = date_obj - timedelta(days=1)
    elif weekday == 6:  # Sunday
        # Adjust Sunday to Friday
        adjusted_date = date_obj - timedelta(days=2)
    else:
        # It's a weekday, return the original date
        return date_str

    # Return the adjusted date string in the same format
    return adjusted_date.strftime(date_format)


def get_next_day(date_str, current_format="%Y-%m-%d", target_format="%Y-%m-%d"):
    # Parse the date from the current format
    date_obj = datetime.strptime(date_str, current_format)
    # Add one day
    next_day = date_obj + timedelta(days=1)
    # Convert back to string in the target format
    return next_day.strftime(target_format)


def format_date(date_str, current_format="%m/%d/%Y", target_format="%Y-%m-%d"):
    try:
        # Parse the date from the current format
        nearest_monday(date_str=date_str, date_format="%m/%d/%Y")
        date_obj = datetime.strptime(date_str, current_format)
        # Convert it to the target format
        return date_obj.strftime(target_format)
    except ValueError as e:
        print(f"Error converting date: {date_str} - {e}")
        return None
    

def days_from_date(date_str:str, days:int, date_format="%Y-%m-%d"):
    """Returns a new date string that is {days} number of days from {date_str}

    Args:
        date_str (str): The original date string
        days (int): The number of days from the date string 
        date_format (str, optional): The input and output date format. Defaults to "%Y-%m-%d".
    """
    input_date = datetime.strptime(date_str, date_format)
    output_date = input_date + timedelta(days=days)

    output_datestr = output_date.strftime(date_format)
    # Ensure the output date is a weekday
    output_datestr = nearest_monday(date_str=output_datestr)
    return output_datestr





def get_most_recent_weekday(date_format="%Y-%m-%d"):
    today = datetime.now()
    # Check if today is a weekend
    if today.weekday() == 5:  # Saturday
        return (today - timedelta(days=1)).strftime(date_format)
    elif today.weekday() == 6:  # Sunday
        return (today - timedelta(days=2)).strftime(date_format)
    else:
        return today.strftime(date_format)


def days_ago(date_str, date_format="%m/%d/%Y"):

    # Convert the date string to a datetime object
    past_date = datetime.strptime(date_str, date_format)

    # Get today's date
    today_date = datetime.now()

    # Calculate the difference in days
    delta = today_date - past_date
    return delta.days

def sort_by_date(disclosures: list[dict]):
    """Sorts a list of disclosures by the transaction date from least to most recent

    Args:
        disclosures (list[dict]): List of disclosure dictionary records
    """
    return sorted(disclosures, key=lambda x: datetime.strptime(x["transaction_date"], "%Y-%m-%d"))
