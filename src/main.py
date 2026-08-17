"""
Hoofdscript voor backtester
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

from data_import import df_btc, df_sp500
import indicators as add_ind
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log

#import plotly_plots

import plotly.io as pio
pio.renderers.default = "browser"

#%%

# config obv kolom logica: de 'maak_regel' maakt een lambda functie
CONFIG = {
        # start en einddatum test
        'date_min':'1920-01-31',
        'date_max':'2035-12-30',
        
        # fee in pct
        "fee": 0.002,
        
        # sl en tp in pct
        "stop_loss_pct": None,  
        "take_profit_pct": None, 
        "max_holding_period": None,
        
        
        # add indicators (nodig voor rules)
        "indicators": [
                       ("RSI_6", add_ind.rsi, 6),
                       ("TSM_90", add_ind.time_series_momentum_days, 90),
                       ],
                
        # rules
        "rules": {
                "buy": [
                        ("RSI_6", "<", 20),      
                        ("TSM_90", "==", 1),   
                        ],
                
                "sell": [
                        ("RSI_6", ">", 70), 
                        ]
                }
        }

# apply backtest engine to df and config
df_final = backtest.run_pipeline(CONFIG = CONFIG,
                               df = df_btc)

# trade log obv result df
trade_log = calculate_trade_log(CONFIG = CONFIG,
                                df = df_final)

# weergeven statistieken result
df_stats = calculate_summary_stats(df_final)

# --- DYNAMISCH INDICATOREN OPHALEN UIT CONFIG ---
gebruikte_indicatoren = backtest.extract_indicators_from_config(CONFIG, df_btc.columns)

# plots (geef de gebruikte indicatoren mee)
#plot_performance = plotly_plots.plot_performance(df_final, extra_columns=gebruikte_indicatoren)
#plot_drawdowns = plotly_plots.plot_drawdowns(df_final)


#%%
if __name__ == "__main__":
    print(df_final)
    print(df_stats)
    gebruikte_indicatoren
    
    #%%
    gebruikte_indicatoren
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    