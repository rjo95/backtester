"""
Hoofdscript voor backtester
"""
import pandas as pd
import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie


#%% filter op datum
def filter_date(CONFIG, df):
    
    # copy df
    data = df.copy()
    
    # indien nodig datum omzetten naar pandas datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        data = data.copy()
        data.index = data.to_datetime(df.index)
        
    # filter df op datum range uit CONFIG
    data = df[ CONFIG['date_min'] : CONFIG['date_max'] ]
    
    return data


#%% in positie kolom (inclusief Stop Loss, Take Profit én Max Holding Period)
def current_position(CONFIG, df):
    """
    input:
        CONFIG met regels, optionele stop_loss_pct, take_profit_pct, max_holding_period en df
    output:
        df met position kolom
    """
    data = df.copy()
    
    # Signalen ophalen
    data['buy_signal'] = CONFIG["rules"]["buy"](data)
    data['sell_signal'] = CONFIG["rules"]["sell"](data)

    sl_pct = CONFIG.get("stop_loss_pct", None)
    tp_pct = CONFIG.get("take_profit_pct", None)
    max_holding = CONFIG.get("max_holding_period", None)

    position = []
    current_pos = 0  # 0=geen positie; 1=long
    entry_price = 0.0
    days_in_trade = 0  # Houdt bij hoeveel dagen de trade open staat

    for i in range(len(data)):
        price = data["close"].iloc[i]
        
        # ALS WE IN DE MARKT ZITTEN (1)
        if current_pos == 1:
            days_in_trade += 1  # Verhoog de teller elke dag dat we open staan
            exit_triggered = False
            
            # 1. Check Stop Loss
            if sl_pct is not None and price <= entry_price * (1 - sl_pct):
                exit_triggered = True
                
            # 2. Check Take Profit
            elif tp_pct is not None and price >= entry_price * (1 + tp_pct):
                exit_triggered = True
                
            # 3. Check Max Holding Period (bijv. max 30 dagen open)
            elif max_holding is not None and days_in_trade >= max_holding:
                exit_triggered = True
                
            # 4. Check normaal Verkoop-signaal
            elif data["sell_signal"].iloc[i]:
                exit_triggered = True
                
            # Als er een exit plaatsvindt
            if exit_triggered:
                current_pos = 0
                entry_price = 0.0
                days_in_trade = 0  # Reset de teller
                
        # ALS WE NIET IN DE MARKT ZITTEN (0)
        elif current_pos == 0:
            if data["buy_signal"].iloc[i]:
                current_pos = 1
                entry_price = price  # Sla de nieuwe instapprijs op
                days_in_trade = 0    # Start de teller op 0 voor de nieuwe trade
                
        position.append(current_pos)

    data["position"] = position
    return data
#%% return kolommen
def calculate_returns(CONFIG, df):
    """
    input:
        df met 'position' kolom
    output:
        df met return kolommen obv 'position' kolom
    """
    # copy df
    data = df.copy()
    
    # Dagelijkse rendement
    data["market_return"] = data["close"].pct_change()

    # Strategy return volgt de positie van de *vorige* dag; want positie opent/sluit op close
    data["strategy_return"] = data["market_return"] * data["position"].shift(1)
    
    
    # fee verwerking (gebruik .get() om een KeyError te voorkomen als 'fee' ontbreekt in CONFIG)
    fee = CONFIG.get('fee', 0.0)
    
    if fee > 0:
        # Stap A: Zoek alle rijen waar de positie verandert (0->1 of 1->0)
        # We negeren de eerste NaN via .notna()
        trade_occurred = (data["position"] != data["position"].shift(1)) & (data["position"].shift(1).notna())
        
        # Stap B: Trek de fee af op exact die datums
        # Omdat het een percentage van het totale vermogen is, trek je 'fee' direct af van de return op die dag.
        data.loc[trade_occurred, "strategy_return"] -= fee
        
    return data

#%% stats kolommen
def calculate_stats(CONFIG, df):
    """
    input:
        df met 'position' kolom
    output:
        df met return kolommen obv 'position' kolom
    """
    # copy df
    data = df.copy()
        
    # Maak kolommen om individuele trades bij te houden
    data["trade_id"] = (
                        (data["position"] == 1) & (data["position"].shift(1) == 0)
                        ).cumsum()
       
    # Bereken de cumulatieve groei
    data["strategy_growth"] = (1 + data["strategy_return"].fillna(0)).cumprod()
       
    # Bereken de piek tot nu toe
    data["peak"] = data["strategy_growth"].cummax()
       
    # Bereken de drawdown per dag
    data["drawdown"] = (data["strategy_growth"] - data["peak"]) / data["peak"]
       
    # Bereken de buy & hold groei
    data["buy_and_hold_growth"] = (1 + data["market_return"].fillna(0)).cumprod()

    return data

#%% run alle defs voor backtest proces
def run_pipeline(CONFIG, df):
    # copy
    data = df.copy()
    
    # filter df op datum uit CONFIG
    data = filter_date(CONFIG=CONFIG, df=data)
    
    # positie kolommen obv CONFIG rules
    data = current_position(CONFIG=CONFIG, df=data)
    
    # returns berekenen obv in/uit positie
    data = calculate_returns(CONFIG=CONFIG, df=data)
    
    # statistieken berekenen
    data = calculate_stats(CONFIG=CONFIG, df=data)
    
    return data

#%% lambda creator voor in CONFIG
def maak_regel(kolom, operator, waarde):
    """
    Bouwt dynamisch een functie op basis van simpele argumenten.
    """
    if operator == "==":
        return lambda df: df[kolom] == waarde
    elif operator == "<":
        return lambda df: df[kolom] < waarde
    elif operator == ">":
        return lambda df: df[kolom] > waarde  
    elif operator == "<=":
        return lambda df: df[kolom] <= waarde
    elif operator == ">=":
        return lambda df: df[kolom] >= waarde
    else:
        raise ValueError(f"Onbekende operator: {operator}")
        

#%% voorbeeld
if __name__ == "__main__":
    
    # import df
    from data_import import df_btc
    
    # show columns
    print(df_btc.columns)

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
        
        "rules": {
                "buy": maak_regel("RSI_14", "<", 50),
                "sell": maak_regel("RSI_14", ">", 50),
                }
    }
    
    # apply backtest engine to df and config
    result = run_pipeline(CONFIG = CONFIG,
                          df = df_btc)
    
    # show result
    print(result.head())


