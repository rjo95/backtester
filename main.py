"""
Hoofdscript voor backtester
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

from data_import import df_btc
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log
import plotly_plots

#import plotly.io as pio
#pio.renderers.default = "browser"
#%% nog maken: dash app: ook kiezen geschikte kolommen...
df_btc.columns

#%%
# config obv kolom logica: de 'maak_regel' maakt een lambda functie
CONFIG = {
    # backtest datum
    'date_min':'2010-01-31',
    'date_max':'2035-12-30',
    
    # pct fee per trade
    "fee": 0.001,
    
    # sl en tp in pct; max holding period days
    "stop_loss_pct": None,  
    "take_profit_pct": None, 
    "max_holding_period": None,
    
    # backtest regels
    "rules": {
        "buy": backtest.maak_regel("RSI_14", ">", 60),
        "sell": backtest.maak_regel("RSI_14", "<", 40),
    }
}

#%% apply backtest engine to df and config
df_final = backtest.run_pipeline(CONFIG = CONFIG,
                               df = df_btc)

# trade log obv result df
trade_log = calculate_trade_log(CONFIG = CONFIG,
                                df = df_final)

# resultaat df
df_stats = calculate_summary_stats(df_final)


# plots
plot_performance=plotly_plots.plot_performance(df_final)
plot_drawdowns=plotly_plots.plot_drawdowns(df_final)


#%%
if __name__ == "__main__":
    print(df_final)
    print(df_stats)


