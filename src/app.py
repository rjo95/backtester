"""
Streamlit App voor Backtester
- Simpele modus: indicatoren en regels via tabellen
- Geavanceerde modus: CONFIG als Python dict
- CSV/Excel import
- Validatie vóór run + nette foutmeldingen
- Export CSV + HTML
"""

# !streamlit run app.py --server.headless true

import os
import pprint
import io
import pandas as pd
import streamlit as st
import plotly_plots
from datetime import datetime
from html import escape

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from data_import import df_btc
import indicators as ind
import backtest_engine as backtest
from backtest_statistics import calculate_summary_stats, calculate_trade_log

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

st.set_page_config(page_title="Crypto Backtester", layout="wide")
st.title("Backtester")


# ============================================================
# DATA BRON
# ============================================================
if "df_data" not in st.session_state:
    st.session_state.df_data = df_btc.copy()
    st.session_state.data_source = "Standaard BTC (data_import.df_btc)"


def _normalize_ohlc_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        date_candidates = [
            c for c in df.columns
            if str(c).lower() in ("date", "datetime", "timestamp", "time", "datum")
        ]
        if date_candidates:
            df[date_candidates[0]] = pd.to_datetime(
                df[date_candidates[0]], errors="coerce", utc=False
            )
            df = df.set_index(date_candidates[0])
        else:
            try:
                df.index = pd.to_datetime(df.index, errors="coerce")
            except Exception:
                pass
    df = df[~df.index.isna()].sort_index()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "Geen geldige datum-index. Zet de datum in de index of in een kolom "
            "date / datetime / timestamp / datum."
        )

    col_map = {}
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for target in ("open", "high", "low", "close", "volume"):
        if target in lower_map:
            col_map[lower_map[target]] = target
        for alt in (f"{target}_price", f"{target}price"):
            if alt in lower_map and target not in col_map.values():
                col_map[lower_map[alt]] = target
    df = df.rename(columns=col_map)

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Verplichte kolommen ontbreken: {sorted(missing)}. "
            f"Gevonden: {list(df.columns)}"
        )

    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise ValueError("Na opschonen blijven er geen rijen over.")
    return df


with st.expander("📂 Data importeren (CSV of Excel)", expanded=False):
    st.markdown(
        """
**Eisen aan het bestand**

| Onderdeel | Vereiste |
|-----------|----------|
| Formaat | `.csv`, `.xlsx` of `.xls` |
| Datum | Index, of kolom `date` / `datetime` / `timestamp` / `datum` |
| Verplicht | `open`, `high`, `low`, `close` (hoofdletterongevoelig) |
| Optioneel | `volume` + extra kolommen (bruikbaar in regels) |
| CSV | Komma of puntkomma (wordt automatisch geprobeerd) |

Rijen met ontbrekende OHLC worden verwijderd. Extra kolommen blijven behouden.
"""
    )
    uploaded = st.file_uploader(
        "Kies een CSV- of Excel-bestand",
        type=["csv", "xlsx", "xls"],
    )
    if st.button("🔄 Reset naar standaard BTC-data"):
        st.session_state.df_data = df_btc.copy()
        st.session_state.data_source = "Standaard BTC (data_import.df_btc)"
        st.rerun()

    if uploaded is not None:
        try:
            name = uploaded.name.lower()
            if name.endswith(".csv"):
                raw = uploaded.getvalue()
                df_up, last_err = None, None
                for kwargs in (
                    {"sep": ",", "index_col": 0, "parse_dates": True},
                    {"sep": ";", "index_col": 0, "parse_dates": True},
                    {"sep": ",", "parse_dates": True},
                    {"sep": ";", "parse_dates": True},
                    {"sep": None, "engine": "python", "index_col": 0},
                ):
                    try:
                        df_up = pd.read_csv(io.BytesIO(raw), **kwargs)
                        break
                    except Exception as e:
                        last_err = e
                if df_up is None:
                    raise ValueError(f"CSV kon niet gelezen worden: {last_err}")
            else:
                df_up = pd.read_excel(uploaded, index_col=0, parse_dates=True)

            df_up = _normalize_ohlc_columns(df_up)
            st.session_state.df_data = df_up
            st.session_state.data_source = f"Geüpload: {uploaded.name}"
            st.success(
                f"✅ **{uploaded.name}** — {len(df_up):,} rijen, "
                f"{df_up.index.min().date()} t/m {df_up.index.max().date()}. "
                f"Kolommen: {list(df_up.columns)}"
            )
            st.dataframe(df_up.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Import mislukt: {e}")

st.caption(
    f"Actieve data: **{st.session_state.data_source}**  |  "
    f"{len(st.session_state.df_data):,} rijen  |  "
    f"{st.session_state.df_data.index.min().date()} → "
    f"{st.session_state.df_data.index.max().date()}"
)
df_active = st.session_state.df_data


# ============================================================
# REGISTRY
# ============================================================
INDICATOR_REGISTRY = {
    "SMA – Simple Moving Average":   {"func": ind.sma,                       "needs_n": True,  "prefix": "SMA",           "default_n": 50},
    "RSI – Relative Strength Index": {"func": ind.rsi,                       "needs_n": True,  "prefix": "RSI",           "default_n": 14},
    "TSM – Time Series Momentum":    {"func": ind.time_series_momentum_days, "needs_n": True,  "prefix": "TSM",           "default_n": 90},
    "CLV – Close Location Value":    {"func": ind.close_location_value,      "needs_n": False, "prefix": "CLV",           "default_n": None},
    "Return Z-Score":                {"func": ind.return_zscore,             "needs_n": True,  "prefix": "Return_ZScore", "default_n": 20},
    "ATR – Average True Range":      {"func": ind.atr,                       "needs_n": True,  "prefix": "ATR",           "default_n": 14},
}

OPERATORS = ["<", ">", "<=", ">=", "=="]
BASE_COLUMNS = sorted(df_active.columns.tolist())
INDICATORS_COLUMNS = ["Verwijderen", "Indicator", "Periode", "Naam", "Plot op grafiek"]
RULES_COLUMNS = ["Verwijderen", "Kolom", "Operator", "Vergelijk met"]


def default_indicators_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Indicator": "SMA – Simple Moving Average", "Periode": 100, "Naam": "SMA_100", "Plot op grafiek": True},
    ], columns=INDICATORS_COLUMNS)


def default_buy_rules_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Kolom": "close", "Operator": ">", "Vergelijk met": "SMA_100"},
    ], columns=RULES_COLUMNS)


def default_sell_rules_df():
    return pd.DataFrame([
        {"Verwijderen": False, "Kolom": "close", "Operator": "<", "Vergelijk met": "SMA_100"},
    ], columns=RULES_COLUMNS)


def _apply_data_editor_changes(session_key: str):
    editor_key = f"_{session_key}"
    if editor_key not in st.session_state:
        return
    changes = st.session_state[editor_key]
    if not isinstance(changes, dict):
        return
    df = st.session_state[session_key].copy()

    for row_idx, edits in changes.get("edited_rows", {}).items():
        for col, val in edits.items():
            if col in df.columns:
                df.at[int(row_idx), col] = val

    deleted = sorted(changes.get("deleted_rows", []), reverse=True)
    if deleted:
        df = df.drop(index=[i for i in deleted if i in df.index]).reset_index(drop=True)

    for new_row in changes.get("added_rows", []):
        row_data = {c: new_row.get(c, None) for c in df.columns}
        df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

    st.session_state[session_key] = df


def editable_table(session_key, default_df_func, column_config, column_order, delete_button_label):
    if session_key not in st.session_state:
        st.session_state[session_key] = default_df_func()

    editor_key = f"_{session_key}"
    edited_df = st.data_editor(
        st.session_state[session_key],
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
        column_config=column_config,
        column_order=column_order,
        on_change=_apply_data_editor_changes,
        args=(session_key,),
    )
    st.session_state[session_key] = edited_df

    if st.button(f"🗑️ {delete_button_label}", key=f"{session_key}_delete_btn"):
        df = st.session_state[session_key]
        if "Verwijderen" in df.columns:
            st.session_state[session_key] = df[~df["Verwijderen"].fillna(False)].reset_index(drop=True)
        st.rerun()

    return st.session_state[session_key]


def build_indicators_list(indicators_df: pd.DataFrame):
    indicators_list, plot_names = [], []
    for _, row in indicators_df.iterrows():
        ind_key = row.get("Indicator")
        if not ind_key or ind_key not in INDICATOR_REGISTRY:
            continue
        entry = INDICATOR_REGISTRY[ind_key]
        func, prefix = entry["func"], entry["prefix"]

        if entry["needs_n"]:
            n = row.get("Periode")
            if pd.isna(n):
                continue
            n = int(n)
            naam = (row.get("Naam") or "").strip() or f"{prefix}_{n}"
            indicators_list.append((naam, func, n))
        else:
            naam = (row.get("Naam") or "").strip() or prefix
            indicators_list.append((naam, func))

        if bool(row.get("Plot op grafiek", True)):
            plot_names.append(naam)
    return indicators_list, plot_names


def build_rules(rules_df: pd.DataFrame):
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
            waarde = str(waarde_raw).strip()
        rules.append((kolom, operator, waarde))
    return rules


def format_rules_preview(rules: list, label: str) -> str:
    if not rules:
        return f"**{label}:** *(geen regels)*"
    conds = [f"`{c}` {op} `{v}`" for c, op, v in rules]
    return f"**{label}:** " + " **ÉN** ".join(conds)


# ============================================================
# VALIDATIE
# ============================================================
def validate_simple_mode(
    date_min,
    date_max,
    fee_pct,
    use_sl, sl_pct,
    use_tp, tp_pct,
    use_max_hold, max_hold,
    indicators_df,
    indicators_list,
    buy_rules,
    sell_rules,
    available_columns,
    df,
):
    errors, warnings = [], []

    # --- Data ---
    if df is None or len(df) == 0:
        errors.append("Geen data geladen. Importeer een bestand of reset naar standaard BTC-data.")
    else:
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                errors.append(f"Data mist verplichte kolom `{col}`.")

    # --- Datums ---
    if date_min is not None and date_max is not None:
        if date_min > date_max:
            errors.append("Startdatum ligt na de einddatum.")
        if df is not None and len(df):
            if date_max < df.index.min().date() or date_min > df.index.max().date():
                warnings.append(
                    "Gekozen periode overlapt niet (of nauwelijks) met de data. "
                    f"Data loopt van {df.index.min().date()} t/m {df.index.max().date()}."
                )

    # --- Fee / risk ---
    if fee_pct < 0:
        errors.append("Fee kan niet negatief zijn.")
    if use_sl and (sl_pct is None or sl_pct <= 0):
        errors.append("Stop Loss staat aan maar de waarde is leeg of ≤ 0.")
    if use_tp and (tp_pct is None or tp_pct <= 0):
        errors.append("Take Profit staat aan maar de waarde is leeg of ≤ 0.")
    if use_max_hold and (max_hold is None or int(max_hold) < 1):
        errors.append("Max Holding Period staat aan maar is kleiner dan 1 dag.")

    # --- Indicatoren ---
    seen_names = set()
    for _, row in indicators_df.iterrows():
        ind_key = row.get("Indicator")
        if not ind_key or ind_key not in INDICATOR_REGISTRY:
            if ind_key:
                errors.append(f"Onbekende indicator: `{ind_key}`.")
            continue
        entry = INDICATOR_REGISTRY[ind_key]
        if entry["needs_n"]:
            n = row.get("Periode")
            if pd.isna(n) or int(n) < 1:
                errors.append(
                    f"Indicator **{ind_key}** heeft een geldige periode (n ≥ 1) nodig."
                )
        naam = (row.get("Naam") or "").strip()
        if not naam:
            # auto-naam wordt later gezet; check op prefix+n
            if entry["needs_n"] and not pd.isna(row.get("Periode")):
                naam = f"{entry['prefix']}_{int(row.get('Periode'))}"
            else:
                naam = entry["prefix"]
        if naam in seen_names:
            errors.append(f"Dubbele indicator-kolomnaam: `{naam}`. Kies unieke namen.")
        seen_names.add(naam)

    if not indicators_list and len(indicators_df) > 0:
        warnings.append(
            "Er staan indicator-rijen in de tabel, maar geen enkele is geldig "
            "(controleer type en periode)."
        )

    # --- Regels ---
    if not buy_rules:
        warnings.append(
            "Geen koopregels: er wordt nooit gekocht "
            "(tenzij je dat bewust zo wilt)."
        )
    if not sell_rules:
        warnings.append(
            "Geen verkoopregels: positie wordt gesloten zodra niet meer aan de "
            "koopregels wordt voldaan (of via SL/TP/max holding)."
        )

    def _check_rule_side(rules, side_label):
        for col, op, val in rules:
            if col not in available_columns:
                errors.append(
                    f"{side_label}-regel: kolom `{col}` bestaat niet. "
                    f"Beschikbaar: {', '.join(available_columns[:12])}"
                    + ("…" if len(available_columns) > 12 else "")
                )
            if op not in OPERATORS:
                errors.append(f"{side_label}-regel: ongeldige operator `{op}`.")
            if isinstance(val, str) and val not in available_columns:
                # kan een typefout in kolomnaam zijn
                try:
                    float(val)
                except ValueError:
                    errors.append(
                        f"{side_label}-regel: `{val}` is geen getal en geen bestaande kolom."
                    )

    _check_rule_side(buy_rules, "Koop")
    _check_rule_side(sell_rules, "Verkoop")

    return errors, warnings


def validate_advanced_config(CONFIG, df):
    errors, warnings = [], []
    if not isinstance(CONFIG, dict):
        errors.append("CONFIG is geen dictionary.")
        return errors, warnings

    for key in ("date_min", "date_max", "fee", "indicators", "rules"):
        if key not in CONFIG:
            errors.append(f"CONFIG mist verplichte sleutel `{key}`.")

    if df is None or len(df) == 0:
        errors.append("Geen data geladen.")

    rules = CONFIG.get("rules") or {}
    if not isinstance(rules, dict):
        errors.append("`rules` moet een dict zijn met 'buy' en 'sell'.")
    else:
        buy = rules.get("buy") or []
        sell = rules.get("sell") or []
        if not buy:
            warnings.append("Geen koopregels: er wordt nooit gekocht.")
        if not sell:
            warnings.append(
                "Geen verkoopregels: exit via einde koopconditie of SL/TP/max holding."
            )

    fee = CONFIG.get("fee")
    if fee is not None and fee < 0:
        errors.append("fee kan niet negatief zijn.")

    inds = CONFIG.get("indicators") or []
    names = []
    for item in inds:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            errors.append(f"Ongeldige indicator-entry: {item}")
            continue
        names.append(item[0])
    if len(names) != len(set(names)):
        errors.append("Dubbele indicator-namen in CONFIG.")

    return errors, warnings


def show_validation(errors, warnings):
    if errors:
        st.error("**Kan de backtest niet starten:**\n\n" + "\n".join(f"- {e}" for e in errors))
    if warnings:
        st.warning("**Let op:**\n\n" + "\n".join(f"- {w}" for w in warnings))


def build_html_report(config_text, df_stats, trade_log, fig_perf, fig_dd, data_source):
    stats_html = df_stats.to_html(classes="table", border=0)
    trades_html = (
        trade_log.to_html(classes="table", border=0, index=False)
        if trade_log is not None and len(trade_log)
        else "<p>Geen trades</p>"
    )
    perf_html = fig_perf.to_html(full_html=False, include_plotlyjs="cdn") if fig_perf is not None else ""
    dd_html = fig_dd.to_html(full_html=False, include_plotlyjs=False) if fig_dd is not None else ""

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8"/>
<title>Backtest rapport – {timestamp}</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #222; }}
  h1, h2 {{ color: #0f172a; }}
  pre {{ background: #f8fafc; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.85rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.9rem; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 0.4rem 0.6rem; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .meta {{ color: #64748b; margin-bottom: 1.5rem; }}
  .section {{ margin-bottom: 2.5rem; }}
</style>
</head>
<body>
  <h1>Backtest rapport</h1>
  <p class="meta">Gegenereerd: {timestamp} &nbsp;|&nbsp; Data: {escape(str(data_source))}</p>
  <div class="section"><h2>Gebruikte CONFIG</h2><pre>{escape(config_text)}</pre></div>
  <div class="section"><h2>Stats</h2>{stats_html}</div>
  <div class="section"><h2>Performance grafiek</h2>{perf_html}</div>
  <div class="section"><h2>Drawdown grafiek</h2>{dd_html}</div>
  <div class="section"><h2>Trade logs</h2>{trades_html}</div>
</body>
</html>"""
    return html.encode("utf-8")


# ============================================================
# MODUS
# ============================================================
advanced_mode = st.toggle(
    "🔧 Geavanceerde modus (CONFIG direct als Python dict bewerken)",
    value=False,
    help="Voor Donchian channels, custom logica, etc.",
)

CONFIG = None
config_display_text = None
plot_names = []
validation_errors = []
validation_warnings = []

if advanced_mode:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚙️ Python CONFIG Editor")
        default_config_text = """{
        'date_min': '1920-01-31',
        'date_max': '2035-12-30',
        "fee": 0.002,
        "stop_loss_pct": None,
        "take_profit_pct": None,
        "max_holding_period": None,
        "indicators": [
            ("RSI_14", ind.rsi, 14),
            ("SMA_100", ind.sma, 100),
            ("SMA_200", ind.sma, 200),
        ],
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
        run_button = st.button("Voer Backtest Uit", type="primary", key="run_adv")

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
            validation_errors, validation_warnings = validate_advanced_config(CONFIG, df_active)
        except Exception as e:
            st.error(f"Fout in CONFIG-syntax: {e}")
            with st.expander("Technische details"):
                st.exception(e)
            CONFIG = None

else:
    stats_placeholder = st.empty()
    stats_placeholder.info("Vul de instellingen in en klik op **Voer Backtest Uit**.")

    with st.expander("📅 Basisinstellingen", expanded=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            date_min = st.date_input(
                "Startdatum",
                value=df_active.index.min().date(),
                min_value=df_active.index.min().date(),
                max_value=df_active.index.max().date(),
            )
        with r1c2:
            date_max = st.date_input(
                "Einddatum",
                value=df_active.index.max().date(),
                min_value=df_active.index.min().date(),
                max_value=df_active.index.max().date(),
            )
        with r1c3:
            fee_pct = st.number_input(
                "Fee per trade (%)", value=0.2, min_value=0.0, step=0.05, format="%.3f"
            )

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            use_sl = st.checkbox("Gebruik Stop Loss")
            sl_pct = st.number_input(
                "Stop Loss (%)", value=5.0, min_value=0.0, step=0.5, disabled=not use_sl
            ) / 100
        with r2c2:
            use_tp = st.checkbox("Gebruik Take Profit")
            tp_pct = st.number_input(
                "Take Profit (%)", value=10.0, min_value=0.0, step=0.5, disabled=not use_tp
            ) / 100
        with r2c3:
            use_max_hold = st.checkbox("Gebruik Max Holding Period")
            max_hold = st.number_input(
                "Max Holding Period (dagen)", value=30, min_value=1, step=1, disabled=not use_max_hold
            )

    with st.expander("📈 Indicatoren toevoegen", expanded=True):
        st.caption(
            "Kies per rij een indicator-type en periode. Laat 'Kolomnaam' leeg voor een automatische naam. "
            "Nieuwe rij: '+' onderaan; verwijderen: aanvinken + knop."
        )
        indicators_df = editable_table(
            session_key="indicators_df",
            default_df_func=default_indicators_df,
            column_order=INDICATORS_COLUMNS,
            delete_button_label="Verwijder aangevinkte indicatoren",
            column_config={
                "Verwijderen": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "Indicator": st.column_config.SelectboxColumn(
                    "Indicator type", options=list(INDICATOR_REGISTRY.keys()), required=True, width="large"
                ),
                "Periode": st.column_config.NumberColumn(
                    "Periode (n)", min_value=1, step=1, help="Nodig voor indicatoren met een periode."
                ),
                "Naam": st.column_config.TextColumn("Kolomnaam (optioneel)", help="Leeg = automatische naam."),
                "Plot op grafiek": st.column_config.CheckboxColumn("📈 Plot op grafiek", default=True),
            },
        )
        indicators_list, plot_names = build_indicators_list(indicators_df)
        indicator_names = [item[0] for item in indicators_list]
        available_columns = sorted(set(BASE_COLUMNS + indicator_names))

        if indicators_list:
            st.caption("Beschikbare kolommen voor regels: " + ", ".join(available_columns))

    with st.expander("✅ Koop- en verkoopregels", expanded=True):
        st.caption(
            "Alle regels binnen Koop (en binnen Verkoop) moeten tegelijk waar zijn (**AND**). "
            "'Vergelijk met' mag een getal of een kolomnaam zijn. "
            "Zonder verkoopregels wordt de positie gesloten zodra de koopregels niet meer gelden "
            "(tenzij SL/TP/max holding eerder ingrijpt)."
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

        st.caption(format_rules_preview(buy_rules, "Koop"))
        st.caption(format_rules_preview(sell_rules, "Verkoop"))

    CONFIG = {
        "date_min": str(date_min),
        "date_max": str(date_max),
        "fee": fee_pct / 100,
        "stop_loss_pct": sl_pct if use_sl else None,
        "take_profit_pct": tp_pct if use_tp else None,
        "max_holding_period": int(max_hold) if use_max_hold else None,
        "indicators": indicators_list,
        "rules": {"buy": buy_rules, "sell": sell_rules},
    }

    validation_errors, validation_warnings = validate_simple_mode(
        date_min, date_max, fee_pct,
        use_sl, sl_pct, use_tp, tp_pct, use_max_hold, max_hold,
        indicators_df, indicators_list, buy_rules, sell_rules,
        available_columns, df_active,
    )

    with st.expander("👀 Gegenereerde CONFIG bekijken"):
        st.code(pprint.pformat(CONFIG, sort_dicts=False), language="python")

    config_display_text = pprint.pformat(CONFIG, sort_dicts=False)

    show_validation(validation_errors, validation_warnings)
    run_disabled = len(validation_errors) > 0
    run_button = st.button(
        "Voer Backtest Uit",
        type="primary",
        disabled=run_disabled,
        key="run_simple",
        help="Los eerst de fouten hierboven op." if run_disabled else None,
    )


st.markdown("---")

# --- UITVOEREN ---
if run_button and CONFIG is not None:
    # Advanced: validatie pas na parse; toon en blokkeer bij errors
    if advanced_mode and validation_errors:
        show_validation(validation_errors, validation_warnings)
    elif validation_errors:
        show_validation(validation_errors, validation_warnings)
    else:
        if validation_warnings:
            show_validation([], validation_warnings)
        try:
            with st.status("Backtest wordt uitgevoerd…", expanded=True) as status:
                st.write("Pipeline starten…")
                df_final = backtest.run_pipeline(CONFIG=CONFIG, df=df_active)
                st.write("Statistieken berekenen…")
                df_stats = calculate_summary_stats(df_final, CONFIG=CONFIG)
                st.write("Trade log opbouwen…")
                trade_log = calculate_trade_log(CONFIG=CONFIG, df=df_final)
                status.update(label="Backtest voltooid", state="complete")

            with stats_placeholder.container():
                st.subheader("📊 Stats")
                st.dataframe(df_stats.astype(str), use_container_width=True, height=580)

            gebruikte_indicatoren = [n for n in plot_names if n in df_final.columns]

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
                config_display_text or "",
                "",
                "=== STATS ===",
                df_stats.to_csv(header=True),
                "",
                "=== TRADE LOGS ===",
                trade_log.to_csv(index=False) if trade_log is not None else "",
            ]
            volledige_export = "\n".join(rapport_lijst)

            html_bytes = build_html_report(
                config_display_text or "",
                df_stats,
                trade_log,
                fig_perf,
                fig_dd,
                st.session_state.data_source,
            )

            st.subheader("📥 Download resultaten")
            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    label="📄 CSV / tekst rapport",
                    data=volledige_export.encode("utf-8"),
                    file_name=f"backtest_{timestamp}.csv",
                    mime="text/csv",
                )
            with d2:
                st.download_button(
                    label="🌐 HTML rapport (met grafieken)",
                    data=html_bytes,
                    file_name=f"backtest_{timestamp}.html",
                    mime="text/html",
                )

        except Exception as e:
            st.error(
                "**Backtest mislukt.** Controleer je regels, indicatoren en data. "
                "Zie technische details hieronder."
            )
            with st.expander("Technische details", expanded=False):
                st.exception(e)