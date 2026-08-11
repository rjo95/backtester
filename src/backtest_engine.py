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


#%% def current position based on rules
def current_position(CONFIG, df):
    data = df.copy()
    
    # --- MEERDERE REGELS AFHANDELEN ---
    buy_rules = CONFIG["rules"]["buy"]
    sell_rules = CONFIG["rules"]["sell"]
    
    # Als buy_rules een enkele functie is (voor backwards compatibility), maak er een lijst van
    if not isinstance(buy_rules, list):
        buy_rules = [buy_rules]
    if not isinstance(sell_rules, list):
        sell_rules = [sell_rules]
        
    # Evalueer alle koopregels en combineer ze met een 'AND' (&)
    buy_series = pd.Series(True, index=data.index)
    for rule in buy_rules:
        buy_series = buy_series & rule(data)
    data['buy_signal'] = buy_series

    # Evalueer alle verkoopregels en combineer ze met een 'AND' (&)
    sell_series = pd.Series(True, index=data.index)
    for rule in sell_rules:
        sell_series = sell_series & rule(data)
    data['sell_signal'] = sell_series
    # ----------------------------------

    sl_pct = CONFIG.get("stop_loss_pct", None)
    tp_pct = CONFIG.get("take_profit_pct", None)
    max_holding = CONFIG.get("max_holding_period", None)

    position = []
    current_pos = 0  
    entry_price = 0.0
    days_in_trade = 0  

    for i in range(len(data)):
        price = data["close"].iloc[i]
        
        if current_pos == 1:
            days_in_trade += 1  
            exit_triggered = False
            
            if sl_pct is not None and price <= entry_price * (1 - sl_pct):
                exit_triggered = True
            elif tp_pct is not None and price >= entry_price * (1 + tp_pct):
                exit_triggered = True
            elif max_holding is not None and days_in_trade >= max_holding:
                exit_triggered = True
            elif data["sell_signal"].iloc[i]:
                exit_triggered = True
                
            if exit_triggered:
                current_pos = 0
                entry_price = 0.0
                days_in_trade = 0  
                
        elif current_pos == 0:
            if data["buy_signal"].iloc[i]:
                current_pos = 1
                entry_price = price  
                days_in_trade = 0    
                
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

#%%
def maak_regel(links, operator, rechts):
    """
    Bouwt dynamisch een regel op en plakt de links/rechts variabelen 
    direct vast aan de functie zodat we ze later kunnen uitlezen.
    """
    def evalueer_kant(df, item):
        if isinstance(item, str) and item in df.columns:
            return df[item]
        return item

    if operator == "==":
        func = lambda df: evalueer_kant(df, links) == evalueer_kant(df, rechts)
    elif operator == "<":
        func = lambda df: evalueer_kant(df, links) < evalueer_kant(df, rechts)
    elif operator == ">":
        func = lambda df: evalueer_kant(df, links) > evalueer_kant(df, rechts)  
    elif operator == "<=":
        func = lambda df: evalueer_kant(df, links) <= evalueer_kant(df, rechts)
    elif operator == ">=":
        func = lambda df: evalueer_kant(df, links) >= evalueer_kant(df, rechts)
    else:
        raise ValueError(f"Onbekende operator: {operator}")
    
    # Hier slaan we de variabelen op de functie op!
    func.links = links
    func.rechts = rechts
    
    return func

#%%
def extract_indicators_from_config(config, available_columns):
    """
    Haalt automatisch alle unieke kolomnamen op uit de CONFIG regels.
    """
    kolommen = set()
    rules_dict = config.get("rules", {})
    
    for actie in ["buy", "sell"]:
        rule_block = rules_dict.get(actie, [])
        
        # Ondersteun zowel lijsten als dicts met "logic"
        if isinstance(rule_block, dict):
            rule_list = rule_block.get("rules", [])
        else:
            rule_list = rule_block if isinstance(rule_block, list) else [rule_block]
            
        for rule in rule_list:
            if hasattr(rule, 'links') and isinstance(rule.links, str) and rule.links in available_columns:
                kolommen.add(rule.links)
            if hasattr(rule, 'rechts') and isinstance(rule.rechts, str) and rule.rechts in available_columns:
                kolommen.add(rule.rechts)
                
    return list(kolommen)

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
            
            # rules
            "rules": {
                "buy": [
                        maak_regel("RSI_14", "<", 40),      
                        maak_regel("SMA_50", ">", "SMA_200"),  
                        ],
                
                "sell": [
                        maak_regel("RSI_14", ">", 70),
                        ]
                }
            }
    
    # apply backtest engine to df and config
    result = run_pipeline(CONFIG = CONFIG,
                          df = df_btc)
    
    # show result
    print(result.head())


