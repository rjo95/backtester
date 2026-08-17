"""
Streamlit App voor Backtester
- Simpele modus: indicatoren en regels bouwen via tabellen met expliciete
  toevoegen/verwijderen-knoppen
- Geavanceerde modus: CONFIG direct als Python dict bewerken (zoals voorheen)
- Data importeren (CSV/Excel met OHLCV)
- Export naar CSV, HTML en PDF
"""

# !streamlit run app.py --server.headless true

import os
import pprint
import io
import base64
import pandas as pd
import streamlit as st
import plotly_plots
from datetime import datetime
from html import escape

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
# DATA BRON (standaard BTC of geïmporteerd bestand)
# ============================================================
if "df_data" not in st.session_state:
    st.session_state.df_data = df_btc.copy()
    st.session_state.data_source = "Standaard BTC (data_import.df_btc)"

def _normalize_ohlc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Maak kolomnamen lowercase en herken open/high/low/close (en volume)."""
    df = df.copy()
    # Index moet datetime zijn
    if not isinstance(df.index, pd.DatetimeIndex):
        # Probeer eerste kolom of 'date'/'datetime'/'timestamp'
        date_candidates = [c for c in df.columns if str(c).lower() in ("date", "datetime", "timestamp", "time", "datum")]
        if date_candidates:
            df[date_candidates[0]] = pd.to_datetime(df[date_candidates[0]], errors="coerce", utc=False)
            df = df.set_index(date_candidates[0])
        else:
            # Probeer index te parsen
            try:
                df.index = pd.to_datetime(df.index, errors="coerce")
            except Exception:
                pass
    df = df[~df.index.isna()].sort_index()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "Geen geldige datum-index gevonden. Zorg dat de datum in de index staat "
            "of in een kolom genaamd date/datetime/timestamp/datum."
        )

    # Kolomnamen normaliseren
    col_map = {}
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for target in ("open", "high", "low", "close", "volume"):
        if target in lower_map:
            col_map[lower_map[target]] = target
        # veelvoorkomende varianten
        for alt in (f"{target}_price", f"{target}price", target[0]):  # o/h/l/c
            if alt in lower_map and target not in col_map.values():
                col_map[lower_map[alt]] = target
    df = df.rename(columns=col_map)

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Verplichte kolommen ontbreken na normalisatie: {sorted(missing)}. "
            f"Gevonden kolommen: {list(df.columns)}"
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
| Datum | Staat in de **index**, of in een kolom `date` / `datetime` / `timestamp` / `datum` |
| Verplichte kolommen | `open`, `high`, `low`, `close` (hoofdletterongevoelig) |
| Optioneel | `volume` en eventuele extra kolommen (die kun je later in regels gebruiken) |
| Scheidingsteken CSV | Komma of puntkomma (wordt automatisch geprobeerd) |
| Decimalen | Punt of komma |

**Tips**
- Rijen met ontbrekende OHLC-waarden worden verwijderd.
- Extra kolommen blijven behouden en zijn beschikbaar in de regel-builder.
- Na een geslaagde import wordt de hele backtest op deze data uitgevoerd.
"""
    )
    uploaded = st.file_uploader(
        "Kies een CSV- of Excel-bestand",
        type=["csv", "xlsx", "xls"],
        help="Bestand met datum + open/high/low/close",
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 Reset naar standaard BTC-data"):
            st.session_state.df_data = df_btc.copy()
            st.session_state.data_source = "Standaard BTC (data_import.df_btc)"
            st.rerun()

    if uploaded is not None:
        try:
            name = uploaded.name.lower()
            if name.endswith(".csv"):
                # Probeer veelvoorkomende CSV-varianten
                raw = uploaded.getvalue()
                df_up = None
                last_err = None
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
                f"✅ Geïmporteerd: **{uploaded.name}** — "
                f"{len(df_up):,} rijen, van {df_up.index.min().date()} t/m {df_up.index.max().date()}. "
                f"Kolommen: {list(df_up.columns)}"
            )
            st.dataframe(df_up.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Import mislukt: {e}")

st.caption(f"Actieve data: **{st.session_state.data_source}**  |  "
           f"{len(st.session_state.df_data):,} rijen  |  "
           f"{st.session_state.df_data.index.min().date()} → {st.session_state.df_data.index.max().date()}")

df_active = st.session_state.df_data


# ============================================================
# REGISTRY
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

BASE_COLUMNS = sorted(df_active.columns.tolist())

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


def _apply_data_editor_changes(session_key: str):
    """Callback: past edits/added/deleted van data_editor toe op de DataFrame in session_state.
    Dit voorkomt de bekende 'eerste Enter springt terug'-bug."""
    editor_key = f"_{session_key}"
    if editor_key not in st.session_state:
        return
    changes = st.session_state[editor_key]
    if not isinstance(changes, dict):
        return
    df = st.session_state[session_key].copy()

    # Bewerkte cellen
    for row_idx, edits in changes.get("edited_rows", {}).items():
        for col, val in edits.items():
            if col in df.columns:
                df.at[int(row_idx), col] = val

    # Verwijderde rijen (van hoog naar laag)
    deleted = sorted(changes.get("deleted_rows", []), reverse=True)
    if deleted:
        df = df.drop(index=[i for i in deleted if i in df.index]).reset_index(drop=True)

    # Toegevoegde rijen
    for new_row in changes.get("added_rows", []):
        # Zorg dat alle kolommen aanwezig zijn
        row_data = {c: new_row.get(c, None) for c in df.columns}
        df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

    st.session_state[session_key] = df


def editable_table(session_key, default_df_func, column_config, column_order, delete_button_label):
    """Data editor met betrouwbare session-state (geen revert bij eerste Enter)
    en expliciete 'verwijder aangevinkte rijen'-knop."""
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
    # Return-waarde is de actuele view; session_state is de bron van waarheid via callback
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


def build_html_report(config_text, df_stats, trade_log, fig_perf, fig_dd, data_source):
    """Maak een zelfstandig HTML-rapport met interactive Plotly-grafieken."""
    stats_html = df_stats.to_html(classes="table", border=0)
    trades_html = trade_log.to_html(classes="table", border=0, index=False) if trade_log is not None and len(trade_log) else "<p>Geen trades</p>"
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

  <div class="section">
    <h2>Gebruikte CONFIG</h2>
    <pre>{escape(config_text)}</pre>
  </div>

  <div class="section">
    <h2>Stats</h2>
    {stats_html}
  </div>

  <div class="section">
    <h2>Performance grafiek</h2>
    {perf_html}
  </div>

  <div class="section">
    <h2>Drawdown grafiek</h2>
    {dd_html}
  </div>

  <div class="section">
    <h2>Trade logs</h2>
    {trades_html}
  </div>
</body>
</html>"""
    return html.encode("utf-8")


def build_pdf_report(config_text, df_stats, trade_log, data_source):
    """Eenvoudige PDF met config + tabellen (geen externe binaries).
    Gebruikt een minimale PDF-writer in pure Python."""
    # Minimal PDF generation without external deps
    def _escape_pdf(s):
        return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = []
    lines.append(f"Backtest rapport – {timestamp}")
    lines.append(f"Data: {data_source}")
    lines.append("")
    lines.append("=== CONFIG ===")
    for line in config_text.splitlines():
        lines.append(line[:100])
    lines.append("")
    lines.append("=== STATS ===")
    try:
        stats_str = df_stats.astype(str)
        lines.append(stats_str.to_string())
    except Exception:
        lines.append(str(df_stats))
    lines.append("")
    lines.append("=== TRADE LOGS ===")
    if trade_log is not None and len(trade_log):
        lines.append(trade_log.head(200).to_string(index=False))
        if len(trade_log) > 200:
            lines.append(f"... ({len(trade_log) - 200} extra rijen weggelaten)")
    else:
        lines.append("Geen trades")

    # Build a very simple multi-page text PDF
    y_start = 800
    font_size = 9
    line_height = 11
    pages = []
    current = []
    y = y_start
    for line in lines:
        # soft wrap long lines
        while len(line) > 95:
            current.append(line[:95])
            line = line[95:]
            y -= line_height
            if y < 50:
                pages.append(current)
                current = []
                y = y_start
        current.append(line)
        y -= line_height
        if y < 50:
            pages.append(current)
            current = []
            y = y_start
    if current:
        pages.append(current)

    objects = []
    # Catalog + pages tree filled later
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    page_objs = []
    content_objs = []

    for i, page_lines in enumerate(pages):
        content = "BT /F1 {fs} Tf 40 {y0} Td\n".format(fs=font_size, y0=y_start)
        first = True
        for pl in page_lines:
            txt = _escape_pdf(pl)
            if first:
                content += f"({txt}) Tj\n"
                first = False
            else:
                content += f"0 -{line_height} Td ({txt}) Tj\n"
        content += "ET"
        content_objs.append(content)

    # Object numbers: 1=catalog, 2=pages, 3=font, then content streams, then page objects
    font_obj_num = 3
    objects.append(  # placeholder for pages – filled after we know counts
        ""
    )
    objects.append(
        f"{font_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n"
    )

    content_start = 4
    for i, c in enumerate(content_objs):
        objects.append(
            f"{content_start + i} 0 obj\n<< /Length {len(c.encode('latin-1', errors='replace'))} >>\nstream\n{c}\nendstream\nendobj\n"
        )

    page_start = content_start + len(content_objs)
    kids = []
    for i in range(len(pages)):
        obj_num = page_start + i
        kids.append(f"{obj_num} 0 R")
        objects.append(
            f"{obj_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {content_start + i} 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>\nendobj\n"
        )

    objects[1] = (
        f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>\nendobj\n"
    )

    # Assemble PDF
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj.encode("latin-1", errors="replace"))
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return out.getvalue()


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
config_display_text = None
plot_names = []

if advanced_mode:
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
    stats_placeholder = st.empty()
    stats_placeholder.info("Vul de instellingen hieronder in en klik op **Voer Backtest Uit**.")

    with st.expander("📅 Basisinstellingen", expanded=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            date_min = st.date_input(
                "Startdatum", value=df_active.index.min().date(),
                min_value=df_active.index.min().date(), max_value=df_active.index.max().date())
        with r1c2:
            date_max = st.date_input(
                "Einddatum", value=df_active.index.max().date(),
                min_value=df_active.index.min().date(), max_value=df_active.index.max().date())
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
        df_final = backtest.run_pipeline(CONFIG=CONFIG, df=df_active)
        df_stats = calculate_summary_stats(df_final, CONFIG=CONFIG)
        trade_log = calculate_trade_log(CONFIG=CONFIG, df=df_final)

        with stats_placeholder.container():
            st.subheader("📊 Stats")
            st.dataframe(df_stats.astype(str), use_container_width=True, height=580)

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

        # --- Exports ---
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
        pdf_bytes = build_pdf_report(
            config_display_text or "",
            df_stats,
            trade_log,
            st.session_state.data_source,
        )

        st.subheader("📥 Download resultaten")
        d1, d2, d3 = st.columns(3)
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
        with d3:
            st.download_button(
                label="📕 PDF rapport (tabellen)",
                data=pdf_bytes,
                file_name=f"backtest_{timestamp}.pdf",
                mime="application/pdf",
            )
            st.caption("PDF bevat config, stats en trade log (geen interactieve grafieken). Gebruik HTML voor de volledige visualisatie.")

    except Exception as e:
        st.error(f"Fout in CONFIG of uitvoering: {e}")