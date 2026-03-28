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

import pandas as pd
from datetime import date

# --- 交易紀錄輸入服務 ---
st.divider()
st.header("📝 新增交易紀錄")

# 建立兩欄式表單
with st.form("transaction_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        t_date = st.date_input("交易日期", date.today())
        t_stock = st.text_input("股票代碼", placeholder="例如: 2330.TW 或 NVDA")
        
    with col2:
        t_type = st.selectbox("交易類型", ["加倉", "平倉"])
        t_price = st.number_input("成交單價", min_value=0.0, step=0.1)
        
    with col3:
        t_qty = st.number_input("成交數量", min_value=1, step=1)
        t_note = st.text_input("備註", placeholder="紀錄理由")

    submit_button = st.form_submit_button("確認儲存紀錄")

# --- 處理儲存邏輯 ---
if submit_button:
    if t_stock:
        try:
            # 1. 嘗試讀取資料，如果失敗就建立一個空的 DataFrame
            try:
                existing_data = conn.read(worksheet="Data", ttl=0)
            except:
                existing_data = pd.DataFrame(columns=["Date", "Stock_ID", "Action", "Price", "Quantity", "Note"])
            
            # 2. 準備新的一行數據
            new_record = pd.DataFrame([{
                "Date": str(t_date),
                "Stock_ID": t_stock.upper().strip(),
                "Action": t_type,
                "Price": float(t_price),
                "Quantity": int(t_qty),
                "Note": str(t_note)
            }])
            
            # 3. 合併數據 (確保即使 existing_data 是 None 也能跑)
            if existing_data is not None and not existing_data.empty:
                # 確保欄位一致性
                updated_df = pd.concat([existing_data, new_record], ignore_index=True)
            else:
                updated_df = new_record
                
            # 4. 更新回 Google Sheets
            conn.update(worksheet="Data", data=updated_df)
            
            st.success(f"✅ 已成功紀錄！")
            st.balloons()
            st.rerun()
            
        except Exception as e:
            # 這裡會顯示更詳細的錯誤資訊
            st.error(f"⚠️ 發生錯誤：{e}")
            st.info("請確認試算表左下角的分頁名稱是否真的改成了 Data")
    else:
        st.warning("請輸入股票代碼！")
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
            # 1. 準備這一筆新資料
            new_data = pd.DataFrame([{
                "Date": str(s_date),
                "Stock_ID": str(s_id).upper(), # 強制轉大寫
                "Action": str(s_action),
                "Price": float(s_price),
                "Note": str(s_note)
            }])
            
            # 2. 嘗試讀取現有資料
            try:
                # 注意：這裡 worksheet 統一名稱為 "Sheet1"
                existing_df = conn.read(worksheet="Data", ttl=0)
                # 如果讀取成功且有資料，就合併
                if existing_df is not None and not existing_df.empty:
                    updated_df = pd.concat([existing_df, new_data], ignore_index=True)
                else:
                    updated_df = new_data
            except:
                # 如果讀取失敗（例如表是空的），就直接用新資料
                updated_df = new_data

            # 3. 強制推送到 Google Sheets (這步最關鍵，使用 create 重新定義結構)
            conn.update(worksheet="Sheet1", data=updated_df)
            
            st.success(f"✅ 成功存入！代碼：{s_id}")
            st.balloons()
            st.rerun() # 重新整理頁面顯示新結果
            
        except Exception as e:
            st.error(f"⚠️ 儲存仍有問題，請檢查 Secrets 裡的網址。錯誤詳情：{e}")
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
st.divider()
st.header("💰 當前持倉損益分析")

try:
    df_calc = conn.read(worksheet="Data", ttl=0)
    
    if not df_calc.empty:
        # 1. 基礎數據清理
        df_calc['Price'] = pd.to_numeric(df_calc['Price'])
        
        # 2. 彙總每一支股票的持倉狀況
        summary = []
        for stock_id in df_calc['Stock_ID'].unique():
            df_stock = df_calc[df_calc['Stock_ID'] == stock_id]
            
            # 簡單邏輯：加倉視為買入，平倉視為賣出（這裡假設每次動作單位為1，你可以未來加入數量欄位）
            # 目前先計算平均成本
            buy_prices = df_stock[df_stock['Action'] == "加倉"]['Price']
            if not buy_prices.empty:
                avg_cost = buy_prices.mean()
                
                # 3. 抓取最新市價
                try:
                    ticker = yf.Ticker(stock_id)
                    current_price = ticker.fast_info['last_price']
                except:
                    current_price = avg_cost # 抓不到時暫以成本計
                
                # 4. 計算損益
                profit_loss = current_price - avg_cost
                roi = (profit_loss / avg_cost) * 100
                
                summary.append({
                    "股票代碼": stock_id,
                    "平均成本": round(avg_cost, 2),
                    "目前市價": round(current_price, 2),
                    "單股損益": round(profit_loss, 2),
                    "投報率 (ROI)": f"{round(roi, 2)}%"
                })
        
        # 5. 顯示損益表
        if summary:
            df_summary = pd.DataFrame(summary)
            
            # 使用 st.column 製作儀表板亮點
            total_pnl = df_summary['單股損益'].sum()
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("總累計損益 (單股計)", f"${round(total_pnl, 2)}", f"{round(total_pnl, 2)}")
            
            st.dataframe(
                df_summary,
                column_config={
                    "投報率 (ROI)": st.column_config.TextColumn("投報率", help="綠色代表獲利，紅色代表虧損"),
                },
                hide_index=True,
                use_container_width=True
            )
    else:
        st.info("尚無持倉數據可供計算。")

except Exception as e:
    st.error(f"損益計算發生錯誤：{e}")
