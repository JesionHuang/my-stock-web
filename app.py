import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.title("📈 全球股市即時熱圖")

# 先用少量的代碼測試，確保穩定
tickers = ["2330.TW", "2317.TW", "AAPL", "TSLA", "NVDA"]

@st.cache_data(ttl=600)
def get_real_data(ticker_list):
    results = []
    for t in ticker_list:
        try:
            # 使用 fast_info 獲取數據，這比 info 更穩定
            ticker_obj = yf.Ticker(t)
            # 獲取價格與漲跌
            hist = ticker_obj.history(period="2d")
            if len(hist) >= 2:
                price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change = ((price - prev_close) / prev_close) * 100
                
                results.append({
                    "代碼": t,
                    "價格": round(price, 2),
                    "漲跌幅": round(change, 2),
                    "市值": 100 # 先用固定值測試，確保熱圖能畫出來
                })
        except Exception as e:
            continue # 遇到錯誤先跳過，不要讓整個網頁壞掉
    return pd.DataFrame(results)

with st.spinner('數據加載中...'):
    df_real = get_real_data(tickers)

if not df_real.empty:
    fig = px.treemap(
        df_real,
        path=["代碼"],
        values="市值",
        color="漲跌幅",
        color_continuous_scale='RdYlGn',
        color_continuous_midpoint=0
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("目前無法獲取數據，請確認 GitHub 中的 requirements.txt 是否包含 yfinance")
