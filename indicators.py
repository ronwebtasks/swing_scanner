# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

def scan_stock(df):
    """
    STRICT RISK MANAGEMENT MODEL FOR LARGE CAPITAL DEPLOYMENT.
    Filters out noise, ensures high volume absorption and tight support retests.
    """
    if len(df) < 60:
        return None
        
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df['RSI_3'] = ta.rsi(df['Close'], length=3)
    df['CCI_14'] = ta.cci(df['High'], df['Low'], df['Close'], length=14)
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['Vol_MA50'] = ta.sma(df['Volume'], length=50)
    
    candle_range = (df['High'] - df['Low']).replace(0, 0.01)
    df['Close_Loc'] = (df['Close'] - df['Low']) / candle_range
    
    # STRICT CAPITAL PROTECTION: 2.2x Volume & High institutional close position
    df['Footprint'] = (df['Volume'] > (2.2 * df['Vol_MA50'])) & (df['Close_Loc'] > 0.70)
    
    latest = df.iloc[-1]
    prev_lookback = df.iloc[-4:-1]
    current_close = latest['Close']
    atr = latest['ATR_14']
    
    # Structural Trend Guard (Price must be strictly in an intermediate bullish regime)
    is_trending = current_close > df['EMA_50'].iloc[-1] and df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]
    is_oversold = latest['RSI_3'] < 30 # Deep short-term pullback
    had_momentum = any(prev_lookback['CCI_14'] > 100)
    
    footprint_rows = df[df['Footprint'] == True]
    
    status = "NEUTRAL"
    metrics = {
        "ATR": round(atr, 2),
        "Footprint_Zone": "None",
        "Raw_Dates": [],
        "Target": 0.0,
        "SL": 0.0
    }
    
    if not footprint_rows.empty:
        recent_footprints = footprint_rows.tail(4)
        
        for d in recent_footprints['Date']:
            metrics["Raw_Dates"].append(pd.to_datetime(d).strftime('%d-%m-%Y'))
        metrics["Raw_Dates"].reverse()
        
        last_footprint_row = recent_footprints.iloc[-1]
        zone_price = (last_footprint_row['High'] + last_footprint_row['Low']) / 2
        metrics["Footprint_Zone"] = f"₹{zone_price:.2f}"
        
        # TIGHT ENTRY BOUNDARY: Max 2% from the institutional cost floor
        is_near_zone = current_close >= (zone_price * 0.985) and current_close <= (zone_price * 1.02)
        is_low_vol_pullback = latest['Volume'] < latest['Vol_MA50'] # Institutions are not selling
        
        if is_near_zone and is_low_vol_pullback:
            status = "INSTITUTIONAL_RETEST"
            # Tight and logical Stop Loss (3% below the institutional average floor)
            metrics["SL"] = round(zone_price * 0.97, 2)
            metrics["Target"] = round(current_close + (2.5 * atr), 2)
            
            # THE HOLY GRAIL SETUP: Strict Trend + FII Retest + RSI Oversold
            if is_trending and is_oversold and had_momentum:
                status = "STRONG_BUY_SIGNAL"
                
    return status, metrics
