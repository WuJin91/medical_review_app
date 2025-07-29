import streamlit as st
import pandas as pd
import os
from PIL import Image
from streamlit_gsheets import GSheetsConnection

# --- 1. 設定區 ---
ORIGINAL_IMAGE_DIR = "images"
PREDICTED_IMAGE_DIR = "predicted_images"

REVIEW_OPTIONS = [
    "標記完全正確",
    "有未標記出的病兆 (漏標)",
    "病兆名稱標記錯誤",
    "標記框不精準",
    "標記了不存在病兆的位置", 
    "其他問題 (請在備註說明)"
]

# --- 2. 密碼驗證與主應用程式邏輯 ---

def check_password():
    """使用 st.secrets 中的密碼進行驗證"""
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True
    
    st.header("病兆標記審核介面 登入")
    password = st.text_input("輸入密碼 (Password)", type="password")
    
    correct_password = st.secrets.get("APP_PASSWORD", "12345")
    if not correct_password:
        st.error("錯誤：找不到設定的 APP_PASSWORD。請確認您的 secrets.toml 檔案已正確設定。")
        return False

    if password and password == correct_password:
        st.session_state["password_correct"] = True
        st.rerun()
        return True
    elif password:
        st.error("密碼錯誤，請重新輸入。")
    
    return False

if not check_password():
    st.stop()

st.set_page_config(layout="wide", page_title="醫師影像審核系統")
st.title("病兆標記審核介面")
st.text("標記類別：瘜肉(polyp)、腫瘤(tumor)、無病兆(No)")

# --- 建立與 Google Sheets 的連接 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"無法連接至 Google Sheets。請檢查您的 secrets.toml 設定是否正確。錯誤訊息：{e}")
    st.stop()

# 讀取所有本地影像檔案列表
try:
    image_files = sorted([f for f in os.listdir(ORIGINAL_IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    total_files = len(image_files)
except FileNotFoundError:
    st.error(f"錯誤：找不到本地影像資料夾 '{ORIGINAL_IMAGE_DIR}'。")
    st.stop()

# --- 引入 session_state 來管理當前頁碼 ---
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

# --- 讀取 GSheet 資料並處理成「每個檔案的最新一筆紀錄」---
try:
    with st.spinner("正在從 Google Sheets 同步進度..."):
        existing_data = conn.read(worksheet="Sheet1", usecols=list(range(4)), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if not existing_data.empty:
            existing_data['審核時間 (Timestamp)'] = pd.to_datetime(existing_data['審核時間 (Timestamp)'])
            latest_reviews_df = existing_data.sort_values(
                '審核時間 (Timestamp)', ascending=False
            ).drop_duplicates(subset='影像檔名 (Filename)', keep='first')
        else:
            latest_reviews_df = pd.DataFrame()

except Exception as e:
    st.error(f"讀取 Google Sheet 'Sheet1' 失敗。請確認工作表名稱和權限設定是否正確。錯誤訊息：{e}")
    st.stop()

# 檢查是否所有影像都已審核完畢
if len(latest_reviews_df) >= total_files and total_files > 0:
    st.success("🎉 所有影像皆已審核完畢！感謝您的辛勞。")
    st.balloons()
    st.stop()

# --- 獲取當前要顯示的影像 ---
current_index = st.session_state.current_index
current_image_name = image_files[current_index]

# --- 讀取此影像之前的審核記錄，用於恢復介面狀態 ---
if not latest_reviews_df.empty and current_image_name in latest_reviews_df['影像檔名 (Filename)'].values:
    previous_review_series = latest_reviews_df.loc[latest_reviews_df['影像檔名 (Filename)'] == current_image_name].iloc[0]
    previous_options = previous_review_series.get('審核結果 (Review)', '').split('; ')
    previous_notes = previous_review_series.get('醫師備註 (Notes)', '')
else:
    previous_options = []
    previous_notes = ""
    
# --- 3. 介面佈局 ---
progress_text = f"進度: {current_index + 1} / {total_files}"
st.info(progress_text)

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"原始影像: {current_image_name}")
    st.image(os.path.join(ORIGINAL_IMAGE_DIR, current_image_name), use_container_width=True)
with col2:
    st.subheader(f"模型標記影像: {current_image_name}")
    st.image(os.path.join(PREDICTED_IMAGE_DIR, current_image_name), use_container_width=True)
st.markdown("---")

# 表單僅用於收集輸入，但內部不再需要提交按鈕
with st.form(key=f"review_form_{current_image_name}"):
    st.subheader("請勾選所有適用的審核項目 (可複選)：")
    review_status = {}
    for option in REVIEW_OPTIONS:
        review_status[option] = st.checkbox(option, value=(option in previous_options))
    
    notes = st.text_area("補充說明 (選填)", value=previous_notes)
    
    # --- 【修改點】---
    # st.form_submit_button("同步當前選項")  <-- 此行已被移除

# --- 將導覽按鈕放在表單外部 ---
nav_cols = st.columns([1, 5, 1]) 

with nav_cols[0]:
    if st.button("返回上一張", use_container_width=True):
        if st.session_state.current_index > 0:
            st.session_state.current_index -= 1
            st.rerun()

with nav_cols[2]:
    if st.button("儲存並下一張", type="primary", use_container_width=True):
        selected_options = [option for option, checked in review_status.items() if checked]
        if not selected_options and not notes:
            st.warning("請至少選填一個審核項目或填寫備註後再儲存。")
        else:
            with st.spinner("正在將結果寫入 Google Sheets..."):
                review_summary = "; ".join(selected_options)
                
                new_data = pd.DataFrame([{
                    "影像檔名 (Filename)": current_image_name,
                    "審核結果 (Review)": review_summary,
                    "醫師備註 (Notes)": notes,
                    "審核時間 (Timestamp)": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                }])
                
                # 使用 conn.update 來附加新紀錄
                conn.update(worksheet="Sheet1", data=new_data)
                
                st.success(f"影像 {current_image_name} 的審核結果已成功儲存！")

                if st.session_state.current_index < total_files - 1:
                    st.session_state.current_index += 1
                
                # 重新執行以刷新頁面到下一張圖片或顯示完成訊息
                st.rerun()