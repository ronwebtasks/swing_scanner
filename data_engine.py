import yfinance as yf
import pandas as pd

def fetch_indian_stock_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    Fetches daily historical OHLCV data for an Indian stock from Yahoo Finance.
    Automatically handles formatting for the NSE market.
    
    Parameters:
        symbol (str): Stock ticker (e.g., 'RELIANCE', 'TCS', 'INFY')
        period (str): Lookback period ('6m', '1y', '2y')
        
    Returns:
        pd.DataFrame: Structured market data with clean, readable columns.
    """
    # Clean symbol inputs and append the National Stock Exchange suffix (.NS)
    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        ticker_symbol = f"{symbol}.NS"
    else:
        ticker_symbol = symbol

    try:
        ticker = yf.Ticker(ticker_symbol)
        # Fetch daily history
        df = ticker.history(period=period, interval="1d")
        
        if df.empty:
            return pd.DataFrame()
            
        # Reset index to move 'Date' from index into a normal column
        df = df.reset_index()
        
        # Clean up column names for our indicator calculations
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Strip time zone data to make manipulations simpler
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        
        return df
    except Exception as e:
        print(f"Error fetching data for ticker {ticker_symbol}: {e}")
        return pd.DataFrame()
