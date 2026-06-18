# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

def scan_stock(df):
    """
    Evaluates 5-8 day swing trends and institutional foot-printing anomalies.
    Returns calculated levels for advanced target, sl, and strong buy signals.
    """
    if len(df) < 60:
        return None
        
    # Standard Technical Calculations
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df['RSI_3'] = ta.rsi(df['Close'], length=3)
    df['CCI_14'] = ta.cci(df['High'], df['Low'], df['Close'], length=14)
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['Vol_MA50'] = ta.sma(df['Volume'], length=50)
    
    # Calculate Institutional Footprint Zones
    candle_range = (df['High'] - df['Low']).replace(0, 0.01)
    df['Close_Loc'] = (df['Close'] - df['Low']) / candle_range
    # Heavy Volume: 2.2x above 50MA and closing in the upper 70% of day's range
    df['Footprint'] = (df['Volume'] > (2.2 * df['Vol_MA50'])) & (df['Close_Loc'] > 0.70)
    
    latest = df.iloc[-1]
    prev_lookback = df.iloc[-4:-1]
    current_close = latest['Close']
    atr = latest['ATR_14']
    
    # Core Strategy Logic
    is_trending = latest['Close'] > latest['EMA_50'] and latest['EMA_50'] > latest['EMA_200']
    is_oversold = latest['RSI_3'] < 30
    had_momentum = any(prev_lookback['CCI_14'] > 100)
    
    # Extract Latest Footprint
    footprint_idx = df[df['Footprint'] == True].index
    
    status = "NEUTRAL"
    metrics = {
        "ATR": round(atr, 2),
        "Footprint_Zone": "None",
        "Footprint_Date": "None",
        "Target": 0.0,
        "SL": 0.0
    }
    
    if len(footprint_idx) > 0:
        last_footprint_row = df.loc[footprint_idx[-1]]
        zone_price = (last_footprint_row['High'] + last_footprint_row['Low']) / 2
        f_date = last_footprint_row['Date']
        
        metrics["Footprint_Zone"] = f"₹{zone_price:.2f}"
        metrics["Footprint_Date"] = str(f_date)
        
        # Check if price is within 2% of the FII/DII average cost zone
        is_near_zone = current_close >= (zone_price * 0.985) and current_close <= (zone_price * 1.02)
        is_low_vol_pullback = latest['Volume'] < latest['Vol_MA50']
        
        if is_near_zone and is_low_vol_pullback:
            status = "INSTITUTIONAL_RETEST"
            # Mathematical Target & SL optimized for 5-8 day hold
            metrics["SL"] = round(zone_price * 0.97, 2) # 3% below institutional concrete floor
            metrics["Target"] = round(current_close + (2.5 * atr), 2) # 2.5x ATR dynamic profit target
            
            # UPGRADE TO STRONG BUY: If it triggers retest AND short-term chart is oversold in an uptrend
            if is_trending and is_oversold and had_momentum:
                status = "STRONG_BUY_SIGNAL"
                
    return status, metrics
