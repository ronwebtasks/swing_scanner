# indicators.py
import pandas as pd
import pandas_ta_classic as ta
import numpy as np

MIN_BARS_REQUIRED = 210

# Momentum-burst (squeeze + breakout) params
SQUEEZE_LOOKBACK = 120
SQUEEZE_PERCENTILE = 0.25
BREAKOUT_WINDOW = 10
BREAKOUT_VOL_MULTIPLIER = 1.5


def _detect_momentum_burst(df: pd.DataFrame) -> dict | None:
    """
    Looks for a volatility-contraction (squeeze) followed by a volume-backed
    breakout -- a pattern more associated with FAST, short-horizon moves
    (days, not weeks) than slow mean-reversion setups. Still NOT a guarantee
    of any move in a fixed number of days -- just a higher-probability
    short-term continuation pattern.
    """
    sma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    bb_width_pct = (bb_upper - bb_lower) / sma20

    squeeze_threshold = bb_width_pct.rolling(SQUEEZE_LOOKBACK).quantile(SQUEEZE_PERCENTILE)
    was_squeezed_recently = (bb_width_pct.rolling(10).min() <= squeeze_threshold).iloc[-1]

    prior_high = df['High'].rolling(BREAKOUT_WINDOW).max().shift(1)
    latest = df.iloc[-1]

    breakout_today = latest['Close'] > prior_high.iloc[-1]
    volume_confirmed = latest['Volume'] > (BREAKOUT_VOL_MULTIPLIER * latest['Vol_MA50'])
    above_trend = latest['Close'] > latest['EMA_50']

    if not (was_squeezed_recently and breakout_today and volume_confirmed and above_trend):
        return None

    atr = float(latest['ATR_14'])
    if atr <= 0:
        return None

    current_close = float(latest['Close'])
    breakout_level = float(prior_high.iloc[-1])

    entry_floor = round(breakout_level, 2)
    entry_ceiling = round(current_close + (0.3 * atr), 2)
    stop_loss = round(min(breakout_level - (0.5 * atr), current_close - (1.2 * atr)), 2)
    target = round(current_close + (2.0 * atr), 2)

    return {
        "ATR": round(atr, 2),
        "Floor": entry_floor,
        "Ceiling": entry_ceiling,
        "Blocks_Data": [{
            "date": pd.to_datetime(latest['Date']).strftime('%d-%m-%Y'),
            "price": round(current_close, 2)
        }],
        "Target": target,
        "SL": stop_loss,
        "Base_Status": "MOMENTUM_BURST_CANDIDATE",
        "Setup_Type": "⚡ Momentum Burst (fast)"
    }


def scan_stock(df: pd.DataFrame, vol_multiplier: float = 1.8, close_loc_threshold: float = 0.62):
    """
    Cap-protected swing engine. Checks for a momentum-burst (fast move) setup
    FIRST since that's the short-horizon pattern; falls back to the
    institutional-retest (slower, pullback-style) setup if no burst is found.

    vol_multiplier / close_loc_threshold control how strict the footprint
    (FII/DII proxy) detection is for the institutional-retest path:
        Strict:   vol_multiplier=2.2, close_loc_threshold=0.70  (fewer, higher-conviction blocks)
        Balanced: vol_multiplier=1.8, close_loc_threshold=0.62  (default)
        Relaxed:  vol_multiplier=1.5, close_loc_threshold=0.55  (more blocks, lower conviction each)

    NOTE: "footprints" here are a PRICE-ACTION PROXY (volume spike + strong
    close), not actual disclosed FII/DII trade data.

    Returns:
        None if no qualifying setup is found.
        (status, metrics) tuple otherwise.
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

    latest = df.iloc[-1]
    required_fields = ['EMA_50', 'EMA_200', 'RSI_3', 'ATR_14', 'Vol_MA50']
    if latest[required_fields].isna().any():
        return None

    # --- Check 1: Momentum Burst (fast, short-horizon) ---
    burst_metrics = _detect_momentum_burst(df)
    if burst_metrics:
        return "MOMENTUM_BURST_CANDIDATE", burst_metrics

    # --- Check 2: Institutional Retest (slower, pullback-style) ---
    candle_range = (df['High'] - df['Low']).replace(0, 0.01)
    df['Close_Loc'] = (df['Close'] - df['Low']) / candle_range
    df['Footprint'] = (df['Volume'] > (vol_multiplier * df['Vol_MA50'])) & (df['Close_Loc'] > close_loc_threshold)

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
    zone_ceiling = round(zone_floor + (0.3 * atr), 2)

    status = "NEUTRAL"
    if (zone_floor * 0.96) <= current_close <= (zone_floor * 1.05):
        status = "INSTITUTIONAL_RETEST"
        if is_trending and is_oversold and had_momentum:
            status = "STRONG_BUY_SIGNAL"

    if status == "NEUTRAL":
        return None

    stop_loss = round(min(zone_floor * 0.97, current_close - (1.5 * atr)), 2)

    metrics = {
        "ATR": round(atr, 2),
        "Floor": round(zone_floor, 2),
        "Ceiling": zone_ceiling,
        "Blocks_Data": historical_blocks,
        "Target": round(current_close + (2.5 * atr), 2),
        "SL": stop_loss,
        "Base_Status": status,
        "Setup_Type": "🐢 Institutional Retest (slower)"
    }

    return status, metrics
