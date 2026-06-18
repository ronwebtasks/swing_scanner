# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from symbols import NIFTY_50, NIFTY_NEXT_50, MIDCAP_150
from data_engine import fetch_indian_stock_data
from indicators import scan_stock

st.set_page_config(page_title="Advanced NSE Capital Protected Scanner", layout="wide")

st.title("🇮🇳 Indian Market Segment Swing Scanner")
st.caption("Strict Risk-Managed Scanning for Large & Mid Cap Assets")

# --- Interactive Sidebar Controls ---
segment = st.sidebar.selectbox(
    "Select Targeted Market Segment:", 
    options=["Nifty 50 (Core Bluechip)", "Nifty Next 50 (High Momentum)", "Nifty Midcap 150", "Complete Combined Market Universe"]
)
run_scan = st.sidebar.button("Execute Live Segment Scan", type="primary")

# Route tickers based on selection
if segment == "Nifty 50 (Core Bluechip)":
    tickers = NIFTY_50
elif segment == "Nifty Next 50 (High Momentum)":
    tickers = NIFTY_NEXT_50
elif segment == "Nifty Midcap 150":
    tickers = MIDCAP_150
else:
    tickers = NIFTY_50 + NIFTY_NEXT_50 + MIDCAP_150

total_scanned_count = len(tickers)

# Persist search across frames using streamlit session state cache
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "date_lookup" not in st.session_state:
    st.session_state.date_lookup = {}
if "last_scanned_volume" not in st.session_state:
    st.session_state.last_scanned_volume = 0

if run_scan:
    results = []
    lookup = {}
    progress_bar = st.progress(0)
    
    for idx, sym in enumerate(tickers):
        progress_bar.progress((idx + 1) / len(tickers))
        df = fetch_indian_stock_data(sym, period="1y")
        
        if not df.empty:
            scan_res = scan_stock(df)
            if scan_res:
                status, info = scan_res
                if status != "NEUTRAL":
                    results.append({
                        "Ticker": sym,
                        "Current Price": float(df.iloc[-1]['Close']),
                        "Scanner Alert": status,
                        "FII/DII Support Zone": info["Footprint_Zone"],
                        "5-8 Day Target": float(info["Target"]),
                        "Stop Loss (SL)": float(info["SL"]),
                        "ATR Volatility": float(info["ATR"])
                    })
                    lookup[sym] = info["Raw_Dates"]
                    
    progress_bar.empty()
    st.session_state.scan_results = results
    st.session_state.date_lookup = lookup
    st.session_state.last_scanned_volume = total_scanned_count

# --- MAIN RENDER DISPLAY PANEL ---
if st.session_state.scan_results:
    st.success(f"Scan Successful! Processed delivery and volume matrices for {st.session_state.last_scanned_volume} assets across the index cluster.")
    
    st.subheader("📊 Found Actionable Structural Opportunities")
    res_df = pd.DataFrame(st.session_state.scan_results)
    
    def style_alerts(val):
        if val == 'STRONG_BUY_SIGNAL': return 'background-color: #991B1B; color: white; font-weight: bold;'
        elif val == 'INSTITUTIONAL_RETEST': return 'background-color: #065F46; color: white; font-weight: bold;'
        return ''
        
    st.dataframe(
        res_df.style.map(style_alerts, subset=['Scanner Alert'])
                    .format({"Current Price": "₹{:.2f}", "5-8 Day Target": "₹{:.2f}", "Stop Loss (SL)": "₹{:.2f}", "ATR Volatility": "{:.2f}"}),
        use_container_width=True
    )
    
    # --- INTERACTIVE DEEP-DIVE TIMELINE AND CHARTS PANEL ---
    st.divider()
    st.subheader("🔍 Technical Deep-Dive & Visual Workspace")
    
    selected_ticker = st.selectbox(
        "Select a Ticker from the found setups to generate live institutional charts:", 
        options=res_df["Ticker"].unique()
    )
    
    # Render Timeline Blocks
    if selected_ticker in st.session_state.date_lookup:
        dates_list = st.session_state.date_lookup[selected_ticker]
        if dates_list:
            st.markdown("**Historical Institutional Block Entry Timelines:**")
            cols = st.columns(len(dates_list))
            for i, dt in enumerate(dates_list):
                with cols[i]:
                    st.metric(label=f"🧱 Block Entry {i+1}", value=dt, delta="FII/DII Active")
                    
    # --- FETCH AND PLOT INTERACTIVE CANDLESTICK CHART ---
    with st.spinner(f"Generating institutional chart for {selected_ticker}..."):
        chart_df = fetch_indian_stock_data(selected_ticker, period="1y")
        
    if not chart_df.empty:
        # Get specific target lines from table matching selected stock
        stock_meta = res_df[res_df["Ticker"] == selected_ticker].iloc[0]
        support_val = float(stock_meta["FII/DII Support Zone"].replace("₹", ""))
        target_val = float(stock_meta["5-8 Day Target"])
        sl_val = float(stock_meta["Stop Loss (SL)"])
        
        # Take last 90 trading sessions to keep the chart clean and highly visible
        plot_df = chart_df.tail(90)
        
        fig = go.Figure()
        
        # Candlestick tracking
        fig.add_trace(go.Candlestick(
            x=plot_df['Date'], open=plot_df['Open'], high=plot_df['High'],
            low=plot_df['Low'], close=plot_df['Close'], name="Price Action"
        ))
        
        # Add Horizontal FII/DII Support Line
        fig.add_hline(y=support_val, line_dash="dash", line_color="#065F46", line_width=2.5, 
                      annotation_text=f"FII/DII Support Floor (₹{support_val:.2f})", annotation_position="top left")
        
        # Add Horizontal Target Line
        fig.add_hline(y=target_val, line_dash="dot", line_color="#1E3A8A", line_width=2, 
                      annotation_text=f"5-8 Day Profit Target (₹{target_val:.2f})", annotation_position="bottom right")
        
        # Add Horizontal Stop Loss Line
        fig.add_hline(y=sl_val, line_dash="solid", line_color="#991B1B", line_width=2, 
                      annotation_text=f"Risk Ceiling / SL Floor (₹{sl_val:.2f})", annotation_position="bottom left")
        
        fig.update_layout(
            title=f"{selected_ticker} Institutional Retest Visual Map (Last 90 Sessions)",
            xaxis_title="Trading Timeline", yaxis_title="Price (INR)",
            xaxis_rangeslider_visible=False, height=550, template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)
else:
    if run_scan:
        st.warning(f"Scan complete. Inspected {st.session_state.last_scanned_volume} tickers. No current assets match our strict capital defense thresholds today.")
    else:
        st.info("Please select a targeted index segment from the sidebar control panel and click **'Execute Live Segment Scan'** to launch the tracking array.")
