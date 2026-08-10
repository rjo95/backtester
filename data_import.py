"""
Hoofdscript voor backtester
"""

import os
import pandas as pd
#import pandas_ta as ta

#%% pad naar data
# Dit is de map waar huidige '.py' in staat
src_dir = os.path.dirname(os.path.abspath(__file__))

# Ga één map omhoog om in de hoofdmap
project_root = os.path.dirname(src_dir)

# Bouw het pad naar data
data_dir = os.path.join(project_root, 'data', 'blockhorizon_20260803')

#%% Inlezen en direct joinen op 'timestamp'
df = (
    pd.read_csv(os.path.join(data_dir, 'price_ohlc.csv'))
    .set_index('timestamp')
    .join([
        pd.read_csv(os.path.join(data_dir, 'days_until_halving.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp'),
            
        pd.read_csv(os.path.join(data_dir, 'mvrv_z_score.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp'),
            
        pd.read_csv(os.path.join(data_dir, 'realized_price.csv'))
            .drop(columns=['Price [USD]']).set_index('timestamp')
            
    ], how='left')
    .reset_index()
)

#%% timestamp naar datum; datum als index
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.set_index('timestamp')
df_btc = df
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

# toevoegen indicators
#df_btc.ta.sma(length=50, append=True)
#df_btc.ta.sma(length=200, append=True)
#df_btc.ta.rsi(length=14, append=True)

#%% voorbeeld
if __name__ == "__main__":
    df_btc.columns
    print(df_btc.head())
    


