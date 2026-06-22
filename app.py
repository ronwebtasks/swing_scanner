# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    IST = None

from symbols import NIFTY_50, NIFTY_NEXT_50, MIDCAP_150
from data_engine import fetch_bulk_history, fetch_live_price, fetch_indian_stock_data
from indicators import scan_stock

st.set_page_config(page_title="NSE Live Tracker Engine", layout="wide")

st.title("🇮🇳 Real-Time Institutional Swing Tracker")
st.caption("Auto-Refreshing Order Blocks with Targeted Execution Zones")

# --- Control State Configuration ---
if "active_portfolio" not in st.session_state:
    st.session_state.active_portfolio = {}
if "selected_index" not in st.session_state:
    st.session_state.selected_index = "Nifty 50 (Core Bluechip)"


def is_market_open() -> bool:
    """Returns True if it's a weekday between 9:15 and 15:30 IST."""
    if IST is None:
        return True  # fallback: don't block refresh if zoneinfo unavailable
    now = datetime.now(IST)
    if now.weekday() > 4:  # Sat=5, Sun=6
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


segment = st.sidebar.selectbox(
    "Select Targeted Market Segment:",
    options=["Nifty 50 (Core Bluechip)", "Nifty Next 50 (High Momentum)", "Nifty Midcap 150"],
    key="selected_index"
)
run_scan = st.sidebar.button("Execute Structural Scanning Core", type="primary")

if segment == "Nifty 50 (Core Bluechip)":
    tickers = NIFTY_50
elif segment == "Nifty Next 50 (High Momentum)":
    tickers = NIFTY_NEXT_50
else:
    tickers = MIDCAP_150

if run_scan:
    fresh_portfolio = {}
    with st.spinner(f"Fetching data for {len(tickers)} stocks..."):
        all_data = fetch_bulk_history(tuple(tickers), period="1y")

    progress_bar = st.progress(0)
    total = max(len(all_data), 1)
    for idx, (sym, df) in enumerate(all_data.items()):
        progress_bar.progress((idx + 1) / total)
        if df is not None and not df.empty:
            try:
                scan_res = scan_stock(df)
            except Exception as e:
                st.sidebar.warning(f"Scan failed for {sym}: {e}")
                continue
            if scan_res and scan_res != "NEUTRAL":
                _, metrics = scan_res
                fresh_portfolio[sym] = metrics

    progress_bar.empty()
    st.session_state.active_portfolio = fresh_portfolio

    if not fresh_portfolio:
        st.warning("No qualifying setups found in this segment right now.")

# --- LIVE REFRESH DATA DISPLAY CORE ---
if st.session_state.active_portfolio:
    st.sidebar.divider()
    st.sidebar.subheader("Streaming Control")
    live_stream_active = st.sidebar.toggle("Enable Live 10s Auto-Update", value=True)

    market_open = is_market_open()
    if not market_open:
        st.sidebar.caption("⚠️ Market closed — showing last available prices.")

    compiled_rows = []
    for sym, stored_data in st.session_state.active_portfolio.items():
        live_price = fetch_live_price(sym)
        if live_price is None:
            continue

        floor = stored_data["Floor"]
        ceiling = stored_data["Ceiling"]

        if live_price < stored_data["SL"]:
            current_alert = "❌ INVALID_PASSED"
        elif floor <= live_price <= ceiling:
            current_alert = "🔥 ENTER_ZONE"
        elif live_price > ceiling:
            current_alert = "⏳ AWAIT_PULLBACK"
        else:
            current_alert = stored_data["Base_Status"]

        risk = live_price - stored_data["SL"]
        reward = stored_data["Target"] - live_price
        rr_ratio = round(reward / risk, 2) if risk > 0 else None

        compiled_rows.append({
            "Ticker": sym,
            "Live Price": live_price,
            "Execution State": current_alert,
            "Optimal Buy Zone": f"₹{floor:.2f} - ₹{ceiling:.2f}",
            "Profit Target": float(stored_data["Target"]),
            "Stop Loss (SL)": float(stored_data["SL"]),
            "ATR Level": float(stored_data["ATR"]),
            "Risk:Reward": rr_ratio,
        })

    res_df = pd.DataFrame(compiled_rows)

    if res_df.empty:
        st.warning("Could not fetch live prices for any stock in the portfolio. Will retry on next refresh.")
    else:
        st.caption(f"🕒 Last updated: {datetime.now().strftime('%H:%M:%S')}")

        # HARD FIXED RATIO: 73% Main Table, 27% Deep Dive Panel to match heights perfectly
        col_table, col_meta = st.columns([73, 27])

        with col_table:
            st.subheader("📊 Dynamic Execution Pipeline")

            def style_execution(val):
                if val == '🔥 ENTER_ZONE':
                    return 'background-color: #065F46; color: white; font-weight: bold;'
                elif val == '⏳ AWAIT_PULLBACK':
                    return 'background-color: #1E3A8A; color: white; font-weight: bold;'
                elif val == '❌ INVALID_PASSED':
                    return 'background-color: #991B1B; color: white; font-weight: bold;'
                return ''

            st.dataframe(
                res_df.style.map(style_execution, subset=['Execution State'])
                            .format({
                                "Live Price": "₹{:.2f}",
                                "Profit Target": "₹{:.2f}",
                                "Stop Loss (SL)": "₹{:.2f}",
                                "ATR Level": "{:.2f}",
                                "Risk:Reward": "{:.2f}"
                            }),
                use_container_width=True,
                height=440
            )

        with col_meta:
            st.subheader("🎯 Asset Deep-Dive")
            selected_ticker = st.selectbox("Inspect Asset:", options=res_df["Ticker"].unique())

            if selected_ticker in st.session_state.active_portfolio:
                blocks = st.session_state.active_portfolio[selected_ticker].get("Blocks_Data", [])
                st.markdown("**FII/DII Entry History Matrix:**")
