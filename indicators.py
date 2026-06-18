# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

def scan_stock(df):
    """
    STRICT CAP-PROTECTED SWING ENGINE.
    Extracts multi-date historical FII/DII price coordinates for exact UI tracking.
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
    df['Footprint'] = (df['Volume'] > (2.2 * df['Vol_MA50'])) & (df['Close_Loc'] > 0.70)
    
    latest = df.iloc[-1]
    prev_lookback = df.iloc[-4:-1]
    current_close = latest['Close']
    atr = latest['ATR_14']
    
    is_trending = current_close > df['EMA_50'].iloc[-1] and df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]
    is_oversold = latest['RSI_3'] < 30
    had_momentum = any(prev_lookback['CCI_14'] > 100)
    
    footprint_rows = df[df['Footprint'] == True]
    
    if footprint_rows.empty:
        return None
        
    recent_footprints = footprint_rows.tail(4)
    
    # NEW: Store pairs of {"date": "DD-MM-YYYY", "price": float}
    historical_blocks = []
    for _, row in recent_footprints.iterrows():
        formatted_date = pd.to_datetime(row['Date']).strftime('%d-%m-%Y')
        calculated_cost = (row['High'] + row['Low']) / 2
        historical_blocks.append({
            "date": formatted_date,
            "price": round(calculated_cost, 2)
        })
    historical_blocks.reverse() # Show most recent block first
    
    last_footprint_row = recent_footprints.iloc[-1]
    zone_floor = (last_footprint_row['High'] + last_footprint_row['Low']) / 2
    zone_ceiling = zone_floor * 1.005
    
    status = "NEUTRAL"
    if current_close >= (zone_floor * 0.96) and current_close <= (zone_floor * 1.05):
        status = "INSTITUTIONAL_RETEST"
        if is_trending and is_oversold and had_momentum:
            status = "STRONG_BUY_SIGNAL"
            
    metrics = {
        "ATR": round(atr, 2),
        "Floor": round(zone_floor, 2),
        "Ceiling": round(zone_ceiling, 2),
        "Blocks_Data": historical_blocks, # Upgraded tracking array
        "Target": round(current_close + (2.5 * atr), 2),
        "SL": round(zone_floor * 0.97, 2),
        "Base_Status": status
    }
    
    return status, metrics
