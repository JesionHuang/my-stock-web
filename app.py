import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# 0. 頁面基本設定
st.set_page_config(page_title="錢多多投資管理系統", layout="wide")

# 1. 初始化 Google Sheets 連接
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🌐 全球大盤與核心持股監控面板")

# --- 第一部分：熱圖分析 ---

# 定義要追蹤的標的 (代碼, 顯示名稱, 類別)
market_targets = [
    ("VTI", "美股全市場 (VTI)", "美股大盤"), 
    ("DIA", "道瓊工業 (DIA)", "美股大盤"),
    ("QQQ", "納斯達克 (QQQ)", "美股大盤"),
    ("^TWII", "台股加權指數", "台股大盤"),
    ("2330.TW", "台積電", "台股核心"),
    ("2317.TW", "鴻海", "台股核心"),
    ("AAPL", "蘋果", "美股核心"),
    ("NVDA", "輝達", "美股核心"),
    ("TSLA", "特斯拉", "美股核心")
]

@st.cache_data(ttl=300)
def get_market_heatmap_data(targets):
    results = []
    tickers_list = [t[0] for t in targets]
    try:
        data = yf.download(tickers_list, period="2d", group_by='ticker', progress=False)
        for ticker, name, category in targets:
            if ticker in data and not data[ticker].empty:
                tick_data = data[ticker]
                if len(tick_data) >= 2:
                    current_price = tick_data['Close'].iloc[-1]
                    prev_close = tick_data['Close'].iloc[-2]
                    change = ((current_price - prev_close) / prev_close) * 100
                    
                    # 權重邏輯：大盤指數手動加大權重
                    weight = 1000000000000 if "大盤" in category else 50000000000
                    
                    results.append({
                        "名稱": name,
                        "類別": category,
                        "價格": round(current_price, 2),
                        "漲跌幅": round(change, 2),
                        "權重市值": weight
                    })
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
    return pd.DataFrame(results)

# 顯示熱圖
with st.spinner('正在同步全球市場數據...'):
    df_heatmap = get_market_heatmap_data(market_targets)

if not df_heatmap.empty:
    # 建立更簡潔的標籤，節省空間
    df_heatmap["顯示標籤"] = df_heatmap.apply(
        lambda row: f"{row['名稱']}<br><b>{'+' if row['漲跌幅'] > 0 else ''}{row['漲跌幅']}%</b>", 
        axis=1
    )

    fig = px.treemap(
        df_heatmap,
        path=["類別", "顯示標籤"], # 移除 px.Constant("全球市場")，讓方塊更大
        values="權重市值",
        color="漲跌幅",
        color_continuous_scale='RdYlGn', 
        color_continuous_midpoint=0,
        range_color=[-4, 4]
    )
    
    fig.update_traces(
        textinfo="label",
        texttemplate="%{label}",
        textfont=dict(size=22), # 這裡設定大字級
        insidetextfont=dict(size=22)
    )

    # 強制設定圖表高度，解決「字太小」的根本問題
    fig.update_layout(
        height=500, 
        margin=dict(t=10, l=10, r=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("📊 查看即時行情明細"):
        st.dataframe(df_heatmap[["名稱", "價格", "漲跌幅"]].sort_values(by="漲跌幅", ascending=False), use_container_width=True)
else:
    st.warning("暫時無法獲取市場數據，請稍後再試。")

# --- 第二部分：新增交易紀錄表單 ---

st.divider() 
st.header("📝 新增選股與交易紀錄")

with st.form("trade_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        s_id = st.text_input("股票代碼 (例: 2330.TW)")
        s_action = st.selectbox("交易動作", ["觀察中", "加倉", "平倉"])
    with col2:
        s_price = st.number_input("成交價格", min_value=0.0, step=0.1)
        s_date = st.date_input("交易日期", value=datetime.now())
    
    s_note = st.text_area("技術分析理由 (例如：突破季線、量增價揚)")
    submit = st.form_submit_button("確認儲存紀錄")

if submit:
    if s_id:
        try:
            # 讀取並合併數據
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{
                "Date": str(s_date),
                "Stock_ID": s_id,
                "Action": s_action,
                "Price": s_price,
                "Note": s_note
            }])
            updated_df = pd.concat([existing_data, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success(f"✅ {s_id} 紀錄已存入 Google Sheets！")
            st.balloons()
            st.rerun() # 自動重新整理以顯示最新清單
        except Exception as e:
            st.error(f"儲存失敗：{e}")
    else:
        st.error("請輸入股票代碼！")

# --- 第三部分：顯示歷史紀錄 ---

st.divider()
st.header("📜 歷史交易與選股紀錄")

try:
    df_history = conn.read(worksheet="Sheet1", ttl=0)
    if not df_history.empty:
        # 資料預處理
        df_history['Date'] = pd.to_datetime(df_history['Date'])
        df_history = df_history.sort_values(by='Date', ascending=False)
        
        st.dataframe(
            df_history,
            column_config={
                "Date": st.column_config.DateColumn("日期"),
                "Stock_ID": "代碼",
                "Action": "動作",
                "Price": st.column_config.NumberColumn("價格", format="$%.2f"),
                "Note": "分析備註"
            },
            hide_index=True,
            use_container_width=True
        )
        st.caption(f"目前累計交易筆數：{len(df_history)}")
    else:
        st.info("目前尚無歷史紀錄。")
except Exception as e:
    st.error(f"讀取紀錄失敗，請檢查設定：{e}")
