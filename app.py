import streamlit as st
import datetime
from data_engine import fetch_indian_stock_data

# Set wide layout so charts look expansive and professional
st.set_page_config(page_title="Indian Market Swing & Footprint Scanner", layout="wide")

st.title("🇮🇳 Indian Stock Market Swing Scanner")
st.caption("High-Accuracy 5-8 Day Momentum Pullbacks & Institutional FII/DII Footprint Trackers")

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("Configuration Panel")

# Default high-liquidity stock input for initial testing
ticker_input = st.sidebar.text_input("Enter NSE Ticker Symbol:", value="RELIANCE")
lookback_period = st.sidebar.selectbox("Select Historical Data Depth:", options=["6m", "1y", "2y"], index=1)

st.sidebar.divider()
st.sidebar.info("Next steps will integrate automated scans across the entire Nifty 200 universe.")

# --- MAIN APP INTERFACE ---
if ticker_input:
    with st.spinner(f"Fetching market data for {ticker_input.upper()}..."):
        # Trigger data pipeline
        stock_df = fetch_indian_stock_data(ticker_input, period=lookback_period)
        
    if not stock_df.empty:
        st.success(f"Successfully loaded {len(stock_df)} trading sessions for {ticker_input.upper()}.")
        
        # Display summary cards of the most recent trading session
        latest_row = stock_df.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Last Close Price", f"₹{latest_row['Close']:.2f}")
        col2.metric("Day High", f"₹{latest_row['High']:.2f}")
        col3.metric("Day Low", f"₹{latest_row['Low']:.2f}")
        col4.metric("Volume Traded", f"{int(latest_row['Volume']):,}")
        
        # Preview raw dataframe structure
        st.subheader("Historical Data Preview")
        st.dataframe(stock_df.tail(10), use_container_width=True)
    else:
        st.error("No stock data found. Please verify the symbol name (e.g., RELIANCE, TCS, HDFCBANK).")
