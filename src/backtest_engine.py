"""
Hoofdscript voor backtester (gecorrigeerd)
"""
import pandas as pd
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))  # wd = bestandslocatie


#%% filter op datum
def filter_date(CONFIG, df):
    # copy df
    data = df.copy()

    # indien nodig datum omzetten naar pandas datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)

    # FIX: filter moet op 'data' worden toegepast, niet op de originele 'df'.
    # In de oude versie werd de datetime-conversie genegeerd en werd er
    # gefilterd op de ongewijzigde 'df', wat de conversie zinloos maakte.
    data = data[CONFIG['date_min']: CONFIG['date_max']]

    return data


#%% Pipeline stap om de indicatoren daadwerkelijk uit te voeren
"""
def add_indicators(CONFIG, df):
    data = df.copy()

    indicators = CONFIG.get("indicators", [])

    # Verwacht een lijst van tuples: ("RSI_6", ind_module.rsi, 6)
    for kolnaam, func, *args in indicators:
        res = func(data, *args)

        if isinstance(res, pd.Series):
            data[kolnaam] = res
        elif isinstance(res, pd.DataFrame):
            for col in res.columns:
                data[col] = res[col]

        if kolnaam in data.columns:
            data[kolnaam] = pd.to_numeric(data[kolnaam], errors='coerce')

    return data
"""

def add_indicators(CONFIG, df):
    data = df.copy()
    indicators = CONFIG.get("indicators", [])

    for kolnaam, func, *args in indicators:
        # We geven 'name=kolnaam' expliciet mee als keyword argument
        # Dit overrulet de standaardnaam in de indicator-functie
        data = func(data, *args, name=kolnaam)

    return data

#%% def current position based on rules (met tuples ipv lambda's)
def current_position(CONFIG, df):
    data = df.copy()

    buy_rules = CONFIG["rules"].get("buy", [])
    sell_rules = CONFIG["rules"].get("sell", [])

    if not isinstance(buy_rules, list):
        buy_rules = [buy_rules]
    if not isinstance(sell_rules, list):
        sell_rules = [sell_rules]

    # Hulpfunctie om te kijken of een waarde een kolomnaam is of een vaste waarde
    def evalueer_kant(d, item):
        if isinstance(item, str) and item in d.columns:
            return d[item]
        return item

    # Hulpfunctie om een regel-tuple om te zetten in een boolean Series
    def evalueer_regel(d, regel):
        links, operator, rechts = regel
        l_val = evalueer_kant(d, links)
        r_val = evalueer_kant(d, rechts)

        if operator == "==":
            return l_val == r_val
        elif operator == "<":
            return l_val < r_val
        elif operator == ">":
            return l_val > r_val
        elif operator == "<=":
            return l_val <= r_val
        elif operator == ">=":
            return l_val >= r_val
        else:
            raise ValueError(f"Onbekende operator: {operator}")

    # Evalueer alle koopregels en combineer ze met een 'AND' (&)
    if buy_rules:
        buy_series = pd.Series(True, index=data.index)
        for regel in buy_rules:
            buy_series = buy_series & evalueer_regel(data, regel)
    else:
        # FIX: geen buy-regels -> nooit kopen (was voorheen ook al correct
        # door de True-startwaarde, maar expliciet gemaakt voor consistentie).
        buy_series = pd.Series(False, index=data.index)
    data['buy_signal'] = buy_series

    # Evalueer alle verkoopregels en combineer ze met een 'AND' (&)
    if sell_rules:
        sell_series = pd.Series(True, index=data.index)
        for regel in sell_rules:
            sell_series = sell_series & evalueer_regel(data, regel)
    else:
        # FIX: dit was de belangrijkste bug. Bij een lege sell_rules-lijst
        # bleef sell_series overal True (identiteit van AND), waardoor
        # elke positie de volgende dag alweer verkocht werd. Zonder
        # sell-regels moet er juist nooit (op basis van regels) verkocht
        # worden, tenzij stop-loss/take-profit/max_holding ingrijpt.
        sell_series = pd.Series(False, index=data.index)
    data['sell_signal'] = sell_series

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
    data = df.copy()

    # Dagelijkse rendement
    data["market_return"] = data["close"].pct_change()

    # Strategy return volgt de positie van de *vorige* dag
    data["strategy_return"] = data["market_return"] * data["position"].shift(1)

    fee = CONFIG.get('fee', 0.0)

    if fee > 0:
        # Fee wordt verrekend op de dag dat de positie daadwerkelijk wisselt
        # (entry of exit). Dit is de dag waarop de transactiekost ontstaat,
        # ongeacht of het rendement die dag al de nieuwe positie weerspiegelt.
        trade_occurred = (data["position"] != data["position"].shift(1)) & (data["position"].shift(1).notna())
        data.loc[trade_occurred, "strategy_return"] = data.loc[trade_occurred, "strategy_return"].fillna(0) - fee

    return data


#%% stats kolommen
def calculate_stats(CONFIG, df):
    data = df.copy()

    data["trade_id"] = ((data["position"] == 1) & (data["position"].shift(1) == 0)).cumsum()
    data["strategy_growth"] = (1 + data["strategy_return"].fillna(0)).cumprod()
    data["peak"] = data["strategy_growth"].cummax()
    data["drawdown"] = (data["strategy_growth"] - data["peak"]) / data["peak"]
    data["buy_and_hold_growth"] = (1 + data["market_return"].fillna(0)).cumprod()

    return data


#%% run alle defs voor backtest proces
def run_pipeline(CONFIG, df):
    data = df.copy()

    # Indicatoren toevoegen vanuit de CONFIG (vóór date-filter, zodat
    # indicatoren met een lookback-periode ook data van vóór date_min
    # kunnen gebruiken voor hun opwarmperiode)
    data = add_indicators(CONFIG=CONFIG, df=data)

    # filter df op datum uit CONFIG
    data = filter_date(CONFIG=CONFIG, df=data)

    # positie kolommen obv CONFIG rules
    data = current_position(CONFIG=CONFIG, df=data)

    # returns berekenen obv in/uit positie
    data = calculate_returns(CONFIG=CONFIG, df=data)

    # statistieken berekenen
    data = calculate_stats(CONFIG=CONFIG, df=data)

    return data


#%% voorbeeld
if __name__ == "__main__":

    # import df
    from data_import import df_sp500
    import indicators as ind_module

    df = df_sp500

    CONFIG = {
        # start en einddatum test
        'date_min': '1920-01-31',
        'date_max': '2035-12-30',

        # fee in pct
        "fee": 0.002,

        # sl en tp in pct
        "stop_loss_pct": None,
        "take_profit_pct": None,
        "max_holding_period": None,

        # add indicators
        "indicators": [
            ("RSI_6", ind_module.rsi, 6),
            ("TSM_90", ind_module.time_series_momentum_days, 90),
        ],

        # rules (nu direct als nette tuples opgegeven)
        "rules": {
            "buy": [
                ("RSI_6", "<", 30),
                ("TSM_90", "==", 1),
            ],

            "sell": [
                ("RSI_6", ">", 70),
            ]
        }
    }

    # apply backtest engine to df and config
    result = run_pipeline(CONFIG=CONFIG, df=df)

    # show result
    print(result.head())

    # show columns
    print(result.columns)