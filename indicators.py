import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_indicators(df):
    # Moving Averages
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI
    df['RSI'] = calculate_rsi(df['Close'])
    
    # NR7 detection
    df['Range'] = df['High'] - df['Low']
    df['NR7'] = df['Range'] == df['Range'].rolling(window=7).min()
    
    # Momentum Score (0-100) - Simplified logic based on 12-period ROC and RSI
    roc = ((df['Close'] - df['Close'].shift(12)) / df['Close'].shift(12)) * 100
    df['Momentum_Score'] = (df['RSI'] * 0.6 + (roc + 50) * 0.4).clip(0, 100)
    
    # VCP Pattern (Simplified: Volatility Contraction over last 20 days)
    df['Vol_20'] = df['Range'].rolling(window=20).std()
    df['Vol_10'] = df['Range'].rolling(window=10).std()
    df['VCP'] = df['Vol_10'] < df['Vol_20'] * 0.8
    
    # Pocket Pivot (Simplified: Volume > max volume of last 10 down days)
    down_days_vol = df['Volume'].where(df['Close'] < df['Close'].shift(1), 0)
    df['Max_Down_Vol_10'] = down_days_vol.rolling(window=10).max()
    df['Pocket_Pivot'] = (df['Close'] > df['Close'].shift(1)) & (df['Volume'] > df['Max_Down_Vol_10'])
    
    return df

def get_ai_grade(row):
    # Grade A: Strong sector + strong stock + high momentum
    # Grade B: Sector strong, stock moderate
    # Grade C: Weak sector
    
    score = 0
    if row['Close'] > row['SMA50']: score += 1
    if row['Close'] > row['SMA200']: score += 1
    if row['RSI'] > 60: score += 1
    if row['Momentum_Score'] > 70: score += 1
    if row['Pocket_Pivot']: score += 1
    
    if score >= 4:
        return 'Grade A'
    elif score >= 2:
        return 'Grade B'
    else:
        return 'Grade C'
