import json


def load_json(path: str) -> dict:
    """Tool for loading json data from a file to dictionary.

    Args:
        path (str): Path to the json file.

    Returns:
        dict: Json data as a python dictionary.
    """
    # Open the file for reading
    with open(path, "r", encoding="utf-8") as file:
        # Load the contents from the file
        data = json.load(file)
    return data


def write_json(data: dict, path:str) -> None:
    """Writes dictionary data to a json file with proper formatting.

    Args:
        data (dict): _description_
        path (str): _description_
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        print(f"Data was written to {path}")


def extract_json(text: str) -> dict:
    """This function extracts a python dictionary data from a json string.

    Args:
        text (str): The input text containing json data.

    Returns:
        dict: The extracted json data as a python dictionary.
    """
    json_string = text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(json_string)
        print("ALERT: Successfully converted JSON string to python dict.")
        return data
    except:
        print("WARNING: Failed to convert JSON string to python dict.")
        return None
