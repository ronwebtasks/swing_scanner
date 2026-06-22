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

if "active_portfolio" not in st.session_state:
    st.session_state.active_portfolio = {}
if "selected_index" not in st.session_state:
    st.session_state.selected_index = "Nifty 50 (Core Bluechip)"


def now_ist():
    if IST is not None:
        return datetime.now(IST)
    return datetime.utcnow()


def is_market_open():
    now = now_ist()
    if now.weekday() > 4:
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

sensitivity = st.sidebar.radio(
    "Footprint Detection Sensitivity:",
    options=["Strict", "Balanced", "Relaxed"],
    index=1,
    help="Strict = fewer, higher-conviction blocks. Relaxed = more blocks shown, lower conviction each."
)

SENSITIVITY_PRESETS = {
    "Strict": {"vol_multiplier": 2.2, "close_loc_threshold": 0.70},
    "Balanced": {"vol_multiplier": 1.8, "close_loc_threshold": 0.62},
    "Relaxed": {"vol_multiplier": 1.5, "close_loc_threshold": 0.55},
}
scan_params = SENSITIVITY_PRESETS[sensitivity]

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
    skipped = []
    for idx, (sym, df) in enumerate(all_data.items()):
        progress_bar.progress((idx + 1) / total)
        if df is not None and not df.empty:
            try:
                scan_res = scan_stock(df, **scan_params)
            except Exception as e:
                skipped.append(f"{sym} (error: {e})")
                continue
            if scan_res:
                _, metrics = scan_res
                fresh_portfolio[sym] = metrics
        else:
            skipped.append(f"{sym} (no data)")

    progress_bar.empty()
    st.session_state.active_portfolio = fresh_portfolio

    if not fresh_portfolio:
        st.warning("No qualifying setups found in this segment right now.")
    if skipped:
        with st.sidebar.expander(f"⚠️ {len(skipped)} skipped"):
            st.write(skipped)

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
            "Setup Type": stored_data.get("Setup_Type", "-"),
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
        st.caption(f"🕒 Last updated (IST): {now_ist().strftime('%H:%M:%S')}")

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
                res_df.style.map(style_execution, subset=['Execution State']).format({
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

            st.markdown("**FII/DII Entry History Matrix:**")
            blocks = []
            if selected_ticker in st.session_state.active_portfolio:
                blocks = st.session_state.active_portfolio[selected_ticker].get("Blocks_Data", [])

            if blocks:
                shown_blocks = blocks[:4]
                prices = [b['price'] for b in shown_blocks]
                lowest_price = min(prices)
                highest_price = max(prices)

                card_html = "<div style='display:flex; flex-direction:column; gap:8px;'>"
                for i, block in enumerate(shown_blocks):
                    price = block['price']
                    date = block['date']

                    if price == lowest_price and lowest_price != highest_price:
                        border_color = "#22C55E"
                        badge_bg = "#064E3B"
                        badge_color = "#6EE7B7"
                        badge_text = "LOWEST"
                    elif price == highest_price and lowest_price != highest_price:
                        border_color = "#F97316"
                        badge_bg = "#7C2D12"
                        badge_color = "#FDBA74"
                        badge_text = "HIGHEST"
                    else:
                        border_color = "#6B7280"
                        badge_bg = "#374151"
                        badge_color = "#D1D5DB"
                        badge_text = f"B{i+1}"

                    card_html += f"""
                    <div style='
                        border-left: 4px solid {border_color};
                        background-color: #1F2937;
                        border-radius: 8px;
                        padding: 10px 14px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    '>
                        <div>
                            <div style='color:#9CA3AF; font-size:12px; margin-bottom:2px;'>📅 {date}</div>
                            <div style='color:#F9FAFB; font-size:17px; font-weight:600;'>₹{price:.2f}</div>
                        </div>
                        <div style='
                            background-color:{badge_bg};
                            color:{badge_color};
                            font-size:11px;
                            font-weight:700;
                            padding:4px 10px;
                            border-radius:12px;
                            letter-spacing:0.5px;
                        '>{badge_text}</div>
                    </div>
                    """
                card_html += "</div>"
                st.markdown(card_html, unsafe_allow_html=True)

                if lowest_price != highest_price:
                    st.markdown(
                        f"<div style='margin-top:10px; font-size:13px; color:#9CA3AF;'>"
                        f"🟢 Best entry: <b style='color:#6EE7B7;'>₹{lowest_price:.2f}</b>"
                        f" &nbsp;|&nbsp; 🟠 Worst entry: <b style='color:#FDBA74;'>₹{highest_price:.2f}</b>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.caption("⚠️ No institutional footprint blocks detected for this asset in the lookback window.")

        st.divider()
        chart_df = fetch_indian_stock_data(selected_ticker, period="1y")
        if not chart_df.empty and selected_ticker in st.session_state.active_portfolio:
            target_meta = st.session_state.active_portfolio[selected_ticker]
            blocks = target_meta.get("Blocks_Data", [])

            chart_df['Date'] = pd.to_datetime(chart_df['Date'])
            window = 60
            if blocks:
                oldest_block_date = min(pd.to_datetime(b['date'], format='%d-%m-%Y') for b in blocks)
                bars_since_oldest = (chart_df['Date'] >= oldest_block_date).sum()
                window = max(window, bars_since_oldest + 10)

            plot_df = chart_df.tail(window)

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=plot_df['Date'],
                open=plot_df['Open'],
                high=plot_df['High'],
                low=plot_df['Low'],
                close=plot_df['Close'],
                name="Price"
            ))

            fig.add_hline(y=target_meta["Floor"], line_dash="dash", line_color="#065F46", line_width=2, annotation_text="Buy Zone Floor")
            fig.add_hline(y=target_meta["Target"], line_dash="dot", line_color="#1E3A8A", line_width=2, annotation_text="Target")
            fig.add_hline(y=target_meta["SL"], line_dash="solid", line_color="#991B1B", line_width=2, annotation_text="Hard SL")

            if blocks:
                shown_blocks = blocks[:4]
                block_dates = [pd.to_datetime(b['date'], format='%d-%m-%Y') for b in shown_blocks]
                block_prices = [b['price'] for b in shown_blocks]
                block_labels = [f"B{i+1}" for i in range(len(shown_blocks))]

                lowest_price = min(block_prices)
                highest_price = max(block_prices)

                marker_colors = []
                for p in block_prices:
                    if p == lowest_price and lowest_price != highest_price:
                        marker_colors.append("#22C55E")
                    elif p == highest_price and lowest_price != highest_price:
                        marker_colors.append("#F97316")
                    else:
                        marker_colors.append("#FBBF24")

                hover_labels = []
                for lbl, p, d in zip(block_labels, block_prices, block_dates):
                    tag = ""
                    if p == lowest_price and lowest_price != highest_price:
                        tag = " Lowest"
                    elif p == highest_price and lowest_price != highest_price:
                        tag = " Highest"
                    hover_labels.append(f"{lbl}{tag}: Rs {p:.2f} on {d.strftime('%d-%b-%Y')}")

                fig.add_trace(
                    go.Scatter(
                        x=block_dates,
                        y=block_prices,
                        mode="markers+text",
                        marker=dict(
                            symbol="triangle-up",
                            size=15,
                            color=marker_colors,
                            line=dict(width=1, color="black")
                        ),
                        text=block_labels,
                        textposition="top center",
                        textfont=dict(color="#E5E7EB", size=12),
                        name="Footprint proxy",
                        hovertext=hover_labels,
                        hoverinfo="text"
                    )
                )

            fig.update_layout(
                title=f"{selected_ticker} Live Structural Workspace",
                template="plotly_dark",
                height=450,
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chart data unavailable for this asset right now.")

    if live_stream_active and market_open:
        time.sleep(10)
        st.rerun()
    elif live_stream_active and not market_open:
        st.sidebar.caption("Auto-refresh paused (market closed).")
else:
    st.info("System initialized. Select a market segment from the sidebar and execute the scan to spin up the real-time tracking matrix.")
