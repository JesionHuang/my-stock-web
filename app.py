import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# 顯示版本資訊，方便我們除錯
# st.write(f"目前運行的 Streamlit 版本: {st.__version__}")

st.title("📈 我的投資管理系統")

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
from streamlit_gsheets import GSheetsConnection

# 建立 Google Sheets 連結
conn = st.connection("gsheets", type=GSheetsConnection)

st.divider() 
st.header("📝 新增選股與交易紀錄")

# 使用正確的語法建立表單
with st.form("trade_form"):
    col1, col2 = st.columns(2)
    with col1:
        s_id = st.text_input("股票代碼 (如 2330.TW)")
        s_action = st.selectbox("動作", ["觀察中", "加倉", "平倉"])
    with col2:
        s_price = st.number_input("成交價格", value=0.0)
        s_date = st.date_input("日期")
    
    s_note = st.text_area("技術分析理由 (例如：突破季線、量增價揚)")
    
    # 修正後的正確指令
    submit = st.form_submit_button("儲存紀錄")

from streamlit_gsheets import GSheetsConnection

# 建立連結
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 這裡是你之前的表單代碼 ---

if submit:
    if s_id:
        # 1. 先讀取現有的資料
        existing_data = conn.read(worksheet="工作表1", usecols=[0,1,2,3,4], ttl=0)
        
        # 2. 準備新的一行資料
        new_row = pd.DataFrame([{
            "Date": str(s_date),
            "Stock_ID": s_id,
            "Action": s_action,
            "Price": s_price,
            "Note": s_note
        }])
        
        # 3. 合併資料並寫回 Google Sheets
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="工作表1", data=updated_df)
        
        st.success(f"✅ 資料已成功存入 Google Sheets！")
        st.balloons()
    else:
        st.error("請輸入股票代碼！")
