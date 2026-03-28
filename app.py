import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.title("🌐 全球大盤與核心持股熱圖")

# 1. 定義要追蹤的標的 (包含指數代表與個股)
#格式：(代碼, 顯示名稱, 類別)
market_targets = [
    # 美股大盤代表 (使用 ETF)
    ("VTI", "美股全市場 (VTI)", "美股大盤"), 
    ("DIA", "道瓊工業 (DIA)", "美股大盤"),
    ("QQQ", "納斯達克 (QQQ)", "美股大盤"),
    
    # 台股大盤與核心權值
    ("^TWII", "台股加權指數", "台股大盤"),
    ("2330.TW", "台積電", "台股核心"),
    ("2317.TW", "鴻海", "台股核心"),
    
    # 自選美股核心
    ("AAPL", "蘋果", "美股核心"),
    ("NVDA", "輝達", "美股核心"),
    ("TSLA", "特斯拉", "美股核心")
]

@st.cache_data(ttl=300) # 快取 5 分鐘
def get_market_heatmap_data(targets):
    results = []
    # 提取所有代碼用於批量抓取，效率更高
    tickers_list = [t[0] for t in targets]
    
    try:
        # 批量抓取當天數據
        data = yf.download(tickers_list, period="2d", group_by='ticker', progress=False)
        
        for ticker, name, category in targets:
            if ticker in data and not data[ticker].empty:
                tick_data = data[ticker]
                if len(tick_data) >= 2:
                    # 計算漲跌幅
                    current_price = tick_data['Close'].iloc[-1]
                    prev_close = tick_data['Close'].iloc[-2]
                    change = ((current_price - prev_close) / prev_close) * 100
                    
                    # 獲取市值 (個股有市值，指數用固定值代表權重)
                    # 指數(ETF)通常yf抓不到Cap，我們設一個較大值讓它在熱圖中顯眼
                    t_obj = yf.Ticker(ticker)
                    
                    # 謹慎處理市值抓取失敗的情況
                    try:
                        market_cap = t_obj.info.get('marketCap', 50000000000) # 預設 500億
                    except:
                        market_cap = 50000000000 # info 失敗時的備案

                    # 如果是指數，手動加大權重讓它突出
                    if "大盤" in category:
                        market_cap = 1000000000000 # 設為 1兆，讓大盤區塊最大

                    results.append({
                        "名稱": name,
                        "類別": category,
                        "價格": round(current_price, 2),
                        "漲跌幅": round(change, 2),
                        "權重市值": market_cap
                    })
    except Exception as e:
        st.error(f"數據抓取發生嚴重錯誤: {e}")
        
    return pd.DataFrame(results)

# 執行抓取
with st.spinner('正在同步全球大盤數據...'):
    df_heatmap = get_market_heatmap_data(market_targets)

if not df_heatmap.empty:
    # 2. 繪製熱圖 (層級：類別 -> 名稱)
    fig = px.treemap(
        df_heatmap,
        path=[px.Constant("全球市場"), "類別", "名稱"],
        values="權重市值",
        color="漲跌幅",
        hover_data=["價格"],
        color_continuous_scale='RdYlGn', 
        color_continuous_midpoint=0,
        range_color=[-4, 4] # 鎖定顏色範圍 -4% 到 +4%，視覺更直觀
    )
    
    # 美化圖表設定
    if not df_heatmap.empty:
    # --- 新增：建立顯示標籤 ---
    # 我們將名稱與漲跌幅結合，加上 % 符號
    df_heatmap["顯示標籤"] = df_heatmap.apply(
        lambda row: f"{row['名稱']}<br>{'+' if row['漲跌幅'] > 0 else ''}{row['漲跌幅']}%", 
        axis=1
    )

    # 2. 繪製熱圖
    fig = px.treemap(
        df_heatmap,
        # 注意：這裡的 path 最後一層要改成我們剛建立的 "顯示標籤"
        path=[px.Constant("全球市場"), "類別", "顯示標籤"],
        values="權重市值",
        color="漲跌幅",
        hover_data=["價格"],
        color_continuous_scale='RdYlGn', 
        color_continuous_midpoint=0,
        range_color=[-4, 4]
    )
    
    # --- 新增：調整文字顯示格式 ---
    fig.update_traces(
        textinfo="label", # 只顯示我們自定義的標籤
        texttemplate="%{label}", # 確保顯示完整文字
        hovertemplate='<b>%{label}</b><br>價格: %{customdata[0]}', # 滑鼠指過去的顯示
        textfont=dict(size=15) # 調整字體大小，讓數字更清楚
    )

    fig.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    
    # 顯示數據明細
    with st.expander("查看數據明細"):
        st.dataframe(df_heatmap[["名稱", "價格", "漲跌幅"]].sort_values(by="漲跌幅", ascending=False))
else:
    st.error("無法獲取市場數據。")

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
        existing_data = conn.read(worksheet="Sheet1", usecols=[0,1,2,3,4], ttl=0)
        
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
        conn.update(worksheet="Sheet1", data=updated_df)
        
        st.success(f"✅ 資料已成功存入 Google Sheets！")
        st.balloons()
    else:
        st.error("請輸入股票代碼！")
st.divider()
st.header("📜 歷史交易與選股紀錄")

# 1. 從 Google Sheets 讀取最新數據
# ttl=0 代表不使用快取，確保每次都能看到最新存入的資料
try:
    df_history = conn.read(worksheet="Sheet1", ttl=0)
    
    if not df_history.empty:
        # 2. 資料預處理：按日期排序（由新到舊）
        df_history['Date'] = pd.to_datetime(df_history['Date'])
        df_history = df_history.sort_values(by='Date', ascending=False)
        
        # 3. 美化顯示表格
        # 使用 st.dataframe 可以讓用戶自行縮放、排序或搜尋
        st.dataframe(
            df_history,
            column_config={
                "Date": st.column_config.DateColumn("交易日期"),
                "Stock_ID": "股票代碼",
                "Action": "動作",
                "Price": st.column_config.NumberColumn("成交價格", format="$%.2f"),
                "Note": "技術分析備註"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # 4. 簡單的數據統計（加分功能）
        total_trades = len(df_history)
        st.caption(f"目前總計共有 {total_trades} 筆紀錄")
        
    else:
        st.info("目前尚無歷史紀錄，請先在上方表單新增第一筆資料。")

except Exception as e:
    st.error(f"讀取紀錄失敗，請檢查 Google Sheets 連結設定。錯誤訊息: {e}")
