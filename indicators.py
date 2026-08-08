import pandas as pd
import pandas_ta as ta

def calculate_all_indicators(df, ticker_symbol):
    try:
        if df.empty or len(df) < 200:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker_symbol, axis=1, level=1)

        df['MA_200'] = ta.sma(df['Close'], length=200)
        df['EMA_20'] = ta.ema(df['Close'], length=20)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        
        macd_df = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            df['MACD'] = macd_df['MACD_12_26_9']
            df['MACD_signal'] = macd_df['MACDs_12_26_9']
        else:
            return None

        adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx_df is not None and not adx_df.empty:
            df['ADX'] = adx_df['ADX_14']
        else:
            return None

        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['Resistance_20'] = df['High'].rolling(20).max()
        df['Vol_SMA20'] = ta.sma(df['Volume'], length=20)

        return df

    except Exception as e:
        return None
