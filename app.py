import streamlit as st
import plotly.express as px
import pandas as pd

st.title("📊 股票市場即時熱圖")

# 1. 準備模擬數據 (未來可以串接 API 自動更新)
# 這裡我們手動建立一些台股與美股的熱門標的作為範例
data = {
    "股票": ["台積電", "鴻海", "聯發科", "蘋果", "微軟", "輝達", "Google"],
    "產業": ["半導體", "電子代工", "半導體", "科技終端", "軟體服務", "半導體", "軟體服務"],
    "漲跌幅": [2.5, -1.2, 0.8, 1.5, -0.5, 4.2, 1.1],
    "市值權重": [500, 150, 100, 400, 350, 450, 300]
}
df = pd.DataFrame(data)

# 2. 建立熱圖邏輯
fig = px.treemap(
    df, 
    path=[px.Constant("股票市場"), "產業", "股票"], # 層級：市場 -> 產業 -> 個股
    values="市值權重", 
    color="漲跌幅",
    color_continuous_scale='RdYlGn', # 紅(跌)黃(平)綠(漲) 漸層
    color_continuous_midpoint=0     # 以 0% 為顏色中心點
)

# 3. 在網頁上顯示
st.plotly_chart(fig, use_container_width=True)

st.info("💡 提示：點擊熱圖中的產業區塊可以放大觀察。")
