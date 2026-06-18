# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

def scan_stock(df):
    """
    Evaluates 5-8 day swing trends and captures MULTIPLE institutional entry dates.
    Formats dates into DD-MM-YYYY format.
    """
    if len(df) < 60:
        return None
        
    # Technical Calculations
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
    current_close = latest['Close']
    atr = latest['ATR_14']
    
    is_trending = latest['Close'] > latest['EMA_50'] and latest['EMA_50'] > latest['EMA_200']
    is_oversold = latest['RSI_3'] < 30
    had_momentum = any(prev_lookback['CCI_14'] > 100)
    
    # Extract ALL Footprint Days instead of just the last one
    footprint_rows = df[df['Footprint'] == True]
    
    status = "NEUTRAL"
    metrics = {
        "ATR": round(atr, 2),
        "Footprint_Zone": "None",
        "All_Entry_Dates": "None",
        "Target": 0.0,
        "SL": 0.0
    }
    
    if not footprint_rows.empty:
        # Take up to the last 4 major institutional entry points
        recent_footprints = footprint_rows.tail(4)
        
        # Convert all those dates to DD-MM-YYYY format and join them as a list
        formatted_dates = []
        for d in recent_footprints['Date']:
            # Handle string or datetime object safely
            dt = pd.to_datetime(d)
            formatted_dates.append(dt.strftime('%d-%m-%Y'))
            
        # Reverse the list so the most recent date stays first
        formatted_dates.reverse()
        metrics["All_Entry_Dates"] = " ── ".join(formatted_dates)
        
        # Base the support calculation on the most recent accumulation node
        last_footprint_row = recent_footprints.iloc[-1]
        zone_price = (last_footprint_row['High'] + last_footprint_row['Low']) / 2
        metrics["Footprint_Zone"] = f"₹{zone_price:.2f}"
        
        is_near_zone = current_close >= (zone_price * 0.985) and current_close <= (zone_price * 1.02)
        is_low_vol_pullback = latest['Volume'] < latest['Vol_MA50']
        
        if is_near_zone and is_low_vol_pullback:
            status = "INSTITUTIONAL_RETEST"
            metrics["SL"] = round(zone_price * 0.97, 2)
            metrics["Target"] = round(current_close + (2.5 * atr), 2)
            
            if is_trending and is_oversold and had_momentum:
                status = "STRONG_BUY_SIGNAL"
                
    return status, metrics
