import streamlit as st
import pandas as pd

st.title("💰 錢多多的投資管理系統")
st.write("這是我的第一個投資網頁！")

# 模擬一個簡單的輸入框
stock = st.text_input("請輸入選股代碼：", "2330")
price = st.number_input("加倉價格：", value=600)

if st.button("儲存紀錄"):
    st.success(f"已成功紀錄 {stock} 在 {price} 元的交易！")
