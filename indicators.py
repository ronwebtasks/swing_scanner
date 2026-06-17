# indicators.py
import pandas as pd
import pandas_ta as ta
import numpy as np

def scan_stock(df):
    """
    Evaluates 5-8 day swing trends and institutional foot-printing anomalies.
    """
    if len(df) < 60:
        return None
        
    # Standard Technical Math
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df['RSI_3'] = ta.rsi(df['Close'], length=3)
    df['CCI_14'] = ta.cci(df['High'], df['Low'], df['Close'], length=14)
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['Vol_MA50'] = ta.sma(df['Volume'], length=50)
    
    # Calculate Institutional Footprint Zones
    candle_range = (df['High'] - df['Low']).replace(0, 0.01)
    df['Close_Loc'] = (df['Close'] - df['Low']) / candle_range
    df['Footprint'] = (df['Volume'] > (2.2 * df['Vol_MA50'])) & (df['Close_Loc'] > 0.70)
    
    latest = df.iloc[-1]
    prev_lookback = df.iloc[-4:-1]
    
    # Check Strategies
    is_trending = latest['Close'] > latest['EMA_50'] and latest['EMA_50'] > latest['EMA_200']
    is_swing_pullback = latest['RSI_3'] < 30 and any(prev_lookback['CCI_14'] > 100)
    
    # Footprint Extraction
    footprint_idx = df[df['Footprint'] == True].index
    has_footprint = len(footprint_idx) > 0
    
    status = "NEUTRAL"
    metrics = {"ATR": round(latest['ATR_14'], 2), "Footprint_Zone": "None"}
    
    if has_footprint:
        last_footprint_row = df.loc[footprint_idx[-1]]
        zone_price = (last_footprint_row['High'] + last_footprint_row['Low']) / 2
        metrics["Footprint_Zone"] = f"₹{zone_price:.2f}"
        
        # Pullback to Institutional Zone condition
        if latest['Close'] >= (zone_price * 0.99) and latest['Close'] <= (zone_price * 1.02) and latest['Volume'] < latest['Vol_MA50']:
            status = "INSTITUTIONAL_RETEST"
            
    if is_trending and is_swing_pullback:
        status = "SWING_BUY_ALERT"
        
    return status, metrics
