import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.title("📈 全球股市即時熱圖")

# 1. 定義你想追蹤的股票清單 (台股需加 .TW，美股直接輸入代碼)
tickers = ["2330.TW", "2317.TW", "2454.TW", "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]

@st.cache_data(ttl=600) # 快取數據 10 分鐘，避免頻繁請求被 Yahoo 封鎖
def get_real_data(ticker_list):
    results = []
    for t in ticker_list:
        try:
            stock = yf.Ticker(t)
            info = stock.info
            # 取得即時價格與昨日收盤價
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev_close = info.get("regularMarketPreviousClose")
            
            if price and prev_close:
                change = ((price - prev_close) / prev_close) * 100
                results.append({
                    "代碼": t,
                    "名稱": info.get("shortName", t),
                    "產業": info.get("sector", "其他"),
                    "價格": price,
                    "漲跌幅": round(change, 2),
                    "市值": info.get("marketCap", 0)
                })
        except Exception as e:
            st.error(f"抓取 {t} 失敗: {e}")
    return pd.DataFrame(results)

# 執行抓取
with st.spinner('正在從 Yahoo Finance 抓取最新數據...'):
    df_real = get_real_data(tickers)

if not df_real.empty:
    # 2. 繪製真實熱圖
    fig = px.treemap(
        df_real,
        path=[px.Constant("我的觀察清單"), "產業", "名稱"],
        values="市值",
        color="漲跌幅",
        hover_data=["價格"],
        color_continuous_scale='RdYlGn', 
        color_continuous_midpoint=0
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 顯示數據表格
    st.dataframe(df_real[["名稱", "價格", "漲跌幅", "產業"]])
else:
    st.warning("目前無法獲取數據，請檢查網路或代碼是否正確。")
