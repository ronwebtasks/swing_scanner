# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from symbols import NIFTY_50, NIFTY_NEXT_50, MIDCAP_150
from data_engine import fetch_indian_stock_data
from indicators import scan_stock

st.set_page_config(page_title="NSE Live Tracker Engine", layout="wide")

st.title("🇮🇳 Real-Time Institutional Swing Tracker")
st.caption("Auto-Refreshing Order Blocks with Targeted Execution Zones")

# --- Control State Configuration ---
if "active_portfolio" not in st.session_state:
    st.session_state.active_portfolio = {}
if "selected_index" not in st.session_state:
    st.session_state.selected_index = "Nifty 50 (Core Bluechip)"
if "last_scanned_count" not in st.session_state:
    st.session_state.last_scanned_count = 0

segment = st.sidebar.selectbox(
    "Select Targeted Market Segment:", 
    options=["Nifty 50 (Core Bluechip)", "Nifty Next 50 (High Momentum)", "Nifty Midcap 150"],
    key="selected_index"
)
run_scan = st.sidebar.button("Execute Structural Scanning Core", type="primary")

if segment == "Nifty 50 (Core Bluechip)": tickers = NIFTY_50
elif segment == "Nifty Next 50 (High Momentum)": tickers = NIFTY_NEXT_50
else: tickers = MIDCAP_150

if run_scan:
    fresh_portfolio = {}
    progress_bar = st.progress(0)
    
    for idx, sym in enumerate(tickers):
        progress_bar.progress((idx + 1) / len(tickers))
        df = fetch_indian_stock_data(sym, period="1y")
        
        if not df.empty:
            scan_res = scan_stock(df)
            if scan_res and scan_res != "NEUTRAL":
                _, metrics = scan_res
                
                metrics["Raw_Highs"] = [float(df[df['Date'] == pd.to_datetime(d).date()]['High'].iloc) if not df[df['Date'] == pd.to_datetime(d).date()].empty else metrics["Floor"] for d in metrics["Raw_Dates"]]
                metrics["Raw_Lows"] = [float(df[df['Date'] == pd.to_datetime(d).date()]['Low'].iloc) if not df[df['Date'] == pd.to_datetime(d).date()].empty else metrics["Floor"] for d in metrics["Raw_Dates"]]
                
                fresh_portfolio[sym] = metrics
                
    progress_bar.empty()
    st.session_state.active_portfolio = fresh_portfolio
    st.session_state.last_scanned_count = len(tickers)

# --- LIVE REFRESH DATA DISPLAY CORE ---
if st.session_state.active_portfolio:
    st.sidebar.divider()
    st.sidebar.subheader("Streaming Control")
    live_stream_active = st.sidebar.toggle("Enable Live 10s Auto-Update", value=True)
    
    compiled_rows = []
    for sym, stored_data in st.session_state.active_portfolio.items():
        live_df = fetch_indian_stock_data(sym, period="5d")
        if not live_df.empty:
            live_price = float(live_df.iloc[-1]['Close'])
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
                
            compiled_rows.append({
                "Ticker": sym,
                "Live Price": live_price,
                "Execution State": current_alert,
                "Optimal Buy Zone": f"₹{floor:.2f} - ₹{ceiling:.2f}",
                # UPGRADED: Explicitly labels High and Low parameters directly in the string format
                "FII/DII Buying Price": f"₹{stored_data['Block_Low']:.0f} (Low) - ₹{stored_data['Block_High']:.0f} (High)",
                "Profit Target": float(stored_data["Target"]),
                "Stop Loss (SL)": float(stored_data["SL"]),
                "ATR Level": float(stored_data["ATR"])
            })
            
    res_df = pd.DataFrame(compiled_rows)
    
    col_table, col_meta = st.columns() 
    
    with col_table:
        st.subheader(f"📊 Dynamic Execution Pipeline (Inspected {st.session_state.last_scanned_count} Stocks)")
        
        def style_execution(val):
            if val == '🔥 ENTER_ZONE': return 'background-color: #065F46; color: white; font-weight: bold;'
            elif val == '⏳ AWAIT_PULLBACK': return 'background-color: #1E3A8A; color: white; font-weight: bold;'
            elif val == '❌ INVALID_PASSED': return 'background-color: #991B1B; color: white; font-weight: bold;'
            return ''
            
        st.dataframe(
            res_df.style.map(style_execution, subset=['Execution State'])
                        .format({"Live Price": "₹{:.2f}", "Profit Target": "₹{:.2f}", "Stop Loss (SL)": "₹{:.2f}", "ATR Level": "{:.2f}"}),
            use_container_width=True,
            height=440 
        )
        
    with col_meta:
        st.subheader("🎯 Asset Deep-Dive")
        selected_ticker = st.selectbox("Inspect Asset:", options=res_df["Ticker"].unique())
        
        if selected_ticker in st.session_state.active_portfolio:
            target_data = st.session_state.active_portfolio[selected_ticker]
            dates = target_data["Raw_Dates"]
            highs = target_data.get("Raw_Highs", [target_data["Floor"]]*4)
            lows = target_data.get("Raw_Lows", [target_data["Floor"]]*4)
            
            st.markdown("**FII/DII Historical Limits [High / Low]:**")
            sub_cols = st.columns(3)
            for i, d_val in enumerate(dates[:3]):
                with sub_cols[i]:
                    st.error(f"🧱 **B{i+1}**")
                    st.caption(f"📅 {d_val}")
                    st.markdown(f"**H:** ₹{highs[i]:.0f}\n\n**L:** ₹{lows[i]:.0f}")

    # --- CLEAN CHART RENDER PASSTHRU ---
    st.divider()
    chart_df = fetch_indian_stock_data(selected_ticker, period="1y")
    if not chart_df.empty:
        target_meta = st.session_state.active_portfolio[selected_ticker]
        plot_df = chart_df.tail(60)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=plot_df['Date'], open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Price"))
        
        fig.add_hline(y=target_meta["Floor"], line_dash="dash", line_color="#065F46", line_width=2, annotation_text="Buy Zone Floor")
        fig.add_hline(y=target_meta["Target"], line_dash="dot", line_color="#1E3A8A", line_width=2, annotation_text="Target")
        fig.add_hline(y=target_meta["SL"], line_dash="solid", line_color="#991B1B", line_width=2, annotation_text="Hard SL")
        
        fig.update_layout(
            title=f"{selected_ticker} Live Structural Workspace", 
            template="plotly_dark", 
            height=450, 
            xaxis_rangeslider_visible=False
        )
        st.plotly_chart(fig, use_container_width=True)

    if live_stream_active:
        time.sleep(10)
        st.rerun()
else:
    st.info("System initialized. Select a market segment from the sidebar and execute the scan to spin up the real-time tracking matrix.")
