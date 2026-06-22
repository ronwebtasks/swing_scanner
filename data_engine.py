# data_engine.py
import time
import logging
import streamlit as st
import yfinance as yf
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}


def _normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    return symbol


def _with_retry(fn, retries: int = 2, delay: float = 1.5):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == retries:
                logger.warning(f"Failed after {retries} retries: {e}")
                return None
            time.sleep(delay)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_indian_stock_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    Fetches daily historical OHLCV data for an Indian stock from Yahoo Finance.
    Cached for 5 minutes to avoid redundant network calls.

    Parameters:
        symbol (str): Stock ticker (e.g., 'RELIANCE', 'TCS', 'INFY')
        period (str): Lookback period, e.g. '6mo', '1y', '2y' (must be a valid yfinance period)

    Returns:
        pd.DataFrame: Columns = Date, Open, High, Low, Close, Volume
    """
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period '{period}'. Use one of {sorted(VALID_PERIODS)}")

    ticker_symbol = _normalize_symbol(symbol)

    def _fetch():
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval="1d", auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df

    result = _with_retry(_fetch)
    if result is None:
        logger.warning(f"Error fetching data for ticker {ticker_symbol}")
        return pd.DataFrame()
    return result


@st.cache_data(ttl=8, show_spinner=False)
def fetch_live_price(symbol: str) -> float | None:
    """
    Lightweight fetch of just the latest traded price (no full OHLCV history).
    Cached for 8 seconds to match your 10s auto-refresh without hammering Yahoo.

    Parameters:
        symbol (str): Stock ticker (e.g., 'RELIANCE')

    Returns:
        float | None: Latest price, or None if unavailable.
    """
    ticker_symbol = _normalize_symbol(symbol)

    def _fetch():
        fast = yf.Ticker(ticker_symbol).fast_info
        price = fast.get("lastPrice") if hasattr(fast, "get") else fast["lastPrice"]
        return float(price)

    result = _with_retry(_fetch)
    if result is None:
        logger.warning(f"Error fetching live price for {ticker_symbol}")
    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_bulk_history(symbols: tuple[str, ...], period: str = "1y") -> dict[str, pd.DataFrame]:
    """
    Fetches historical OHLCV data for MULTIPLE tickers in a single batched,
    threaded call -- much faster than looping fetch_indian_stock_data() per symbol.
    Use this for your initial scan instead of a per-ticker for-loop.

    Parameters:
        symbols (tuple[str, ...]): Tuple of raw tickers, e.g. ('RELIANCE', 'TCS', 'INFY')
                                    (tuple, not list, so it's hashable for st.cache_data)
        period (str): Lookback period, must be a valid yfinance period

    Returns:
        dict[str, pd.DataFrame]: Maps each ORIGINAL input symbol -> its DataFrame
                                  (empty DataFrame if that symbol failed)
    """
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period '{period}'. Use one of {sorted(VALID_PERIODS)}")

    normalized = [_normalize_symbol(s) for s in symbols]
    result: dict[str, pd.DataFrame] = {}

    def _fetch():
        return yf.download(
            normalized,
            period=period,
            interval="1d",
            group_by="ticker",
            threads=True,
            auto_adjust=False,
            progress=False,
        )

    raw = _with_retry(_fetch)
    if raw is None:
        return {s: pd.DataFrame() for s in symbols}

    for orig, norm in zip(symbols, normalized):
        try:
            df = raw[norm] if len(normalized) > 1 else raw
            df = df.reset_index()
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            result[orig] = df if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Error parsing bulk data for {orig} ({norm}): {e}")
            result[orig] = pd.DataFrame()

    return result
