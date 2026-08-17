"""
Hoofdscript voor backtester
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__))) # wd = bestandslocatie


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


#%% regel maken met kolom of waarde
def create_rule(links, operator, rechts):
    """
    Kan zowel links als rechts een kolomnaam (string) of een getal/waarde gebruiken.
    Voorbeeld: maak_regel("SMA_5", "<", "SMA_10") of maak_regel("RSI_14", "<", 50)
    """
    def evalueer_kant(df, item):
        # Als het item een string is én bestaat als kolom in de dataframe, pak dan die kolomdata
        if isinstance(item, str) and item in df.columns:
            return df[item]
        # Anders is it gewoon een vaste waarde (getal, string, boolean, etc.)
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
    
    # Sla attributen op zodat je ze eventueel kunt inzien
    func.links = links
    func.operator = operator
    func.rechts = rechts
    
    return func

#%%
df_btc['buy_signal'] == rule




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



