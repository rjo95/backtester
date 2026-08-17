"""
Hoofdscript voor backtester
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

#%%
def calculate_summary_stats(df, CONFIG=None):
    if CONFIG is None:
        CONFIG = {}
        
    """
    Balans tussen compact en informatief voor backtest statistieken (gecorrigeerd).
    """
    # Zorg dat we werken met een schone kopie en genormaliseerde groei vanaf start van de slice
    strat_growth = df['strategy_growth'] / df['strategy_growth'].iloc[0]
    bh_growth = df['buy_and_hold_growth'] / df['buy_and_hold_growth'].iloc[0]

    # Trades voorbereiden obv groeifactoren (eindwaarde / beginwaarde per trade)
    trades = df.groupby('trade_id')['strategy_growth'].agg(lambda x: x.iloc[-1] / x.iloc[0])
    trades = trades[trades.index != 0] # Filter 'geen positie' (trade_id 0) eruit
    
    # Omzetten naar losse trade rendementen (bijv. 1.15 -> 0.15)
    trade_returns = trades - 1
    
    aantal_trades = len(trade_returns)
    win_trades = trade_returns[trade_returns > 0]
    loss_trades = trade_returns[trade_returns < 0]
    
    # Kerncijfers trades
    win_pct = len(win_trades) / aantal_trades if aantal_trades > 0 else 0
    gem_win = win_trades.mean() if not win_trades.empty else 0
    gem_loss = loss_trades.mean() if not loss_trades.empty else 0
    
    # Profit Factor: gebaseerd op totale bruto winst en bruto verlies in factoren
    gross_profit = win_trades.sum() if not win_trades.empty else 0
    gross_loss = abs(loss_trades.sum()) if not loss_trades.empty else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    
    # Geometrisch gemiddelde per trade (rekening houdend met compounding)
    if aantal_trades > 0:
        # Product van alle groeifactoren tot de macht (1 / aantal_trades) min 1
        gem_return_trade = (trades.prod()) ** (1 / aantal_trades) - 1
    else:
        gem_return_trade = 0
    
    # Sharpe ratio (geannualiseerd)
    strat_returns = df["strategy_return"].dropna()
    sharpe_ratio = (strat_returns.mean() / strat_returns.std()) * np.sqrt(252) if strat_returns.std() > 0 else 0
    
    # --- GEOPTIMALISEERDE TRADE LENGTE BEREKENING ---
    active_trades = df[df['trade_id'] != 0]
    if not active_trades.empty:
        trade_lengths = active_trades[active_trades['position'] == 1].groupby('trade_id').size()
        gem_trade_lengte = trade_lengths.mean() if not trade_lengths.empty else 0
    else:
        gem_trade_lengte = 0
    
    # Drawdowns berekenen over de genormaliseerde reeks
    peak = strat_growth.cummax()
    drawdown = (strat_growth - peak) / peak
    max_dd_strat = drawdown.min()

    bh_peak = bh_growth.cummax()
    max_dd_bh = ((bh_growth - bh_peak) / bh_peak).min()

    # Overzicht samenstellen
    stats = {
        "Start": df.index[0],
        "Einde": df.index[-1],
        "Aantal Trades": aantal_trades,
        "Win Percentage": f"{win_pct:.2%}",
        "Profit Factor": f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "Inf",
        "Sharpe Ratio": f"{sharpe_ratio:.2f}",
        "Total Return Strat": f"{strat_growth.iloc[-1] - 1:.2%}",
        "Total Return Buy & Hold": f"{bh_growth.iloc[-1] - 1:.2%}",
        "Gem. Return / Trade": f"{gem_return_trade:.2%}",
        "Gem. Win": f"{gem_win:.2%}",
        "Gem. Loss": f"{gem_loss:.2%}",
        "Gem. Trade Lengte": f"{gem_trade_lengte:.1f} dagen",
        "Market Exposure": f"{df['position'].mean():.1%}",
        "Max Drawdown Strat": f"{max_dd_strat:.2%}",
        "Max Drawdown B&H": f"{max_dd_bh:.2%}"
    }
    
    df_stats_res = pd.DataFrame(list(stats.items()), columns=["Metric", "Value"]).set_index("Metric")
    return df_stats_res


#%% Trade log maken per individuele trade
def calculate_trade_log(CONFIG, df):
    """
    input:
        CONFIG en df met 'trade_id', 'position', 'close', 'strategy_growth' etc.
    output:
        DataFrame met per trade een overzicht van entry, exit, prijzen, return (als float) en duur
    """
    trades = []
    
    # Groepeer op unieke trade_id (negeer trade_id 0 wat 'geen positie' is)
    grouped = df[df['trade_id'] != 0].groupby('trade_id')
    
    for trade_id, group in grouped:
        entry_date = group.index[0]
        exit_date = group.index[-1]
        
        entry_price = group['close'].iloc[0]
        exit_price = group['close'].iloc[-1]
        
        # Rendement als numerieke float (handig voor sorteren/filtering, formatteren doe je pas in Streamlit)
        trade_return = (group['strategy_growth'].iloc[-1] / group['strategy_growth'].iloc[0]) - 1
        
        # Aantal dagen dat de trade duurde
        duration = len(group)
        
        trades.append({
            "trade_id": trade_id,
            "entry_date": entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else entry_date,
            "exit_date": exit_date.strftime('%Y-%m-%d') if hasattr(exit_date, 'strftime') else exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return": trade_return,  # Opgeslagen als getal i.p.v. string
            "duration_days": duration
        })
        
    df_trades = pd.DataFrame(trades)
    return df_trades

#%%
if __name__ == "__main__":
    from data_import import df_btc
    from backtest_engine import run_pipeline
   # import indicators as ind_module
    
    from indicators import rsi,time_series_momentum_days

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
                           ("RSI_6", rsi, 6),
                           ("TSM_90", time_series_momentum_days, 90),
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
    result = run_pipeline(CONFIG = CONFIG,
                                   df = df_btc)
    
    # trade log obv result df
    trade_log = calculate_trade_log(CONFIG = CONFIG,
                                    df = result)

    # weergeven statistieken result
    stats = calculate_summary_stats(result)
    
    # show
    print(stats)
    
    #%%
    result.columns
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    