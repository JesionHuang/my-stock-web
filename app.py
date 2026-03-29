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

# --- 第二部分：當前持倉損益分析 (含手動修正與一鍵清空) ---
st.divider()
st.header("💰 當前持倉損益分析")

with st.expander("🛠️ 持倉管理工具 (手動修正成本或一鍵清空)"):
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        m_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW", key="m_stock").upper().strip()
    with col_m2:
        m_qty = st.number_input("修正後總數量", min_value=0, step=1)
    with col_m3:
        m_cost = st.number_input("修正後平均成本", min_value=0.0, step=0.1)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("更新持倉數據", use_container_width=True):
            if m_stock:
                try:
                    df_temp = conn.read(worksheet="Sheet1", ttl=0)
                    new_adj = pd.DataFrame([{
                        "Date": str(date.today()), "Stock_ID": m_stock, "Action": "加倉",
                        "My_Price": float(m_cost), "Quantity": int(m_qty), "Note": "💡 手動修正持倉"
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df_temp, new_adj], ignore_index=True))
                    st.success(f"✅ {m_stock} 更新成功！")
                    st.rerun()
                except Exception as e: st.error(f"錯誤: {e}")
    with c2:
        if st.button("🔥 一鍵清空此標的持倉", use_container_width=True, type="primary"):
            if m_stock:
                try:
                    df_temp = conn.read(worksheet="Sheet1", ttl=0)
                    df_s = df_temp[df_temp['Stock_ID'].astype(str).str.upper() == m_stock]
                    if not df_s.empty:
                        df_s['Q'] = pd.to_numeric(df_s['Quantity'], errors='coerce').fillna(0)
                        curr_q = df_s[df_s['Action'] == "加倉"]['Q'].sum() - df_s[df_s['Action'] == "平倉"]['Q'].sum()
                        if curr_q > 0:
                            clear_rec = pd.DataFrame([{"Date": str(date.today()), "Stock_ID": m_stock, "Action": "平倉", "My_Price": 0.0, "Quantity": int(curr_q), "Note": "🗑️ 一鍵清空"}])
                            conn.update(worksheet="Sheet1", data=pd.concat([df_temp, clear_rec], ignore_index=True))
                            st.success(f"✅ {m_stock} 已清空！"); st.rerun()
                except Exception as e: st.error(f"錯誤: {e}")

try:
    df_calc = conn.read(worksheet="Sheet1", ttl=0)
    if df_calc is not None and not df_calc.empty:
        df_calc['Calc_Price'] = pd.to_numeric(df_calc['My_Price'], errors='coerce').fillna(0)
        df_calc['Quantity'] = pd.to_numeric(df_calc['Quantity'], errors='coerce').fillna(0)
        df_calc['Stock_ID'] = df_calc['Stock_ID'].astype(str).str.upper()

        summary = []
        for stock_id in df_calc['Stock_ID'].unique():
            if not stock_id or stock_id == "NAN": continue
            df_stock = df_calc[df_calc['Stock_ID'] == stock_id]
            current_q = df_stock[df_stock['Action'] == "加倉"]['Quantity'].sum() - df_stock[df_stock['Action'] == "平倉"]['Quantity'].sum()
            
            if current_q > 0:
                buys = df_stock[df_stock['Action'] == "加倉"]
                avg_cost = (buys['Calc_Price'] * buys['Quantity']).sum() / buys['Quantity'].sum()
                try:
                    tk = yf.Ticker(stock_id); hist = tk.history(period="1mo")['Close']
                    curr_p = hist.iloc[-1]
                    def norm(s, d):
                        data = s.iloc[-d:]; avg = data.mean(); diff = data - avg
                        mx = diff.abs().max() if diff.abs().max() != 0 else 1
                        return (diff / mx).tolist()
                    t5, t10, t20 = norm(hist, 5), norm(hist, 10), norm(hist, 20)
                except:
                    curr_p = avg_cost; t5 = t10 = t20 = []
                
                summary.append({
                    "股票代碼": stock_id, "持股數量": int(current_q), "平均成本": round(avg_cost, 2),
                    "目前市價": round(curr_p, 2), "總損益": round((curr_p - avg_cost) * current_q, 2),
                    "投報率_數值": (curr_p - avg_cost) / avg_cost, "5日趨勢": t5, "10日趨勢": t10, "20日趨勢": t20
                })
        
        if summary:
            df_final = pd.DataFrame(summary)
            def color_pnl(val): return f'color: {"red" if val > 0 else "green" if val < 0 else "#ccc"}; font-weight: bold'
            st.dataframe(df_final.style.map(color_pnl, subset=['總損益', '投報率_數值']), column_config={
                "總損益": st.column_config.NumberColumn(format="$%.2f"),
                "投報率_數值": st.column_config.NumberColumn("投報率", format="%.2f%%"),
                "5日趨勢": st.column_config.LineChartColumn(y_min=-1, y_max=1),
                "10日趨勢": st.column_config.LineChartColumn(y_min=-1, y_max=1),
                "20日趨勢": st.column_config.LineChartColumn(y_min=-1, y_max=1),
            }, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"持倉分析載入失敗：{e}")

# --- 第三部分：新增交易紀錄表單 ---
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
            with st.spinner(f"正在抓取 {t_stock} 行情..."):
                tk = yf.Ticker(t_stock.upper().strip()); hist = tk.history(period="2d")
                if not hist.empty:
                    d_h, d_l, d_c = round(hist['High'].iloc[-1], 2), round(hist['Low'].iloc[-1], 2), round(hist['Close'].iloc[-1], 2)
                    d_chg = f"{round(((d_c - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2)}%" if len(hist) >= 2 else "N/A"
                else: d_h = d_l = d_c = 0; d_chg = "N/A"

            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            new_record = pd.DataFrame([{"Date": str(t_date), "Stock_ID": t_stock.upper().strip(), "Action": t_type, "My_Price": float(t_price), "Quantity": int(t_qty), "Day_High": d_h, "Day_Low": d_l, "Day_Close": d_c, "Day_Change": d_chg, "Note": str(t_note)}])
            conn.update(worksheet="Sheet1", data=pd.concat([existing_data, new_record], ignore_index=True))
            st.success("✅ 儲存成功！"); st.balloons(); st.rerun()
        except Exception as e: st.error(f"失敗: {e}")

# --- 第四部分：歷史紀錄查詢 ---
st.divider()
st.header("📜 歷史紀錄查詢")

try:
    df_history = conn.read(worksheet="Sheet1", ttl=0)
    if df_history is not None and not df_history.empty:
        all_actions = df_history['Action'].unique().tolist()
        selected_actions = st.multiselect("🔍 篩選動作類型", all_actions, default=all_actions)
        filtered_df = df_history[df_history['Action'].isin(selected_actions)].copy().sort_values(by='Date', ascending=False)
        
        if 'Day_Change' in filtered_df.columns:
            filtered_df['Display_Change'] = pd.to_numeric(filtered_df['Day_Change'].astype(str).str.replace('%', '').replace('N/A', '0'), errors='coerce').fillna(0)
            if filtered_df['Display_Change'].abs().max() > 1: filtered_df['Display_Change'] /= 100
        
        def color_style(val): return f'color: {"red" if val > 0 else "green" if val < 0 else "#ccc"}; font-weight: bold'
        st.dataframe(filtered_df.style.map(color_style, subset=['Display_Change']), column_config={
            "My_Price": st.column_config.NumberColumn("成交價", format="$%.2f"),
            "Display_Change": st.column_config.NumberColumn("當日漲跌", format="%.2f%%")
        }, hide_index=True, use_container_width=True)
except Exception as e: st.error(f"讀取錯誤：{e}")
