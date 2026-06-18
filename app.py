# app.py
import streamlit as st
import pandas as pd
from data_engine import fetch_indian_stock_data
from indicators import scan_stock

# --- HARDCODED SYMBOLS REGISTRY BYPASS ---
LARGE_CAP_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
    "BHARTIARTL", "SBIN", "LTIM", "HINDUNILVR", "ITC", 
    "LT", "BAJFINANCE", "MARUTI", "HCLTECH", "SUNPHARMA",
    "AXISBANK", "ADANIENT", "ULTRACEMCO", "TITAN", "NTPC", 
    "POWERGRID", "TATASTEEL", "ASIANPAINT", "COALINDIA", "M&M", 
    "JIOFIN", "INDIGO", "HAL", "ZOMATO", "ADANIPORTS"
]

MID_CAP_STOCKS = [
    "VOLTAS", "BEL", "OBEROIRLTY", "POLYCAB", "MAXHEALTH", 
    "PFC", "RECLTD", "PERSISTENT", "KPITTECH", "TATACOMM", 
    "CONCOR", "CUMMINSIND", "ASHOKLEY", "BALKRISIND", "DIXON",
    "SUPREMEIND", "ASTRAL", "MRF", "DALBHARAT", "BHARATFORG", 
    "LUPIN", "AUROPHARMA", "COFORGE", "MPHASIS", "PIIND",
    "NMDC", "SAIL", "GMRINFRA", "FEDERALBNK", "IDFCFIRSTB"
]

st.set_page_config(page_title="Advanced NSE Swing Scanner", layout="wide")

st.title("🇮🇳 Indian Market Swing & Footprint Scanner")
st.caption("Automated Multi-Cap Scanning for 5-8 Day Holds with Target & SL Management")

# --- Control Panel ---
segment = st.sidebar.radio("Select Market Segment:", ["Large-Cap (Nifty 100)", "Mid-Cap (Nifty 150)", "All Combined"])
run_scan = st.sidebar.button("Execute Live Market Scan", type="primary")

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
                        "Current Price": float(df.iloc[-1]['Close']),
                        "Scanner Alert": status,
                        "FII/DII Entry Date": info["Footprint_Date"],
                        "FII/DII Support Zone": info["Footprint_Zone"],
                        "5-8 Day Target": float(info["Target"]),
                        "Stop Loss (SL)": float(info["SL"]),
                        "ATR Volatility": float(info["ATR"])
                    })
                    
    progress_bar.empty()
    
    if results:
        st.subheader("📊 Found Actionable Structural Opportunities")
        res_df = pd.DataFrame(results)
        
        # Color coding highlighter for different setup triggers
        def style_alerts(val):
            if val == 'STRONG_BUY_SIGNAL':
                return 'background-color: #991B1B; color: white; font-weight: bold;' # Deep Red/Crimson for alert urgency
            elif val == 'INSTITUTIONAL_RETEST':
                return 'background-color: #065F46; color: white; font-weight: bold;' # Emerald Green
            return ''
            
        st.dataframe(
            res_df.style.map(style_alerts, subset=['Scanner Alert'])
                        .format({"Current Price": "₹{:.2f}", "5-8 Day Target": "₹{:.2f}", "Stop Loss (SL)": "₹{:.2f}", "ATR Volatility": "{:.2f}"}),
            use_container_width=True
        )
    else:
        st.info("Scan complete. No stocks are currently entering consolidation retests or deep short-term pullbacks.")
else:
    st.info("Click **'Execute Live Market Scan'** in the sidebar panel to check momentum pullbacks across segments.")
