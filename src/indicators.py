# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

import pandas_ta as ta
import numpy as np

#%%
def sma(df, n:int, name=None):
    col_name = name if name else f'SMA_{n}'
    df[col_name] = ta.sma(df['close'], length=n)
    return df

#%%
def rsi(df, n:int, name=None):
    col_name = name if name else f'RSI_{n}'
    df[col_name] = ta.rsi(df['close'], length=n)
    return df

#%%
def time_series_momentum_days(df, n:int, name=None):
    col_name = name if name else f'TSM_{n}'
    # We slaan de hulpreturn op met een dynamische naam of unieke naam als dat nodig is, 
    # maar de hoofdindicator krijgt de gevraagde 'col_name'.
    df[f'Return_{n}'] = df['close'].pct_change(periods=n)
    df[col_name] = (df[f'Return_{n}'] > 0).astype(int)
    return df

#%%
def close_location_value(df, name=None):
    col_name = name if name else 'CLV'
    high_low_range = df['high'] - df['low']
    high_low_range = np.where(high_low_range == 0, np.nan, high_low_range)
    df[col_name] = (df['close'] - df['low']) / high_low_range
    return df

#%%
def donchian_channels(df, n: int, name_high=None, name_low=None):
    # Donchian levert twee kolommen op. Hiervoor kun je eventueel 
    # name_high en name_low gebruiken in je CONFIG als dat nodig is.
    df[name_high if name_high else f'Donchian_High_{n}'] = df['high'].rolling(window=n).max()
    df[name_low if name_low else f'Donchian_Low_{n}'] = df['low'].rolling(window=n).min()
    return df

#%%
def return_zscore(df, n: int, name=None):
    col_name = name if name else f'Return_ZScore_{n}'
    returns = df['close'].pct_change()
    rolling_mean = returns.rolling(window=n).mean()
    rolling_std = returns.rolling(window=n).std()
    df[col_name] = (returns - rolling_mean) / rolling_std
    return df

#%%
def atr(df, n: int = 14, name=None):
    col_name = name if name else f'ATR_{n}'
    df[col_name] = ta.atr(df['high'], df['low'], df['close'], length=n)
    return df


#%%


