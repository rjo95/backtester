#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  9 15:06:09 2026

@author: roy
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

#%%
def plot_performance(result_df, extra_columns=None):
    if extra_columns is None:
        extra_columns = []

    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05,
        row_heights=[0.5, 0.5],
        subplot_titles=("Strategy vs Buy & Hold", "Price, Trades & Indicators")
    )
    
    # 1. Cumulatieve groei grafiek (Bovenste subgrafiek)
    fig.add_trace(
        go.Scatter(x=result_df.index, y=result_df["strategy_growth"], name="Strategy Growth", line=dict(color="blue")),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=result_df.index, y=result_df["buy_and_hold_growth"], name="Buy & Hold", line=dict(color="orange")),
        row=1, col=1
    )
    
    # 2. Onderste grafiek: Prijs en in/uit positie markers
    fig.add_trace(
        go.Scatter(x=result_df.index, y=result_df["close"], name="Close Price", line=dict(color="gray", width=1)),
        row=2, col=1
    )
    
    # --- AANGEVINKTE INDICATOREN TOEVOEGEN AAN ONDERSTE GRAFIEK ---
    for col in extra_columns:
        if col in result_df.columns:
            fig.add_trace(
                go.Scatter(x=result_df.index, y=result_df[col], name=col, line=dict(dash='dash')),
                row=2, col=1
            )
    # -------------------------------------------------------------
    
    # Koopmomenten markeren
    buy_signals = result_df[(result_df["position"] == 1) & (result_df["position"].shift(1) == 0)]
    fig.add_trace(
        go.Scatter(x=buy_signals.index, y=buy_signals["close"], mode="markers", 
                   marker=dict(symbol="triangle-up", color="green", size=10), name="Buy Signal"),
        row=2, col=1
    )
    
    # Verkoopmomenten markeren
    sell_signals = result_df[(result_df["position"] == 0) & (result_df["position"].shift(1) == 1)]
    fig.add_trace(
        go.Scatter(x=sell_signals.index, y=sell_signals["close"], mode="markers", 
                   marker=dict(symbol="triangle-down", color="red", size=10), name="Sell Signal"),
        row=2, col=1
    )
    
    fig.update_layout(height=700, template="plotly_white", hovermode="x unified")
    
    return fig

#%%
def plot_drawdowns(result_df):
    # Bereken optioneel ook de drawdown voor buy & hold voor een eerlijke vergelijking
    bh_peak = result_df["buy_and_hold_growth"].cummax()
    bh_drawdown = (result_df["buy_and_hold_growth"] - bh_peak) / bh_peak
    
    fig = go.Figure()
    
    # Strategy drawdown
    fig.add_trace(go.Scatter(
        x=result_df.index, 
        y=result_df["drawdown"] * 100, # naar percentages
        name="Strategy Drawdown",
        fill='tozeroy',
        line=dict(color='rgba(255, 0, 0, 0.6)')
    ))
    
    # Buy & Hold drawdown ter referentie
    fig.add_trace(go.Scatter(
        x=result_df.index, 
        y=bh_drawdown * 100, 
        name="Buy & Hold Drawdown",
        fill='tozeroy',
        line=dict(color='rgba(128, 128, 128, 0.4)')
    ))
    
    fig.update_layout(
        title="Drawdown (%)",
        xaxis_title="Datum",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        hovermode="x unified"
    )
    
    return fig


#%%
if __name__ == "__main__":
    from data_import import df_btc
    import backtest_engine as backtest
    import plotly.io as pio
    pio.renderers.default = "browser"

    # config voor backtest
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
            "buy": backtest.maak_regel("RSI_14", ">", 50),
            "sell": backtest.maak_regel("RSI_14", "<", 50),
        }
    }

    # backtest resultaat in df
    result = backtest.run_pipeline(CONFIG = CONFIG,
                                   df = df_btc)

    # backtest df als input voor plot
    plot_performance(result).show()
    plot_drawdowns(result).show()
    
    

#%%














