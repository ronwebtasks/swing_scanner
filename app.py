# app.py
import streamlit as st
import pandas as pd
from symbols import LARGE_CAP_STOCKS, MID_CAP_STOCKS
from data_engine import fetch_indian_stock_data
from indicators import scan_stock

st.set_page_config(page_title="NSE Swing & Footprint Scanner", layout="wide")

st.title("🇮🇳 Indian Market Swing & Footprint Scanner")
st.caption("Automated Multi-Cap Scanning for 5-8 Day Holds")

# --- Control Panel ---
segment = st.sidebar.radio("Select Market Segment:", ["Large-Cap (Nifty 100)", "Mid-Cap (Nifty 150)", "All Combined"])
run_scan = st.sidebar.button("Execute Live Market Scan", type="primary")

# Assemble stock list based on selection
if segment == "Large-Cap (Nifty 100)":
    tickers = LARGE_CAP_STOCKS
elif segment == "Mid-Cap (Nifty 150)":
    tickers = MID_CAP_STOCKS
else:
    tickers = LARGE_CAP_STOCKS + MID_CAP_STOCKS

if run_scan:
    results = []
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
                        "Current Price": f"₹{df.iloc[-1]['Close']:.2f}",
                        "Scanner Alert": status,
                        "FII/DII Zone Support": info["Footprint_Zone"],
                        "ATR (Volatility)": info["ATR"]
                    })
                    
    progress_bar.empty()
    
    if results:
        st.subheader("📊 Found Actionable Structural Opportunities")
        res_df = pd.DataFrame(results)
        
        # Color coding highlighter for different setup triggers
        def style_alerts(val):
            color = '#1E3A8A' if val == 'SWING_BUY_ALERT' else '#065F46'
            return f'background-color: {color}; color: white; font-weight: bold;'
            
        st.dataframe(res_df.style.map(style_alerts, subset=['Scanner Alert']), use_container_width=True)
    else:
        st.info("Scan complete. No stocks are currently entering consolidation retests or deep short-term pullbacks.")
else:
    st.info("Click **'Execute Live Market Scan'** in the sidebar panel to check momentum pullbacks across segments.")
