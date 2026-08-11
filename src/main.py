"""
Hoofdscript voor backtester
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

from data_import import df_btc
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log
import plotly_plots

import plotly.io as pio
pio.renderers.default = "browser"

#%%
# config obv kolom logica: de 'maak_regel' maakt een lambda functie
CONFIG = {
        # start en einddatum test
        'date_min':'2020-01-31',
        'date_max':'2035-12-30',
        
        # fee in pct
        "fee": 0.001,
        
        # sl en tp in pct
        "stop_loss_pct": None,  
        "take_profit_pct": None, 
        "max_holding_period": None,
        
        # rules
        "rules": {
            "buy": [
                    backtest.maak_regel("RSI_14", "<", 40),      
                    backtest.maak_regel("SMA_50", ">", "SMA_100"),  
                    ],
            
            "sell": [
                    backtest.maak_regel("RSI_14", ">", 70),
                    ]
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


# --- DYNAMISCH INDICATOREN OPHALEN UIT CONFIG ---
gebruikte_indicatoren = backtest.extract_indicators_from_config(CONFIG, df_btc.columns)

# plots (geef de gebruikte indicatoren mee)
plot_performance = plotly_plots.plot_performance(df_final, extra_columns=gebruikte_indicatoren)
plot_drawdowns = plotly_plots.plot_drawdowns(df_final)


#%%
if __name__ == "__main__":
    print(df_final)
    print(df_stats)
    plot_performance.show()
    gebruikte_indicatoren
    
    #%%
    gebruikte_indicatoren
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    