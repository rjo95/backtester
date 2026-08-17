# -*- coding: utf-8 -*-


import pandas as pd
import yfinance as yf

#%%
# 1. Definieer de parameters
# Gebruik '^GSPC' voor de S&P 500 index of 'SPY' voor de ETF
ticker_symbol = "^GSPC" 

start_date = "1927-01-01"
end_date = None  # None laadt data tot vandaag

print(f"Bezig met ophalen van OHLC-data voor {ticker_symbol}...")

# 2. Download de historische data
df = yf.download(ticker_symbol, start=start_date, end=end_date, interval="1d")

# 3. Bekijk de eerste rijen van de data
print("\nEerste 5 rijen van de gedownloade data:")
print(df.head())

# 4. Opslaan als CSV-bestand voor verdere analyse (bijv. backtesting)
file_name = "sp500_ohlcv_data.csv"
df.to_csv(file_name)

print(f"\nData succesvol opgeslagen als '{file_name}'.")

#%%