import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error
import joblib
import os

def clean_input(records:list[dict]):
    df = pd.DataFrame(records)
    df['sale_days_ago'] = df['sale_days_ago'].fillna(-1)
    df['purchase_days_ago'] = df['purchase_days_ago'].fillna(-1)

    # Create binary features for purchase and sale occurrence
    # df['purchase_occurred'] = (df['purchase_days_ago'] != -1).astype(int)
    # df['sale_occurred'] = (df['sale_days_ago'] != -1).astype(int)
    
    # Define features and target
    x = df.drop(columns=['date', 'purchase_owner', 'sale_owner', 'sale_speculation', 'purchase_speculation', 'ticker'])
    try: 
        x = x.drop(columns=['price_change'])
    except:
        pass
    return x


def model_predict(records:list[dict], model="gradient_boost", clean=True):
    if model == "gradient_boost":
        model = joblib.load(f'{os.path.dirname(__file__)}/pretrained_models/gradient_boosting_regressor.joblib')
    else:
        print("Model not found")
        return None

    if clean:
        records = clean_input(records=records)
    # Make predictions and evaluate the model
    predictions = model.predict(records)

    return predictions