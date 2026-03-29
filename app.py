import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# 0. 頁面基本設定
st.set_page_config(page_title="錢多多投資管理系統", layout="wide")

# 1. 初始化 Google Sheets 連接
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🌐 全球大盤與核心持股監控面板")

# --- 第一部分：熱圖分析 ---
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
                    weight = 1000000000000 if "大盤" in category else 50000000000
                    results.append({
                        "名稱": name, "類別": category, "價格": round(current_price, 2),
                        "漲跌幅": round(change, 2), "權重市值": weight
                    })
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
    return pd.DataFrame(results)

with st.spinner('正在同步全球市場數據...'):
    df_heatmap = get_market_heatmap_data(market_targets)

if not df_heatmap.empty:
    df_heatmap["顯示標籤"] = df_heatmap.apply(
        lambda row: f"{row['名稱']}<br><b>{'+' if row['漲跌幅'] > 0 else ''}{row['漲跌幅']}%</b>", axis=1
    )
    fig = px.treemap(df_heatmap, path=["類別", "顯示標籤"], values="權重市值",
                     color="漲跌幅", color_continuous_scale='RdYlGn', 
                     color_continuous_midpoint=0, range_color=[-4, 4])
    fig.update_traces(textinfo="label", texttemplate="%{label}", textfont=dict(size=22))
    fig.update_layout(height=500, margin=dict(t=10, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("暫時無法獲取市場數據。")

# --- 第二部分：當前持倉損益分析 (紅綠配色 + 零線折線趨勢版) ---
st.divider()
st.header("💰 當前持倉損益分析")

try:
    df_calc = conn.read(worksheet="Sheet1", ttl=0)
    
    if df_calc is not None and not df_calc.empty:
        target_col = 'My_Price' if 'My_Price' in df_calc.columns else 'Price'
        df_calc['Calc_Price'] = pd.to_numeric(df_calc[target_col], errors='coerce').fillna(0)
        df_calc['Quantity'] = pd.to_numeric(df_calc['Quantity'], errors='coerce').fillna(0)
        df_calc['Stock_ID'] = df_calc['Stock_ID'].astype(str).str.upper()

        summary = []
        for stock_id in df_calc['Stock_ID'].unique():
            if not stock_id or stock_id == "NAN": continue
            df_stock = df_calc[df_calc['Stock_ID'] == stock_id]
            buy_q = df_stock[df_stock['Action'] == "加倉"]['Quantity'].sum()
            sell_q = df_stock[df_stock['Action'] == "平倉"]['Quantity'].sum()
            current_q = buy_q - sell_q
            
            if current_q > 0:
                buys = df_stock[df_stock['Action'] == "加倉"]
                avg_cost = (buys['Calc_Price'] * buys['Quantity']).sum() / buys['Quantity'].sum()
                
                try:
                    tk = yf.Ticker(stock_id)
                    hist_trend = tk.history(period="1mo")['Close']
                    current_price = hist_trend.iloc[-1]
                    
                    # --- 核心邏輯：將折線圖「零軸化」 ---
                    def get_trend_normalized(series, days):
                        data = series.iloc[-days:]
                        avg = data.mean()
                        diff = data - avg  # 減去平均值，讓數據圍繞 0 震盪
                        max_abs = diff.abs().max() if diff.abs().max() != 0 else 1
                        return (diff / max_abs).tolist() # 縮放到 -1 ~ 1 區間

                    t5 = get_trend_normalized(hist_trend, 5)
                    t10 = get_trend_normalized(hist_trend, 10)
                    t20 = get_trend_normalized(hist_trend, 20)
                except:
                    current_price = avg_cost
                    t5 = t10 = t20 = []
                
                roi_val = ((current_price - avg_cost) / avg_cost)
                summary.append({
                    "股票代碼": stock_id, 
                    "持股數量": int(current_q),
                    "平均成本": round(avg_cost, 2), 
                    "目前市價": round(current_price, 2),
                    "總損益": round((current_price - avg_cost) * current_q, 2),
                    "投報率_數值": roi_val,
                    "5日趨勢": t5, "10日趨勢": t10, "20日趨勢": t20
                })
        
        if summary:
            df_final = pd.DataFrame(summary)

            # 定義紅漲綠跌顏色
            def color_pnl_style(val):
                color = 'red' if val > 0 else 'green' if val < 0 else '#cccccc'
                return f'color: {color}; font-weight: bold'

            styled_summary = df_final.style.map(color_pnl_style, subset=['總損益', '投報率_數值'])
            
            st.dataframe(
                styled_summary,
                column_config={
                    "股票代碼": "代碼",
                    "平均成本": st.column_config.NumberColumn("成本", format="$%.2f"),
                    "目前市價": st.column_config.NumberColumn("市價", format="$%.2f"),
                    "總損益": st.column_config.NumberColumn("總損益", format="$%.2f"),
                    "投報率_數值": st.column_config.NumberColumn("投報率", format="%.2f%%"),
                    # --- 使用 LineChartColumn 並固定 y 軸對稱，產生零線視覺 ---
                    "5日趨勢": st.column_config.LineChartColumn("5D 走勢", y_min=-1, y_max=1),
                    "10日趨勢": st.column_config.LineChartColumn("10D 走勢", y_min=-1, y_max=1),
                    "20日趨勢": st.column_config.LineChartColumn("20D 走勢", y_min=-1, y_max=1),
                },
                column_order=("股票代碼", "持股數量", "平均成本", "目前市價", "總損益", "投報率_數值", "5日趨勢", "10日趨勢", "20日趨勢"),
                use_container_width=True, 
                hide_index=True
            )
            st.caption("💡 💡 註：趨勢圖中位線為該期間平均價。曲線在前半格代表低於平均，後半格代表高於平均。")
        else:
            st.info("目前無實際持倉。")

# --- 第三部分：新增交易紀錄表單 (含當日行情自動抓取) ---
st.divider()
st.header("📝 新增選股與交易紀錄 (含當日行情)")

with st.form("transaction_form_v5", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        t_date = st.date_input("紀錄日期", date.today())
        t_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW")
    with col2:
        t_type = st.selectbox("動作類型", ["觀察中", "加倉", "平倉"])
        t_price = st.number_input("我的成交/觀察價", min_value=0.0, step=0.1)
    with col3:
        t_qty = st.number_input("數量", min_value=0, step=1, value=0 if t_type == "觀察中" else 1)
        t_note = st.text_input("分析備註")

    submit_button = st.form_submit_button("確認儲存紀錄並抓取行情")

if submit_button:
    if t_stock:
        try:
            # A. 自動抓取當日行情數據
            with st.spinner(f"正在抓取 {t_stock} 當日行情..."):
                tk = yf.Ticker(t_stock.upper().strip())
                # 抓取最近 1 天的數據
                hist = tk.history(period="1d")
                if not hist.empty:
                    day_high = round(hist['High'].iloc[-1], 2)
                    day_low = round(hist['Low'].iloc[-1], 2)
                    day_close = round(hist['Close'].iloc[-1], 2)
                    # 計算漲跌幅 (需抓取前一日收盤)
                    prev_hist = tk.history(period="2d")
                    if len(prev_hist) >= 2:
                        prev_close = prev_hist['Close'].iloc[-2]
                        day_change = f"{round(((day_close - prev_close) / prev_close) * 100, 2)}%"
                    else:
                        day_change = "N/A"
                else:
                    day_high, day_low, day_close, day_change = 0, 0, 0, "N/A"

            # B. 讀取與合併資料
            try:
                existing_data = conn.read(worksheet="Sheet1", ttl=0)
            except:
                existing_data = pd.DataFrame()
            
            new_record = pd.DataFrame([{
                "Date": str(t_date),
                "Stock_ID": t_stock.upper().strip(),
                "Action": t_type,
                "My_Price": float(t_price),
                "Quantity": int(t_qty),
                "Day_High": day_high,
                "Day_Low": day_low,
                "Day_Close": day_close,
                "Day_Change": day_change,
                "Note": str(t_note)
            }])
            
            updated_df = pd.concat([existing_data, new_record], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            
            st.success(f"✅ 成功儲存！已自動記錄 {t_stock} 當日行情：高 {day_high} / 低 {day_low}")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"儲存或抓取行情失敗：{e}")
    else:
        st.warning("請輸入股票代碼！")

# --- 第四部分：歷史紀錄表格 (修復顏色定義與百分比問題) ---
st.divider()
st.header("📜 歷史紀錄查詢")

try:
    df_history = conn.read(worksheet="Sheet1", ttl=0)
    if df_history is not None and not df_history.empty:
        # 1. 篩選器
        all_actions = df_history['Action'].unique().tolist()
        selected_actions = st.multiselect("🔍 篩選動作類型", all_actions, default=all_actions)
        
        # 2. 執行篩選
        filtered_df = df_history[df_history['Action'].isin(selected_actions)].copy()
        filtered_df = filtered_df.sort_values(by='Date', ascending=False)
        
        # 3. 數據預處理：確保漲跌幅是數值型態 (處理 -0.0195 這種小數)
        if 'Day_Change' in filtered_df.columns:
            # 移除字串中的 % 並轉為數值，如果是小數則直接轉換
            filtered_df['Display_Change'] = (
                filtered_df['Day_Change']
                .astype(str)
                .str.replace('%', '', regex=False)
                .replace('N/A', '0')
            )
            filtered_df['Display_Change'] = pd.to_numeric(filtered_df['Display_Change'], errors='coerce').fillna(0)
            
            # 關鍵判斷：如果數值大於 1 或小於 -1，通常代表它是百分比整數(1.5)而非小數(0.015)
            # 為了配合 format="%.2f%%"，我們統一將其轉為小數格式
            if filtered_df['Display_Change'].abs().max() > 1:
                filtered_df['Display_Change'] = filtered_df['Display_Change'] / 100

        # 4. 定義顏色邏輯 (紅漲綠跌)
        def color_style(val):
            color = 'red' if val > 0 else 'green' if val < 0 else '#cccccc'
            return f'color: {color}; font-weight: bold'

        # 5. 建立 styled_history 物件 (解決 undefined 錯誤)
        styled_history = filtered_df.style.map(color_style, subset=['Display_Change'])
        
        # 6. 顯示表格
        st.dataframe(
            styled_history,
            column_config={
                "Date": "日期",
                "Stock_ID": "代碼",
                "Action": "動作",
                "My_Price": st.column_config.NumberColumn("成交/觀察價", format="$%.2f"),
                "Day_High": "當日最高",
                "Day_Low": "當日最低",
                "Day_Close": "當日收盤",
                "Display_Change": st.column_config.NumberColumn(
                    "當日漲跌", 
                    help="當天收盤相對於前一天的漲跌幅",
                    format="%.2f%%" # 將 0.0195 自動顯示為 1.95%
                ),
                "Note": "分析備註"
            },
            column_order=("Date", "Stock_ID", "Action", "My_Price", "Day_High", "Day_Low", "Day_Close", "Display_Change", "Note"),
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("尚無紀錄。")
except Exception as e:
    st.error(f"讀取表格時發生錯誤：{e}")
