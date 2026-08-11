"""
Hoofdscript voor backtester
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie

import pandas as pd
import numpy as np


#%%
def calculate_summary_stats(df, CONFIG=None):
    if CONFIG is None:
        CONFIG = {}
        
    """
    Balans tussen compact en informatief voor backtest statistieken.
    """
    # Trades voorbereiden
    trades = df.groupby('trade_id')['strategy_growth'].agg(lambda x: x.iloc[-1] / x.iloc[0] - 1)
    trades = trades[trades.index != 0] # Filter 'geen positie' eruit
    
    aantal_trades = len(trades)
    win_trades = trades[trades > 0]
    loss_trades = trades[trades < 0]
    
    # Kerncijfers trades
    win_pct = len(win_trades) / aantal_trades if aantal_trades > 0 else 0
    gem_win = win_trades.mean() if not win_trades.empty else 0
    gem_loss = loss_trades.mean() if not loss_trades.empty else 0
    
    # Profit factor
    gross_profit = win_trades.sum() if not win_trades.empty else 0
    gross_loss = abs(loss_trades.sum()) if not loss_trades.empty else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    
    # Sharpe ratio (geannualiseerd)
    strat_returns = df["strategy_return"].dropna()
    sharpe_ratio = (strat_returns.mean() / strat_returns.std()) * np.sqrt(252) if strat_returns.std() > 0 else 0
    
    # --- GEOPTIMALISEERDE TRADE LENGTE BEREKENING ---
    # Tel alleen de dagen per trade_id waar de positie daadwerkelijk 1 is geweest
    active_trades = df[df['trade_id'] != 0]
    if not active_trades.empty:
        trade_lengths = active_trades[active_trades['position'] == 1].groupby('trade_id').size()
        gem_trade_lengte = trade_lengths.mean() if not trade_lengths.empty else 0
    else:
        gem_trade_lengte = 0
    
    # Drawdowns
    max_dd_strat = df["drawdown"].min()
    bh_peak = df["buy_and_hold_growth"].cummax()
    max_dd_bh = ((df["buy_and_hold_growth"] - bh_peak) / bh_peak).min()


    # Overzicht samenstellen
    stats = {
        "Start": df.index[0],
        "Einde": df.index[-1],
        "Aantal Trades": aantal_trades,
        "Win Percentage": f"{win_pct:.2%}",
        "Profit Factor": f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "Inf",
        "Sharpe Ratio": f"{sharpe_ratio:.2f}",
        "Total Return Strat": f"{df['strategy_growth'].iloc[-1] - 1:.2%}",
        "Total Return Buy & Hold": f"{df['buy_and_hold_growth'].iloc[-1] - 1:.2%}",
        "Gem. Return / Trade": f"{trades.mean():.2%}",
        "Gem. Win": f"{gem_win:.2%}",
        "Gem. Loss": f"{gem_loss:.2%}",
        "Gem. Trade Lengte": f"{gem_trade_lengte:.1f} dagen",
        "Market Exposure": f"{df['position'].mean():.1%}",
        "Max Drawdown Strat": f"{max_dd_strat:.2%}",
        "Max Drawdown B&H": f"{max_dd_bh:.2%}"
    }
    
    
    # Omzetten naar DataFrame, "Metric" als index instellen en de waarde-kolom een naam geven (bijv. "Value")
    df_stats_res = pd.DataFrame(list(stats.items()), columns=["Metric", "Value"]).set_index("Metric")
    
    return df_stats_res
    #return pd.Series(stats)

#%% trade log maken per individuele trade
def calculate_trade_log(CONFIG, df):
    """
    input:
        CONFIG en df met 'trade_id', 'position', 'close', 'strategy_growth' etc.
    output:
        DataFrame met per trade een overzicht van entry, exit, prijzen, return en duur
    """
    trades = []
    
    # Groepeer op unieke trade_id (negeer trade_id 0 wat 'geen positie' is)
    grouped = df[df['trade_id'] != 0].groupby('trade_id')
    
    for trade_id, group in grouped:
        entry_date = group.index[0]
        exit_date = group.index[-1]
        
        entry_price = group['close'].iloc[0]
        exit_price = group['close'].iloc[-1]
        
        # Rendement van deze specifieke trade (inclusief fees die in de pipeline zijn verwerkt)
        trade_return = (group['strategy_growth'].iloc[-1] / group['strategy_growth'].iloc[0]) - 1
        
        # Aantal dagen dat de trade duurde
        duration = len(group)
        
        trades.append({
            "trade_id": trade_id,
            "entry_date": entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else entry_date,
            "exit_date": exit_date.strftime('%Y-%m-%d') if hasattr(exit_date, 'strftime') else exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return": f"{trade_return:.2%}",
            "duration_days": duration
        })
        
    return pd.DataFrame(trades)

#%%
if __name__ == "__main__":
    from data_import import df_btc
    import backtest_engine as backtest

    # config obv kolom logica: de 'maak_regel' maakt een lambda functie
    CONFIG = {
        # backtest datum
        'date_min':'2018-01-31',
        'date_max':'2035-12-30',
        
        # pct fee per trade (0.001 = 0.1%; None voor geen fee)
        "fee": 0.001,
        
        # sl en tp in pct (0.30 = 30%; None geen sl/tp)
        "stop_loss_pct": None,  
        "take_profit_pct": None, 
        "max_holding_period": 300,
        
        # backtest regels
        "rules": {
            "buy": backtest.maak_regel("RSI_14", ">", 60),
            "sell": backtest.maak_regel("RSI_14", "<", 40),
        }
    }

    # apply backtest engine to df and config
    result = backtest.run_pipeline(CONFIG = CONFIG,
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
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    