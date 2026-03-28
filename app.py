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

# --- 第二部分：當前持倉損益分析 ---
st.divider()
st.header("💰 當前持倉損益分析")

try:
    # 確保從 Sheet1 讀取
    df_calc = conn.read(worksheet="Sheet1", ttl=0)
    
    if df_calc is not None and not df_calc.empty:
        # 統一轉大寫並確保數值化
        df_calc['Stock_ID'] = df_calc['Stock_ID'].str.upper()
        df_calc['Price'] = pd.to_numeric(df_calc['Price'], errors='coerce')
        df_calc['Quantity'] = pd.to_numeric(df_calc['Quantity'], errors='coerce').fillna(0)
        
        summary = []
        for stock_id in df_calc['Stock_ID'].unique():
            if not stock_id: continue
            df_stock = df_calc[df_calc['Stock_ID'] == stock_id]
            
            # 計算庫存：加倉(+) 平倉(-)
            buy_q = df_stock[df_stock['Action'] == "加倉"]['Quantity'].sum()
            sell_q = df_stock[df_stock['Action'] == "平倉"]['Quantity'].sum()
            current_q = buy_q - sell_q
            
            if current_q > 0:
                # 計算平均成本
                buys = df_stock[df_stock['Action'] == "加倉"]
                avg_cost = (buys['Price'] * buys['Quantity']).sum() / buys['Quantity'].sum()
                
                try:
                    ticker = yf.Ticker(stock_id)
                    current_price = ticker.fast_info['last_price']
                except:
                    current_price = avg_cost
                
                profit_loss = (current_price - avg_cost) * current_q
                roi = ((current_price - avg_cost) / avg_cost) * 100
                
                summary.append({
                    "股票代碼": stock_id, "持股數量": current_q,
                    "平均成本": round(avg_cost, 2), "目前市價": round(current_price, 2),
                    "總損益": round(profit_loss, 2), "投報率": f"{round(roi, 2)}%"
                })
        
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
        else:
            st.info("目前無持倉數據（請先新增加倉紀錄）。")
    else:
        st.info("Sheet1 尚無資料。")
except Exception as e:
    st.error(f"損益計算讀取失敗：{e}")

# --- 第三部分：新增交易紀錄表單 ---
st.divider()
st.header("📝 新增交易紀錄")

with st.form("transaction_form_v3", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        t_date = st.date_input("交易日期", date.today())
        t_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW")
    with col2:
        t_type = st.selectbox("交易類型", ["加倉", "平倉", "觀察中"])
        t_price = st.number_input("成交單價", min_value=0.0, step=0.1)
    with col3:
        t_qty = st.number_input("成交數量", min_value=0, step=1, value=1)
        t_note = st.text_input("分析備註")

    submit_button = st.form_submit_button("確認儲存紀錄至 Sheet1")

if submit_button:
    if t_stock:
        try:
            try:
                existing_data = conn.read(worksheet="Sheet1", ttl=0)
            except:
                existing_data = pd.DataFrame(columns=["Date", "Stock_ID", "Action", "Price", "Quantity", "Note"])
            
            new_record = pd.DataFrame([{
                "Date": str(t_date),
                "Stock_ID": t_stock.upper().strip(),
                "Action": t_type,
                "Price": float(t_price),
                "Quantity": int(t_qty),
                "Note": str(t_note)
            }])
            
            updated_df = pd.concat([existing_data, new_record], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            
            st.success(f"✅ 已成功紀錄並存入 Sheet1！")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"儲存失敗，請確認 Google Sheets 分頁名稱為 Sheet1。錯誤：{e}")
    else:
        st.warning("請輸入股票代碼！")

# --- 第四部分：歷史紀錄表格 ---
st.divider()
st.header("📜 歷史交易紀錄 (Sheet1)")
try:
    df_history = conn.read(worksheet="Sheet1", ttl=0)
    if df_history is not None and not df_history.empty:
        st.dataframe(df_history.sort_values(by='Date', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("尚無歷史紀錄。")
except:
    st.info("無法讀取歷史紀錄。")
