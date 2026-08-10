

# start door in console te typen: "!streamlit run app.py --server.headless true"
#%%
"""
Streamlit App voor Backtester (Centrale Layout & Scrollbare Resultaten)
"""

import os
import streamlit as st
import plotly_plots
import pandas as pd

# Zorg dat de werkmap correct staat
os.chdir(os.path.dirname(os.path.abspath(__file__)))
#%%
from data_import import df_btc
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log

# Pagina instellingen
st.set_page_config(page_title="Crypto Backtester", layout="wide")

st.title("Backtester")
st.write("Pas hieronder de `CONFIG` dictionary aan en voer de backtest uit.")

# --- CENTRALE CONFIG EDITOR (In het midden / brede weergave) ---
st.subheader("⚙️ Python CONFIG Editor")

default_config_text = """{
    'date_min': '2018-01-31',       # Startdatum van de backtest (YYYY-MM-DD)
    'date_max': '2035-12-30',       # Einddatum van de backtest (YYYY-MM-DD)
    
    "fee": 0.001,                   # Transactiekosten per trade (0.001 = 0.1%)
    "stop_loss_pct": None,          # Stop loss percentage (bijv. 0.05 voor 5% verlies, of None)
    "take_profit_pct": None,        # Take profit percentage (bijv. 0.15 voor 15% winst, of None)
    "max_holding_period": None,     # Maximaal aantal dagen dat een trade open mag staan (of None)
    
    "rules": {
        "buy": backtest.maak_regel("RSI_14", ">", 60),  # Koopsignaal: koopt als RSI_14 groter is dan 60
        "sell": backtest.maak_regel("RSI_14", "<", 40), # Verkoopsignaal: verkoopt als RSI_14 kleiner is dan 40
    }
}"""

# Groot tekstvak in de hoofdsectie van de pagina
config_input = st.text_area("Bewerk CONFIG", value=default_config_text, height=300)

run_button = st.button("Voer Backtest Uit", type="primary")

st.markdown("---")

# --- UITVOEREN EN RESULTATEN (Scroll naar beneden om te bekijken) ---
if run_button:
    try:
        # Veilig de ingetypte tekst evalueren als Python dictionary
        namespace = {"backtest": backtest, "None": None}
        CONFIG = eval(config_input, namespace)

        # Pipeline en stats draaien
        df_final = backtest.run_pipeline(CONFIG=CONFIG, df=df_btc)
        df_stats = calculate_summary_stats(df_final, CONFIG=CONFIG)
        trade_log = calculate_trade_log(CONFIG = CONFIG, df = df_final)

        # Resultaten onder elkaar weergeven
        st.subheader("Stats")
        st.dataframe(df_stats.astype(str), use_container_width=True)
        
        # 2. Plotly Grafieken toevoegen
        st.subheader("Strategy vs Buy & Hold")
        fig_perf = plotly_plots.plot_performance(df_final)
        st.plotly_chart(fig_perf, use_container_width=True)
        
        st.subheader("Drawdowns")
        fig_perf = plotly_plots.plot_drawdowns(df_final)
        st.plotly_chart(fig_perf, use_container_width=True)
        
        st.subheader("Trade Logs")
        st.dataframe(trade_log, use_container_width=True, height=300)

        st.subheader("Backtest DataFrame")
        st.dataframe(df_final, use_container_width=True, height=300)

    except Exception as e:
        st.error(f"Fout in CONFIG syntax of uitvoering: {e}")
else:
    st.info("👆 Pas de CONFIG hierboven aan en klik op **Voer Backtest Uit** om de resultaten hieronder te bekijken.")
    
    
    
    
    
    
