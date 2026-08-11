"""
Streamlit App voor Backtester (Centrale Layout & Scrollbare Resultaten)
"""

import os
import streamlit as st
import plotly_plots
from datetime import datetime

# Zorg dat de werkmap correct staat
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from data_import import df_btc
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log

# Genereer een timestamp (bijv. "2026-06-06_14-30-00")
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Pagina instellingen
st.set_page_config(page_title="Crypto Backtester", layout="wide")

st.title("Backtester")
st.write("Pas hieronder de `CONFIG` dictionary aan en voer de backtest uit.")

# --- CENTRALE CONFIG & STATS LAYOUT (Naast elkaar) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("⚙️ Python CONFIG Editor")
    default_config_text = """{
    'date_min':'2020-01-31',
    'date_max':'2035-12-30',
    
    "fee": 0.001,
    "stop_loss_pct": None,
    "take_profit_pct": None,
    "max_holding_period": None,
    
    "rules": {
            "buy": [
                backtest.maak_regel("RSI_14", "<", 40),
                backtest.maak_regel("SMA_50", ">", "SMA_200"),
            ],
            "sell": [
                backtest.maak_regel("RSI_14", ">", 70)
            ]
    }
}"""
    config_input = st.text_area("Bewerk CONFIG", value=default_config_text, height=520)
    run_button = st.button("Voer Backtest Uit", type="primary")

with col2:
    st.subheader("📊 Stats")
    # Placeholder zodat de stats netjes in de rechterkolom laden na de klik
    stats_placeholder = st.empty()
    
    if not run_button:
        stats_placeholder.info("Klik op **Voer Backtest Uit** om de stats hier te tonen.")

st.markdown("---")

# --- UITVOEREN EN OVERIGE RESULTATEN (Onder elkaar) ---
if run_button:
    try:
        # Veilig de ingetypte tekst evalueren als Python dictionary
        namespace = {"backtest": backtest, "None": None}
        CONFIG = eval(config_input, namespace)

        # Pipeline en stats draaien
        df_final = backtest.run_pipeline(CONFIG=CONFIG, df=df_btc)
        df_stats = calculate_summary_stats(df_final, CONFIG=CONFIG)
        trade_log = calculate_trade_log(CONFIG=CONFIG, df=df_final)
        
        # Plaats de stats in de rechterkolom
        with stats_placeholder.container():
            st.dataframe(df_stats.astype(str), use_container_width=True, height=580)
        
        # --- AUTOMATISCH INDICATOREN OPHALEN UIT CONFIG (Zonder checkboxes) ---
        gebruikte_indicatoren = backtest.extract_indicators_from_config(CONFIG, df_btc.columns)

        # Plotly Grafieken onder elkaar toevoegen
        st.subheader("Performance Grafiek")
        fig_perf = plotly_plots.plot_performance(df_final, extra_columns=gebruikte_indicatoren)
        st.plotly_chart(fig_perf, use_container_width=True)
        
        st.subheader("Drawdown Grafiek")
        fig_dd = plotly_plots.plot_drawdowns(df_final)
        st.plotly_chart(fig_dd, use_container_width=True)
        
        # Resterende tabellen onder elkaar
        st.subheader("Trade Logs")
        st.dataframe(trade_log, use_container_width=True, height=300)

        st.subheader("Backtest DataFrame")
        st.dataframe(df_final, use_container_width=True, height=300)
        
        # Download resultaat
        rapport_lijst = [
            "=== GEBRUIKTE CONFIG ===",
            config_input,  
            "",
            "=== STATS ===",
            df_stats.to_csv(header=True),
            "",
            "=== TRADE LOGS ===",
            trade_log.to_csv(index=False)
        ]
        
        volledige_export = "\n".join(rapport_lijst)

        st.download_button(
            label="📥 Download resultaat als CSV",
            data=volledige_export.encode('utf-8'),
            file_name=f'trade_logs_{timestamp}.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"Fout in CONFIG syntax of uitvoering: {e}")