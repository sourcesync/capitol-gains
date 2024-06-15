import math

def time_decay(x):
    e = math.e
    return (math.exp(x) - 1) / (e - 1)

def normalize(disclosures: list[dict]) -> list[dict]:
    """Normalize the values in the disclosures list.
    Uses min-max normalization to scale the values between 0 and 1.

    Args:
        disclosures (list[dict]): List of parsed disclosure records

    Returns:
        list[dict]: Normalized list of disclosure records
    """
    keys_to_normalize = [
        "purchase_count",
        "purchase_count_individual",
        "purchase_speculation",
        "purchase_days_ago",
        "sale_count",
        "sale_count_individual",
        "sale_speculation",
        "sale_days_ago"
    ]
    
    min_max_values = {}
    
    for key in keys_to_normalize:
        key_data = [disclosure.get(key) for disclosure in disclosures if disclosure.get(key) is not None]
        if key_data:
            min_max_values[key] = (min(key_data), max(key_data))
        else:
            min_max_values[key] = (0, 0)

    for disclosure in disclosures:
        for key in keys_to_normalize:
            min_val, max_val = min_max_values[key]
            value = disclosure.get(key)
            if value is None:
                continue
            if min_val == max_val:
                disclosure[key] = 0
            else:
                if key in ['sale_days_ago', 'purchase_days_ago']:
                    # Days ago scores should be inverted so that the score is higher the more recent the date is.
                    disclosure[key] = 1 - ((value - min_val) / (max_val - min_val))
                else:
                    disclosure[key] = (value - min_val) / (max_val - min_val)

    return disclosures