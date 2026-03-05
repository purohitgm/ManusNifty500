import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from indicators import calculate_indicators, get_ai_grade
from datetime import datetime, timedelta
import time

# Page Config
st.set_page_config(layout="wide", page_title="Nifty Sectoral Analytics Dashboard")

# Constants
INDEX_TICKERS = {
    "Nifty 50": "^NSEI",
    "Nifty 100": "^CNX100",
    "Nifty 200": "^CNX200",
    "Nifty Bank": "^NSEBANK",
    "Nifty IT": "^CNXIT",
    "Nifty Auto": "^CNXAUTO",
    "Nifty FMCG": "^CNXFMCG",
    "Nifty Metal": "^CNXMETAL",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty Reality": "^CNXREALTY",
    "Nifty Energy": "^CNXENERGY",
    "Nifty Infra": "^CNXINFRA"
}

# Mapping Sectoral Indices to some key stocks (Simplified for demonstration)
SECTOR_STOCKS = {
    "Nifty Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "Nifty IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
    "Nifty Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS"],
    "Nifty FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "VBL.NS"],
    "Nifty Metal": ["TATASTEEL.NS", "JINDALSTEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "VEDL.NS"],
    "Nifty Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
    "Nifty Reality": ["DLF.NS", "LODHA.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS", "PRESTIGE.NS"],
    "Nifty Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS"],
    "Nifty Infra": ["LT.NS", "ADANIPORTS.NS", "GRASIM.NS", "ULTRACEMCO.NS", "BHARTIARTL.NS"]
}

@st.cache_data(ttl=60)
def fetch_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df.empty:
            return None
        return df
    except Exception as e:
        return None

def main():
    st.sidebar.title("NSE Analytics Settings")
    auto_refresh = st.sidebar.checkbox("Auto Refresh (60s)", value=True)
    
    if auto_refresh:
        # Simple auto-refresh mechanism
        time.sleep(1) # Slight delay to avoid rapid looping
        # st.empty()
    
    st.title("📊 Indian Stock Market: Nifty Sectoral Analytics")
    st.markdown(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. LIVE INDEX SUMMARY
    st.subheader("Indices Performance")
    index_cols = st.columns(len(INDEX_TICKERS))
    
    index_performance = []
    for i, (name, ticker) in enumerate(INDEX_TICKERS.items()):
        df = fetch_data(ticker, period="5d")
        if df is not None and len(df) >= 2:
            last_close = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            pct_change = ((last_close - prev_close) / prev_close) * 100
            
            # Display metrics
            if i < len(index_cols):
                index_cols[i].metric(name, f"{last_close:,.2f}", f"{pct_change:+.2f}%")
            
            index_performance.append({
                "Sector": name,
                "Change%": pct_change,
                "Price": last_close
            })
    
    # 2. SECTOR HEATMAP
    st.subheader("Sectoral Momentum Ranking")
    if index_performance:
        perf_df = pd.DataFrame(index_performance).sort_values(by="Change%", ascending=False)
        fig = px.bar(perf_df, x="Sector", y="Change%", color="Change%",
                     color_continuous_scale='RdYlGn', title="Today's Sectoral Performance")
        st.plotly_chart(fig, use_container_width=True)

    # 3. STOCK LEVEL ANALYSIS
    selected_sector = st.selectbox("Drill-down: Select Sector to Analyze Stocks", list(SECTOR_STOCKS.keys()))
    
    if selected_sector:
        tickers = SECTOR_STOCKS[selected_sector]
        stock_data = []
        
        with st.spinner(f"Analyzing stocks in {selected_sector}..."):
            for ticker in tickers:
                df = fetch_data(ticker, period="1y")
                if df is not None:
                    df = calculate_indicators(df)
                    last_row = df.iloc[-1]
                    prev_row = df.iloc[-2]
                    
                    # Calculate Market Breadth logic (stocks above 20 EMA)
                    above_20ema = last_row['Close'] > last_row['EMA20']
                    
                    stock_data.append({
                        "Ticker": ticker,
                        "Price": last_row['Close'],
                        "Change%": ((last_row['Close'] - prev_row['Close']) / prev_row['Close']) * 100,
                        "RSI(14)": last_row['RSI'],
                        "Momentum": last_row['Momentum_Score'],
                        "NR7": "Yes" if last_row['NR7'] else "No",
                        "VCP": "Detected" if last_row['VCP'] else "No",
                        "Pocket Pivot": "Yes" if last_row['Pocket_Pivot'] else "No",
                        "Above 200DMA": "Yes" if last_row['Close'] > last_row['SMA200'] else "No",
                        "Grade": get_ai_grade(last_row)
                    })
        
        if stock_data:
            df_stocks = pd.DataFrame(stock_data)
            
            # Visuals: Treemap for Industry/Sector Strength
            st.subheader(f"Heatmap: {selected_sector} Constituents")
            fig_tree = px.treemap(df_stocks, path=['Ticker'], values='Price', color='Change%',
                                  color_continuous_scale='RdYlGn', hover_data=['RSI(14)', 'Grade'])
            st.plotly_chart(fig_tree, use_container_width=True)
            
            # Filters
            st.subheader("Interactive Filters")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                rsi_range = st.slider("RSI Range", 0, 100, (30, 70))
            with f_col2:
                min_momentum = st.number_input("Min Momentum Score", 0, 100, 0)
            
            filtered_df = df_stocks[
                (df_stocks['RSI(14)'] >= rsi_range[0]) & 
                (df_stocks['RSI(14)'] <= rsi_range[1]) &
                (df_stocks['Momentum'] >= min_momentum)
            ]
            
            st.dataframe(filtered_df.style.applymap(
                lambda x: 'background-color: #90ee90' if x == 'Grade A' else ('background-color: #ffcccb' if x == 'Grade C' else ''),
                subset=['Grade']
            ), use_container_width=True)

            # Advance-Decline Ratio
            advances = len(df_stocks[df_stocks['Change%'] > 0])
            declines = len(df_stocks[df_stocks['Change%'] < 0])
            st.info(f"Market Breadth ({selected_sector}): Advances: {advances} | Declines: {declines} | A/D Ratio: {advances/max(declines,1):.2f}")

    if auto_refresh:
        time.sleep(60)
        st.rerun()

if __name__ == "__main__":
    main()
