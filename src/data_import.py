"""
Hoofdscript voor backtester
"""

import os
import pandas as pd

#%% pad naar data
# Dit is de map waar huidige '.py' in staat
src_dir = os.path.dirname(os.path.abspath(__file__))

# Ga één map omhoog om in de hoofdmap
project_root = os.path.dirname(src_dir)

#%% Verkrijg BTC data 
data_btc = os.path.join(project_root, 'data', 'blockhorizon_20260803')

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
                                "Open":"open",
                                "High":"high",
                                "Low":"low",
                                "Close":"close",
                                "Days Until Halving": "days_until_halving",
                                "MVRV Z-Score": "mvrv_z_score",
                                "Realized Price [USD]": "realized_price",
                                }
                        )


#%% Verkrijg SP500 data 
data_sp500 = os.path.join(project_root, 'data', 'sp500')

df_sp500 = pd.read_csv(
    os.path.join(data_sp500, 'sp500_ohlcv_data.csv'), 
    header=0, 
    skiprows=1, # Sla de eventuele foute header over
    names=['Date', 'close', 'high', 'low', 'open', 'volume']
)

if 'Date' in df_sp500.columns:
    df_sp500['Date'] = pd.to_datetime(df_sp500['Date'])
    df_sp500 = df_sp500.set_index('Date')

# Verwijder de overbodige 'Price' kolom als die er nog in staat
if 'Price' in df_sp500.columns:
    df_sp500 = df_sp500.drop(columns=['Price'])

# Maak de rest van de kolommen numeriek
df_sp500 = df_sp500.astype(float)

#%% voorbeeld
if __name__ == "__main__":
    df_btc.columns
    print(df_btc.head())
    print(df_sp500.head())
    


