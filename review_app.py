# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit (V4 - Google Sheets 整合版)
# --------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import os
from PIL import Image
from streamlit_gsheets import GSheetsConnection

# --- 1. 設定區 ---
ORIGINAL_IMAGE_DIR = "images"
PREDICTED_IMAGE_DIR = "predicted_images"

REVIEW_OPTIONS = [
    "✅ 標記完全正確",
    "⚠️ 有未標記出的病兆 (漏標)",
    "❌ 類別標記錯誤",
    "📐 標記框不精準",
    "🤔 偽陽性 (標記了不存在的物件)",
    "📋 其他問題 (請在備註說明)"
]

# --- 2. 密碼驗證與主應用程式邏輯 ---

def check_password():
    """使用 st.secrets 中的密碼進行驗證"""
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True
    
    st.header("請先登入")
    password = st.text_input("請輸入密碼 (Password)", type="password")
    
    # 從 secrets.toml 讀取密碼
    correct_password = st.secrets.get("APP_PASSWORD", "") # 提供一個空字串作為預設值
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
st.title("YOLOv8 瘜肉/腫瘤標記審核介面")

# --- 建立與 Google Sheets 的連接 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"無法連接至 Google Sheets。請檢查您的 secrets.toml 設定是否正確。錯誤訊息：{e}")
    st.stop()

# 讀取所有本地影像檔案列表
try:
    image_files = sorted([f for f in os.listdir(ORIGINAL_IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
except FileNotFoundError:
    st.error(f"錯誤：找不到本地影像資料夾 '{ORIGINAL_IMAGE_DIR}'。")
    st.stop()

# --- 從 Google Sheets 讀取現有資料來決定進度 ---
try:
    with st.spinner("正在從 Google Sheets 同步進度..."):
        existing_data = conn.read(worksheet="Sheet1", usecols=list(range(4)), ttl=5)
        existing_data = existing_data.dropna(how='all')
    reviewed_files = set(existing_data['影像檔名 (Filename)'])
    
    # 篩選出尚未審核的檔案
    unreviewed_files = [f for f in image_files if f not in reviewed_files]
except Exception as e:
    st.error(f"讀取 Google Sheet 'Sheet1' 失敗。請確認工作表名稱和權限設定是否正確。錯誤訊息：{e}")
    st.stop()


# 檢查是否所有影像都已審核完畢
if not unreviewed_files:
    st.success("🎉 所有影像皆已審核完畢！感謝您的辛勞。")
    st.balloons()
    st.subheader("所有結果都已即時儲存至您的 Google Sheet。")
    try:
        sheet_id = st.secrets.connections.gsheets.spreadsheet
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        st.markdown(f"**[點擊這裡查看 Google Sheet 結果]({sheet_url})**")
    except Exception:
        st.info("無法獲取 Google Sheet 連結，但資料已儲存。")
    st.stop()

# 獲取下一張要審核的影像
current_image_name = unreviewed_files[0]
current_index = len(reviewed_files)
total_files = len(image_files)

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

# 表單用於收集輸入
with st.form(key=f"review_form_{current_image_name}"):
    st.subheader("請勾選所有適用的審核結果 (可複選)：")
    review_status = {option: st.checkbox(option) for option in REVIEW_OPTIONS}
    notes = st.text_area("補充說明 (選填)")
    submitted = st.form_submit_button("➡️ 儲存到 Google Sheets 並檢視下一張", type="primary", use_container_width=True)

if submitted:
    selected_options = [option for option, checked in review_status.items() if checked]
    if not selected_options and not notes:
        st.warning("請至少勾選一個審核項目或填寫備註後再儲存。")
    else:
        with st.spinner("正在將結果寫入 Google Sheets..."):
            review_summary = "; ".join(selected_options)
            
            new_data = pd.DataFrame([{
                "影像檔名 (Filename)": current_image_name,
                "審核結果 (Review)": review_summary,
                "醫師備註 (Notes)": notes,
                "審核時間 (Timestamp)": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }])
            
            conn.update(worksheet="Sheet1", data=new_data)
            
            st.success(f"影像 {current_image_name} 的審核結果已成功儲存！")
            st.rerun()