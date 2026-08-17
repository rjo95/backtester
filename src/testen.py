# -*- coding: utf-8 -*-

from data_import import df_btc, df_sp500
import indicators


#%%
df_sp500.head()

#%%
df_sp500 = indicators.sma(df=df_sp500 ,n=10)
df_sp500 = indicators.time_series_momentum_days(df=df_sp500 ,n=90)

#%%

