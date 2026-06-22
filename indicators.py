# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

MIN_BARS_REQUIRED = 210  # ensures EMA_200 has enough data to not be NaN


def scan_stock(df: pd.DataFrame):
    """
    Cap-protected swing engine.

    Detects high-volume, strong-close candles ("footprints") as a PRICE-ACTION
    PROXY for possible institutional accumulation. This is NOT real FII/DII
    cash-market data -- it's inferred from volume + close location only.
    For genuine confirmation, cross-check footprint dates against NSE bulk/block
    deal reports or delivery % data.

    Returns:
        None if no qualifying setup is found (including NEUTRAL status).
        (status, metrics) tuple if a footprint zone exists and isn't neutral.
    """
    if len(df) < MIN_BARS_REQUIRED:
        return None

    df = df.copy()
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

    # Guard against NaN indicator values (can happen near the start of a series)
    required_fields = ['EMA_50', 'EMA_200', 'RSI_3', 'ATR_14']
    if latest[required_fields].isna().any():
        return None

    prev_lookback = df.iloc[-4:-1]
    current_close = float(latest['Close'])
    atr = float(latest['ATR_14'])

    if atr <= 0:
        return None

    is_trending = current_close > latest['EMA_50'] and latest['EMA_50'] > latest['EMA_200']
    is_oversold = latest['RSI_3'] < 30
    had_momentum = bool((prev_lookback['CCI_14'] > 100).any())

    footprint_rows = df[df['Footprint'] == True]

    if footprint_rows.empty:
        return None

    recent_footprints = footprint_rows.tail(4)

    historical_blocks = []
    for _, row in recent_footprints.iterrows():
        formatted_date = pd.to_datetime(row['Date']).strftime('%d-%m-%Y')
        calculated_cost = (row['High'] + row['Low']) / 2
        historical_blocks.append({
            "date": formatted_date,
            "price": round(float(calculated_cost), 2)
        })
    historical_blocks.reverse()  # most recent block first

    last_footprint_row = recent_footprints.iloc[-1]
    zone_floor = float((last_footprint_row['High'] + last_footprint_row['Low']) / 2)
    # Ceiling scaled to volatility instead of a flat 0.5% -- gives a more
    # realistic entry band on higher-ATR (more volatile) names.
    zone_ceiling = round(zone_floor + (0.3 * atr), 2)

    status = "NEUTRAL"
    if (zone_floor * 0.96) <= current_close <= (zone_floor * 1.05):
        status = "INSTITUTIONAL_RETEST"
        if is_trending and is_oversold and had_momentum:
            status = "STRONG_BUY_SIGNAL"

    if status == "NEUTRAL":
        return None  # don't let neutral setups leak into the scanned portfolio

    # Stop loss tied to ATR (consistent with the ATR-based Target) instead of
    # a flat 3% of the zone floor, so risk reflects each stock's own volatility.
    stop_loss = round(min(zone_floor * 0.97, current_close - (1.5 * atr)), 2)

    metrics = {
        "ATR": round(atr, 2),
        "Floor": round(zone_floor, 2),
        "Ceiling": zone_ceiling,
        "Blocks_Data": historical_blocks,
        "Target": round(current_close + (2.5 * atr), 2),
        "SL": stop_loss,
        "Base_Status": status
    }

    return status, metrics
