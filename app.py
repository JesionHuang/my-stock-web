import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# ==========================================
# 0. 頁面基本設定與快取函數
# ==========================================
st.set_page_config(page_title="錢多多投資管理系統", layout="wide")

# 初始化 Google Sheets 連接
conn = st.connection("gsheets", type=GSheetsConnection)

# 定義快取讀取函數 (ttl=60秒)，防止 Google Sheets API 流量超限 (429 Error)
@st.cache_data(ttl=60)
def fetch_data(worksheet_name):
    try:
        return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"數據抓取失敗，請稍後再試: {e}")
        return pd.DataFrame()

st.title("🌐 全球大盤與核心持股監控面板")

# ==========================================
# 1. 第一部分：全球市場熱圖
# ==========================================
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
    except: pass
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
    fig.update_traces(textinfo="label", texttemplate="%{label}", textfont=dict(size=18))
    fig.update_layout(height=450, margin=dict(t=10, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 2. 第二部分：當前持倉損益分析 (直接覆蓋版)
# ==========================================
st.divider()
st.header("💰 當前持倉損益分析")

# 持倉管理工具箱 (完全覆蓋模式)
with st.expander("🛠️ 持倉管理工具 (手動校正券商最終數值)"):
    st.info("💡 此功能會清除該股票舊紀錄，並以你輸入的「最終數量與成本」作為唯一基準。")
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        m_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW", key="m_stock_input").upper().strip()
    with col_m2:
        m_qty = st.number_input("最終持有總數量", min_value=0, step=1)
    with col_m3:
        m_cost = st.number_input("最終平均成本價", min_value=0.0, step=0.1)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 執行直接覆蓋 (同步券商數值)", use_container_width=True):
            if m_stock:
                try:
                    df_all = conn.read(worksheet="Sheet1", ttl=0)
                    df_filtered = df_all[df_all['Stock_ID'].astype(str).str.upper() != m_stock]
                    new_final_rec = pd.DataFrame([{
                        "Date": str(date.today()), "Stock_ID": m_stock, "Action": "加倉",
                        "My_Price": float(m_cost), "Quantity": int(m_qty), "Note": "🔄 手動直接覆蓋校正"
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df_filtered, new_final_rec], ignore_index=True))
                    st.cache_data.clear() 
                    st.success(f"✅ {m_stock} 已更新為最終狀態！"); st.rerun()
                except Exception as e: st.error(f"覆蓋失敗: {e}")
    with c2:
        if st.button("🔥 一鍵徹底清空紀錄", use_container_width=True, type="primary"):
            if m_stock:
                try:
                    df_all = conn.read(worksheet="Sheet1", ttl=0)
                    df_filtered = df_all[df_all['Stock_ID'].astype(str).str.upper() != m_stock]
                    conn.update(worksheet="Sheet1", data=df_filtered)
                    st.cache_data.clear()
                    st.success(f"✅ {m_stock} 紀錄已清除。"); st.rerun()
                except Exception as e: st.error(f"清空失敗: {e}")

# 顯示持倉表格
try:
    df_calc = fetch_data("Sheet1")
    if not df_calc.empty:
        df_calc['P'] = pd.to_numeric(df_calc['My_Price'], errors='coerce').fillna(0)
        df_calc['Q'] = pd.to_numeric(df_calc['Quantity'], errors='coerce').fillna(0)
        df_calc['Stock_ID'] = df_calc['Stock_ID'].astype(str).str.upper()

        summary = []
        for stock_id in df_calc['Stock_ID'].unique():
            if not stock_id or stock_id == "NAN": continue
            df_s = df_calc[df_calc['Stock_ID'] == stock_id]
            curr_q = df_s[df_s['Action'] == "加倉"]['Q'].sum() - df_s[df_s['Action'] == "平倉"]['Q'].sum()
            
            if curr_q > 0:
                buys = df_s[df_s['Action'] == "加倉"]
                avg_c = (buys['P'] * buys['Q']).sum() / buys['Q'].sum()
                try:
                    tk = yf.Ticker(stock_id); h = tk.history(period="1mo")['Close']
                    curr_p = h.iloc[-1]
                    def norm(s, d):
                        dt = s.iloc[-d:]; avg = dt.mean(); diff = dt - avg
                        mx = diff.abs().max() if diff.abs().max() != 0 else 1
                        return (diff / mx).tolist()
                    t5, t10, t20 = norm(h, 5), norm(h, 10), norm(h, 20)
                except: curr_p = avg_c; t5 = t10 = t20 = []
                
                # 計算投報率 (小數格式，交給 column_config 轉百分比)
                roi = (curr_p - avg_c) / avg_c if avg_c != 0 else 0
                
                summary.append({
                    "股票代碼": stock_id, "持股數量": int(curr_q), "平均成本": round(avg_c, 2),
                    "目前市價": round(curr_p, 2), "總損益": round((curr_p - avg_c) * curr_q, 2),
                    "投報率": roi, "5D趨勢": t5, "10D趨勢": t10, "20D趨勢": t20
                })
# ==========================================
# 2. 第二部分：當前持倉損益分析 (修正圖表顯示)
# ==========================================
# ... (前面的計算與 summary.append 維持不變) ...

        if summary:
            df_final = pd.DataFrame(summary)
            
            # 定義紅漲綠跌
            def color_pnl(val): 
                color = 'red' if val > 0 else 'green' if val < 0 else '#cccccc'
                return f'color: {color}; font-weight: bold'
            
            # --- 核心修改：在顯示前先將小數轉為百分比數值 ---
            # 假設原本是 0.0239 (代表 2.39%)，我們把它乘以 100 變成 2.39
            if not df_final.empty and '投報率' in df_final.columns:
                df_final['Display_ROI'] = df_final['投報率'] * 100
            else:
                df_final['Display_ROI'] = 0

            st.dataframe(
                df_final.style.map(color_pnl, subset=['總損益', '投報率']), # 顏色判斷用原始小數
                column_config={
                    "股票代碼": "代碼",
                    "平均成本": st.column_config.NumberColumn("成本", format="$%.2f"),
                    "目前市價": st.column_config.NumberColumn("市價", format="$%.2f"),
                    "總損益": st.column_config.NumberColumn("總損益", format="$%.2f"),
                    
                    # --- 核心修改：使用處理後的百分比數值進行顯示 ---
                    "Display_ROI": st.column_config.NumberColumn(
                        "投報率", 
                        format="%.2f%%", # 這裡會自動把 2.39 顯示為 2.39%
                        help="原始計算結果已乘以 100 顯示為百分比"
                    ),
                    
                    "5D趨勢": st.column_config.LineChartColumn("5D", y_min=-1, y_max=1),
                    "10D趨勢": st.column_config.LineChartColumn("10D", y_min=-1, y_max=1),
                    "20D趨勢": st.column_config.LineChartColumn("20D", y_min=-1, y_max=1),
                },
                # 調整顯示順序，將 Display_ROI 放在原本投報率的位置，並隱藏原本的投報率
                column_order=("股票代碼", "持股數量", "平均成本", "目前市價", "總損益", "Display_ROI", "5D趨勢", "10D趨勢", "20D趨勢"),
                use_container_width=True, 
                hide_index=True
            )
except Exception as e: st.error(f"持倉處理錯誤: {e}")

# ==========================================
# 3. 第三部分：新增交易紀錄表單 (自動累加成本與數量)
# ==========================================
st.divider()
st.header("📝 新增選股與交易紀錄")

with st.form("transaction_form_v6", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        t_date = st.date_input("日期", date.today())
        t_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW").upper().strip()
    with c2:
        t_type = st.selectbox("動作類型", ["觀察中", "加倉", "平倉"])
        t_price = st.number_input("本次成交/觀察價", min_value=0.0, step=0.1)
    with c3:
        t_qty = st.number_input("本次數量", min_value=0, step=1)
        t_note = st.text_input("分析備註")
    submit = st.form_submit_button("確認儲存並自動更新持倉")

if submit and t_stock:
    try:
        # 1. 抓取當日行情 (保持原有功能)
        with st.spinner("抓取行情中..."):
            tk = yf.Ticker(t_stock); h = tk.history(period="2d")
            if not h.empty:
                dh, dl, dc = round(h['High'].iloc[-1], 2), round(h['Low'].iloc[-1], 2), round(h['Close'].iloc[-1], 2)
                chg = f"{round(((dc - h['Close'].iloc[-2]) / h['Close'].iloc[-2]) * 100, 2)}%" if len(h) >= 2 else "N/A"
            else: dh = dl = dc = 0; chg = "N/A"
        
        # 2. 讀取現有資料
        df_all = conn.read(worksheet="Sheet1", ttl=0)
        
        # 3. 核心累加邏輯：如果是「加倉」或「平倉」，我們要計算新的總量與平均成本
        if t_type in ["加倉", "平倉"]:
            # 找出該股票現有的紀錄
            df_s = df_all[df_all['Stock_ID'].astype(str).str.upper() == t_stock].copy()
            df_s['P'] = pd.to_numeric(df_s['My_Price'], errors='coerce').fillna(0)
            df_s['Q'] = pd.to_numeric(df_s['Quantity'], errors='coerce').fillna(0)
            
            old_qty = df_s[df_s['Action'] == "加倉"]['Q'].sum() - df_s[df_s['Action'] == "平倉"]['Q'].sum()
            
            if t_type == "加倉":
                # 加權平均成本公式: (舊量*舊價 + 新量*新價) / (舊量+新量)
                if old_qty > 0:
                    old_avg_cost = (df_s[df_s['Action'] == "加倉"]['P'] * df_s[df_s['Action'] == "加倉"]['Q']).sum() / df_s[df_s['Action'] == "加倉"]['Q'].sum()
                    new_qty = old_qty + t_qty
                    new_avg_cost = ((old_avg_cost * old_qty) + (t_price * t_qty)) / new_qty
                else:
                    new_qty = t_qty
                    new_avg_cost = t_price
                
                # 為了維持「直接覆蓋」的清爽，我們刪除舊紀錄，只存一筆最新的累加結果
                df_all = df_all[df_all['Stock_ID'].astype(str).str.upper() != t_stock]
                t_final_price = new_avg_cost
                t_final_qty = new_qty
                t_final_note = f"➕ 加倉累加: {t_note}"
            
            elif t_type == "平倉":
                new_qty = max(0, old_qty - t_qty)
                # 平倉不影響平均成本，只影響數量
                old_avg_cost = (df_s[df_s['Action'] == "加倉"]['P'] * df_s[df_s['Action'] == "加倉"]['Q']).sum() / df_s[df_s['Action'] == "加倉"]['Q'].sum() if old_qty > 0 else 0
                
                df_all = df_all[df_all['Stock_ID'].astype(str).str.upper() != t_stock]
                t_final_price = old_avg_cost
                t_final_qty = new_qty
                t_final_note = f"➖ 平倉減少: {t_note}"
            
            # 建立一筆最終的彙整紀錄
            new_row = pd.DataFrame([{
                "Date": str(t_date), "Stock_ID": t_stock, "Action": "加倉", 
                "My_Price": float(t_final_price), "Quantity": int(t_final_qty), 
                "Day_High": dh, "Day_Low": dl, "Day_Close": dc, "Day_Change": chg, "Note": t_final_note
            }])
        else:
            # 「觀察中」不參與累加計算，直接新增紀錄
            new_row = pd.DataFrame([{
                "Date": str(t_date), "Stock_ID": t_stock, "Action": t_type, 
                "My_Price": float(t_price), "Quantity": int(t_qty), 
                "Day_High": dh, "Day_Low": dl, "Day_Close": dc, "Day_Change": chg, "Note": t_note
            }])

        # 4. 更新回 Google Sheets
        final_df = pd.concat([df_all, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=final_df)
        st.cache_data.clear()
        st.success(f"✅ 成功！{t_stock} 已完成累加計算並更新。")
        st.rerun()
        
    except Exception as e: st.error(f"儲存失敗: {e}")

# ==========================================
# 4. 第四部分：歷史紀錄查詢 (百分比顯示修正版)
# ==========================================
st.divider()
st.header("📜 歷史紀錄查詢")

try:
    # 使用快取函數讀取資料
    df_hist = fetch_data("Sheet1")
    
    if df_hist is not None and not df_hist.empty:
        # 1. 動作篩選器
        actions = df_hist['Action'].unique().tolist()
        sel_actions = st.multiselect("🔍 篩選動作類型", actions, default=actions)
        
        # 2. 複製資料並過濾
        df_f = df_hist[df_hist['Action'].isin(sel_actions)].copy()
        df_f = df_f.sort_values(by='Date', ascending=False)
        
        # 3. 核心修正：處理漲跌幅數值
        if 'Day_Change' in df_f.columns:
            # 先將字串中的 % 移除，並處理 N/A 轉為 0
            temp_chg = (
                df_f['Day_Change']
                .astype(str)
                .str.replace('%', '', regex=False)
                .replace('N/A', '0')
            )
            # 轉為純數字 (例如 "2.39" 變成 2.39)
            df_f['Chg_Num'] = pd.to_numeric(temp_chg, errors='coerce').fillna(0)
            
            # 安全機制：如果數值非常小 (例如 0.0239)，代表它是原始小數，則乘以 100
            # 如果數值已經是 2.39，則保持不變
            if df_f['Chg_Num'].abs().max() < 1 and df_f['Chg_Num'].abs().max() != 0:
                df_f['Display_Chg'] = df_f['Chg_Num'] * 100
            else:
                df_f['Display_Chg'] = df_f['Chg_Num']
        else:
            df_f['Display_Chg'] = 0

        # 4. 定義顏色樣式 (紅漲綠跌)
        def color_hist_chg(val):
            color = 'red' if val > 0 else 'green' if val < 0 else '#cccccc'
            return f'color: {color}; font-weight: bold'

        # 5. 顯示表格
        st.dataframe(
            df_f.style.map(color_hist_chg, subset=['Display_Chg']),
            column_config={
                "Date": "日期",
                "Stock_ID": "代碼",
                "Action": "動作",
                "My_Price": st.column_config.NumberColumn("成交/觀察價", format="$%.2f"),
                "Day_High": "最高",
                "Day_Low": "最低",
                "Day_Close": "收盤",
                "Display_Chg": st.column_config.NumberColumn(
                    "當日漲跌", 
                    help="當天收盤相對於前一天的漲跌幅百分比",
                    format="%.2f%%"  # 這裡會顯示如 2.39%
                ),
                "Note": "分析備註"
            },
            # 指定顯示順序並隱藏原始的 Day_Change 和中間計算欄位
            column_order=("Date", "Stock_ID", "Action", "My_Price", "Day_High", "Day_Low", "Day_Close", "Display_Chg", "Note"),
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("目前尚無歷史交易紀錄。")
except Exception as e:
    st.error(f"歷史紀錄載入失敗：{e}")
