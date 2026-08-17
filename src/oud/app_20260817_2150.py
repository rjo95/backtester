"""
Streamlit App voor Backtester
- Simpele modus: indicatoren en regels bouwen via tabellen met expliciete
  toevoegen/verwijderen-knoppen
- Geavanceerde modus: CONFIG direct als Python dict bewerken (zoals voorheen)
"""

# !streamlit run app.py --server.headless true

import os
import pprint
import pandas as pd
import streamlit as st
import plotly_plots
from datetime import datetime

# Zorg dat de werkmap correct staat
os.chdir(os.path.dirname(os.path.abspath(__file__)))

#%%
from data_import import df_btc
import indicators as ind
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

st.set_page_config(page_title="Crypto Backtester", layout="wide")

st.title("Backtester")


# ============================================================
# REGISTRY: welke indicatoren zijn beschikbaar in de builder
# (donchian_channels heeft 2 outputkolommen en is bewust
#  uitgesloten van de simpele builder; gebruik daarvoor de
#  geavanceerde modus)
# ============================================================
INDICATOR_REGISTRY = {
    "SMA – Simple Moving Average":   {"func": ind.sma,                        "needs_n": True,  "prefix": "SMA",           "default_n": 50},
    "RSI – Relative Strength Index": {"func": ind.rsi,                        "needs_n": True,  "prefix": "RSI",           "default_n": 14},
    "TSM – Time Series Momentum":    {"func": ind.time_series_momentum_days,  "needs_n": True,  "prefix": "TSM",           "default_n": 90},
    "CLV – Close Location Value":    {"func": ind.close_location_value,       "needs_n": False, "prefix": "CLV",           "default_n": None},
    "Return Z-Score":                {"func": ind.return_zscore,              "needs_n": True,  "prefix": "Return_ZScore", "default_n": 20},
    "ATR – Average True Range":      {"func": ind.atr,                        "needs_n": True,  "prefix": "ATR",           "default_n": 14},
}

OPERATORS = ["<", ">", "<=", ">=", "=="]

BASE_COLUMNS = sorted(df_btc.columns.tolist())

INDICATORS_COLUMNS = ["Verwijderen", "Indicator", "Periode", "Naam", "Plot op grafiek"]
RULES_COLUMNS = ["Verwijderen", "Kolom", "Operator", "Vergelijk met"]


def default_indicators_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Indicator": "RSI – Relative Strength Index", "Periode": 14, "Naam": "RSI_14", "Plot op grafiek": True},
        {"Verwijderen": False, "Indicator": "SMA – Simple Moving Average", "Periode": 100, "Naam": "SMA_100", "Plot op grafiek": True},
        {"Verwijderen": False, "Indicator": "SMA – Simple Moving Average", "Periode": 200, "Naam": "SMA_200", "Plot op grafiek": True},
    ], columns=INDICATORS_COLUMNS)


def default_buy_rules_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Kolom": "days_until_halving", "Operator": "<", "Vergelijk met": "600"},
    ], columns=RULES_COLUMNS)


def default_sell_rules_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Kolom": "days_until_halving", "Operator": "<", "Vergelijk met": "960"},
        {"Verwijderen": False, "Kolom": "days_until_halving", "Operator": ">", "Vergelijk met": "900"},
    ], columns=RULES_COLUMNS)


def editable_table(session_key, default_df_func, column_config, column_order, delete_button_label):
    """Toont een data_editor met expliciete 'verwijder aangevinkte rijen'-knop.
    Rijen toevoegen kan via de '+' onderaan de tabel (num_rows='dynamic')."""
    if session_key not in st.session_state:
        st.session_state[session_key] = default_df_func()

    edited_df = st.data_editor(
        st.session_state[session_key],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{session_key}_editor",
        column_config=column_config,
        column_order=column_order,
    )
    st.session_state[session_key] = edited_df

    bcol1, bcol2 = st.columns([1, 4])
    with bcol1:
        if st.button(f"🗑️ {delete_button_label}", key=f"{session_key}_delete_btn"):
            df = st.session_state[session_key]
            if "Verwijderen" in df.columns:
                st.session_state[session_key] = df[~df["Verwijderen"].fillna(False)].reset_index(drop=True)
            st.rerun()

    return st.session_state[session_key]


def build_indicators_list(indicators_df: pd.DataFrame):
    """Zet de indicator-tabel om naar de tuple-lijst die backtest_engine verwacht,
    en geeft daarnaast terug welke kolomnamen op de grafiek geplot moeten worden."""
    indicators_list = []
    plot_names = []
    for _, row in indicators_df.iterrows():
        ind_key = row.get("Indicator")
        if not ind_key or ind_key not in INDICATOR_REGISTRY:
            continue
        entry = INDICATOR_REGISTRY[ind_key]
        func = entry["func"]
        prefix = entry["prefix"]

        if entry["needs_n"]:
            n = row.get("Periode")
            if pd.isna(n):
                continue
            n = int(n)
            naam = row.get("Naam") or f"{prefix}_{n}"
            indicators_list.append((naam, func, n))
        else:
            naam = row.get("Naam") or prefix
            indicators_list.append((naam, func))

        if bool(row.get("Plot op grafiek", True)):
            plot_names.append(naam)

    return indicators_list, plot_names


def build_rules(rules_df: pd.DataFrame):
    """Zet een regel-tabel om naar de tuple-lijst die backtest_engine verwacht.
    'Vergelijk met' mag een getal zijn (bv. 30) of een kolomnaam (bv. SMA_200)."""
    rules = []
    for _, row in rules_df.iterrows():
        kolom = row.get("Kolom")
        operator = row.get("Operator")
        waarde_raw = row.get("Vergelijk met")

        if not kolom or not operator or waarde_raw in (None, ""):
            continue

        try:
            waarde = float(waarde_raw)
        except (ValueError, TypeError):
            waarde = str(waarde_raw).strip()  # wordt behandeld als kolomnaam

        rules.append((kolom, operator, waarde))
    return rules


# ============================================================
# MODUS-KEUZE
# ============================================================
advanced_mode = st.toggle(
    "🔧 Geavanceerde modus (CONFIG direct als Python dict bewerken)",
    value=False,
    help="Zet dit aan als je iets wilt doen wat de builder hieronder niet ondersteunt "
         "(bv. Donchian channels, custom logica, etc.).",
)

CONFIG = None
config_display_text = None  # voor het downloadrapport
plot_names = []

if advanced_mode:
    # ---------------- GEAVANCEERDE MODUS (oude gedrag) ----------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚙️ Python CONFIG Editor")
        default_config_text = """{
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
            ("RSI_14", ind.rsi, 14),
            ("SMA_100", ind.sma, 100),
            ("SMA_200", ind.sma, 200),
        ],

        # rules
        "rules": {
            "buy": [
                ("days_until_halving", "<", 600),
                ],

            "sell": [
                ("days_until_halving", "<", 960),
                ("days_until_halving", ">", 900),
            ]
        }
    }"""
        config_input = st.text_area("Bewerk CONFIG", value=default_config_text, height=520)
        run_button = st.button("Voer Backtest Uit", type="primary")

    with col2:
        st.subheader("📊 Stats")
        stats_placeholder = st.empty()
        if not run_button:
            stats_placeholder.info("Klik op **Voer Backtest Uit** om de stats hier te tonen.")

    if run_button:
        try:
            namespace = {"backtest": backtest, "ind": ind, "None": None}
            CONFIG = eval(config_input, namespace)
            config_display_text = config_input
            plot_names = [item[0] for item in CONFIG.get("indicators", [])]
        except Exception as e:
            st.error(f"Fout in CONFIG syntax: {e}")
            CONFIG = None

else:
    # ---------------- SIMPELE MODUS (builder) ----------------
    stats_placeholder = st.empty()
    stats_placeholder.info("Vul de instellingen hieronder in en klik op **Voer Backtest Uit**.")

    with st.expander("📅 Basisinstellingen", expanded=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            date_min = st.date_input(
                "Startdatum", value=df_btc.index.min().date(),
                min_value=df_btc.index.min().date(), max_value=df_btc.index.max().date())
        with r1c2:
            date_max = st.date_input(
                "Einddatum", value=df_btc.index.max().date(),
                min_value=df_btc.index.min().date(), max_value=df_btc.index.max().date())
        with r1c3:
            fee_pct = st.number_input("Fee per trade (%)", value=0.2, min_value=0.0, step=0.05, format="%.3f")

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            use_sl = st.checkbox("Gebruik Stop Loss")
            sl_pct = st.number_input("Stop Loss (%)", value=5.0, min_value=0.0, step=0.5, disabled=not use_sl) / 100
        with r2c2:
            use_tp = st.checkbox("Gebruik Take Profit")
            tp_pct = st.number_input("Take Profit (%)", value=10.0, min_value=0.0, step=0.5, disabled=not use_tp) / 100
        with r2c3:
            use_max_hold = st.checkbox("Gebruik Max Holding Period")
            max_hold = st.number_input("Max Holding Period (dagen)", value=30, min_value=1, step=1, disabled=not use_max_hold)

    with st.expander("📈 Indicatoren toevoegen", expanded=True):
        st.caption(
            "Kies per rij een indicator-type en periode. Laat 'Kolomnaam' leeg voor een automatische naam "
            "(bv. RSI_14) — deze naam kun je hieronder gebruiken in je koop-/verkoopregels. Vink 'Plot op "
            "grafiek' uit als je een indicator alleen voor de regels wilt gebruiken, zonder 'm op de "
            "performance-grafiek te tonen. Nieuwe rij toevoegen kan met de '+' onderaan de tabel; rijen "
            "verwijderen doe je door ze aan te vinken en op de knop hieronder te klikken."
        )
        indicators_df = editable_table(
            session_key="indicators_df",
            default_df_func=default_indicators_df,
            column_order=INDICATORS_COLUMNS,
            delete_button_label="Verwijder aangevinkte indicatoren",
            column_config={
                "Verwijderen": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "Indicator": st.column_config.SelectboxColumn(
                    "Indicator type", options=list(INDICATOR_REGISTRY.keys()), required=True, width="large"),
                "Periode": st.column_config.NumberColumn(
                    "Periode (n)", min_value=1, step=1, help="Alleen nodig voor indicatoren met een periode."),
                "Naam": st.column_config.TextColumn(
                    "Kolomnaam (optioneel)", help="Laat leeg voor automatische naam."),
                "Plot op grafiek": st.column_config.CheckboxColumn(
                    "📈 Plot op grafiek", default=True, help="Toon deze indicator op de performance-grafiek."),
            },
        )
        indicators_list, plot_names = build_indicators_list(indicators_df)
        indicator_names = [item[0] for item in indicators_list]
        available_columns = sorted(set(BASE_COLUMNS + indicator_names))

        if indicators_list:
            st.caption("Beschikbare kolommen voor je regels: " + ", ".join(available_columns))

    with st.expander("✅ Koop- en verkoopregels", expanded=True):
        st.caption(
            "Alle regels binnen 'Koop' (en binnen 'Verkoop') moeten tegelijk waar zijn (AND-logica). "
            "'Vergelijk met' mag een getal zijn (bv. 30) of een kolomnaam (bv. SMA_200) om twee kolommen "
            "met elkaar te vergelijken. Zonder koopregels wordt er nooit gekocht. **Zonder verkoopregels "
            "wordt de positie automatisch gesloten zodra niet meer aan de koopregels wordt voldaan** "
            "(tenzij Stop Loss / Take Profit / Max Holding eerder ingrijpt)."
        )

        rules_col_config = {
            "Verwijderen": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
            "Kolom": st.column_config.SelectboxColumn("Kolom", options=available_columns, required=True),
            "Operator": st.column_config.SelectboxColumn("Operator", options=OPERATORS, required=True),
            "Vergelijk met": st.column_config.TextColumn("Vergelijk met (getal of kolomnaam)", required=True),
        }

        st.markdown("**Koopregels**")
        buy_rules_df = editable_table(
            session_key="buy_rules_df",
            default_df_func=default_buy_rules_df,
            column_order=RULES_COLUMNS,
            delete_button_label="Verwijder aangevinkte koopregels",
            column_config=rules_col_config,
        )

        st.markdown("**Verkoopregels**")
        sell_rules_df = editable_table(
            session_key="sell_rules_df",
            default_df_func=default_sell_rules_df,
            column_order=RULES_COLUMNS,
            delete_button_label="Verwijder aangevinkte verkoopregels",
            column_config=rules_col_config,
        )

        buy_rules = build_rules(buy_rules_df)
        sell_rules = build_rules(sell_rules_df)

    CONFIG = {
        "date_min": str(date_min),
        "date_max": str(date_max),
        "fee": fee_pct / 100,
        "stop_loss_pct": sl_pct if use_sl else None,
        "take_profit_pct": tp_pct if use_tp else None,
        "max_holding_period": int(max_hold) if use_max_hold else None,
        "indicators": indicators_list,
        "rules": {
            "buy": buy_rules,
            "sell": sell_rules,
        },
    }

    with st.expander("👀 Gegenereerde CONFIG bekijken"):
        st.code(pprint.pformat(CONFIG, sort_dicts=False), language="python")

    config_display_text = pprint.pformat(CONFIG, sort_dicts=False)
    run_button = st.button("Voer Backtest Uit", type="primary")


st.markdown("---")

# --- UITVOEREN EN RESULTATEN ---
if run_button and CONFIG is not None:
    try:
        df_final = backtest.run_pipeline(CONFIG=CONFIG, df=df_btc)
        df_stats = calculate_summary_stats(df_final, CONFIG=CONFIG)
        trade_log = calculate_trade_log(CONFIG=CONFIG, df=df_final)

        with stats_placeholder.container():
            st.subheader("📊 Stats")
            st.dataframe(df_stats.astype(str), use_container_width=True, height=580)

        # Alleen de indicatoren die aangevinkt zijn (of, in geavanceerde modus, alle indicatoren) plotten
        gebruikte_indicatoren = [naam for naam in plot_names if naam in df_final.columns]

        st.subheader("Performance Grafiek")
        fig_perf = plotly_plots.plot_performance(df_final, extra_columns=gebruikte_indicatoren)
        st.plotly_chart(fig_perf, use_container_width=True)

        st.subheader("Drawdown Grafiek")
        fig_dd = plotly_plots.plot_drawdowns(df_final)
        st.plotly_chart(fig_dd, use_container_width=True)

        st.subheader("Trade Logs")
        st.dataframe(trade_log, use_container_width=True, height=300)

        st.subheader("Backtest DataFrame")
        st.dataframe(df_final, use_container_width=True, height=300)

        rapport_lijst = [
            "=== GEBRUIKTE CONFIG ===",
            config_display_text,
            "",
            "=== STATS ===",
            df_stats.to_csv(header=True),
            "",
            "=== TRADE LOGS ===",
            trade_log.to_csv(index=False),
        ]
        volledige_export = "\n".join(rapport_lijst)

        st.download_button(
            label="📥 Download resultaat als CSV",
            data=volledige_export.encode('utf-8'),
            file_name=f'trade_logs_{timestamp}.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"Fout in CONFIG of uitvoering: {e}")
