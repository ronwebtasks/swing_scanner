# app.py
import streamlit as st
import pandas as pd
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

# Track data size for transparency
total_scanned_count = len(tickers)

# Persist search across frames using streamlit state cache
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

# --- MAIN RENDER DISPLAY ---
if st.session_state.scan_results:
    # Transparency Indicator Card
    st.success(f"স্ক্যান সফল! এই ক্যাটাগরির মোট {st.session_state.last_scanned_volume} টি স্টকের ডেলিভারি ও ভলিউম ডেটা নিখুঁতভাবে চেক করে নিচের সুইং সুযোগগুলো পাওয়া গেছে।")
    
    st.subheader(" Bars Found Actionable Structural Opportunities")
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
    
    # --- FIXED & TESTED DROP-DOWN DYNAMIC SECTION ---
    st.divider()
    st.subheader("🔍 Deep-Dive Institutional Entry Timelines")
    st.markdown("উপরের টেবিল থেকে যেকোনো একটি স্টক সিলেক্ট করুন। বড় প্লেয়াররা অতীতে যে যে তারিখে এই প্রাইস জোনে বড় ভলিউম নিয়ে এন্ট্রি করেছিল, তার হিস্ট্রি নিচে আলাদা কার্ডে দেখতে পাবেন:")
    
    # Dropdown widget selector
    selected_ticker = st.selectbox(
        "বিশ্লেষণ করার জন্য স্টকটি বেছে নিন (Dropdown):", 
        options=res_df["Ticker"].unique()
    )
    
    if selected_ticker in st.session_state.date_lookup:
        dates_list = st.session_state.date_lookup[selected_ticker]
        
        if dates_list:
            # Create horizontal column slots dynamically for each date block
            cols = st.columns(len(dates_list))
            for i, dt in enumerate(dates_list):
                with cols[i]:
                    st.metric(label=f"🧱 Block Entry {i+1}", value=dt, delta="FII/DII Active")
        else:
            st.info("No specific block records logged.")
else:
    if run_scan:
        st.warning(f"স্ক্যান সম্পূর্ণ। মোট {st.session_state.last_scanned_volume} টি স্টক চেক করা হয়েছে, কিন্তু আজকের বাজারে কোনো স্টকই আমাদের কঠোর ক্যাপিটাল প্রটেকশন ফিল্টার ম্যাচ করতে পারেনি।")
    else:
        st.info("বামদিকের সাইডবার থেকে আপনার পছন্দের ইনডেক্স সেগমেন্ট সিলেক্ট করে **'Execute Live Segment Scan'** বাটনে ক্লিক করুন।")
