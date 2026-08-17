"""
Hoofdscript voor backtester
"""

import os
import pandas as pd

#%% pad naar data
# 1. De map waar dit script in staat (src)
src_dir = os.path.dirname(os.path.abspath(__file__))

# 2. De hoofdmap van het project (één niveau omhoog vanuit src)
project_root = os.path.dirname(src_dir)

# Als jouw projectstructuur op de server toch één map dieper zit, 
# kun je eventueel os.path.dirname(os.path.dirname(src_dir)) gebruiken.
# Maar op basis van je eerdere toelichting is één stap omhoog voldoende:
data_dir = os.path.join(project_root, 'data')

#%% Verkrijg BTC data 
data_btc = os.path.join(data_dir, 'blockhorizon_20260803')

if not os.path.exists(data_btc):
    raise FileNotFoundError(f"Kan de map met BTC data niet vinden op: {data_btc}")

# Inlezen en direct joinen op 'timestamp'
df_btc = (
    pd.read_csv(os.path.join(data_btc, 'price_ohlc.csv'))
    .set_index('timestamp')
    .join([
        pd.read_csv(os.path.join(data_btc, 'days_until_halving.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp'),
            
        pd.read_csv(os.path.join(data_btc, 'mvrv_z_score.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp'),
            
        pd.read_csv(os.path.join(data_btc, 'realized_price.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp')
    ], how='left')
    .reset_index()
)

# timestamp naar datum; datum als index
df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
df_btc = df_btc.set_index('timestamp')
df_btc = df_btc.rename(
    columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Days Until Halving": "days_until_halving",
        "MVRV Z-Score": "mvrv_z_score",
        "Realized Price [USD]": "realized_price",
    }
)


#%% Verkrijg SP500 data 
data_sp500 = os.path.join(data_dir, 'sp500')

sp500_file = os.path.join(data_sp500, 'sp500_ohlcv_data.csv')
if os.path.exists(sp500_file):
    df_sp500 = pd.read_csv(
        sp500_file, 
        header=0, 
        skiprows=1, 
        names=['Date', 'close', 'high', 'low', 'open', 'volume']
    )

    if 'Date' in df_sp500.columns:
        df_sp500['Date'] = pd.to_datetime(df_sp500['Date'])
        df_sp500 = df_sp500.set_index('Date')

    if 'Price' in df_sp500.columns:
        df_sp500 = df_sp500.drop(columns=['Price'])

    df_sp500 = df_sp500.astype(float)
else:
    df_sp500 = pd.DataFrame()  # Leeg dataframe als fallback


#%% voorbeeld
if __name__ == "__main__":
    print("--- BTC DataFrame kolommen ---")
    print(df_btc.columns)
    print(df_btc.head())
    
    print("\n--- S&P500 DataFrame kolommen ---")
    print(df_sp500.head())
