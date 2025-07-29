# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit
#
# 使用前請確認：
# 1. 專案資料夾結構如下：
#    - /images/ (存放原始影像)
#    - /predicted_images/ (存放標記後影像)
#    - review_app.py (本檔案)
# 2. 兩個影像資料夾中的對應檔名必須相同。
#
# 如何執行：
# 1. 開啟 Anaconda Prompt
# 2. conda activate review_app
# 3. cd path/to/medical_review_system
# 4. streamlit run review_app.py
# --------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import os
from PIL import Image
import io

# --- 1. 設定區 ---
ORIGINAL_IMAGE_DIR = "images"
PREDICTED_IMAGE_DIR = "predicted_images"
OUTPUT_EXCEL_PATH = "review_results.xlsx"

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
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True
    st.header("病兆標記審核介面 登入")
    password = st.text_input("輸入密碼 (Password)", type="password")
    if password == "123": # 請務必更換為一個複雜的密碼
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
st.markdown("---")

# 讀取影像檔案列表
try:
    image_files = sorted([f for f in os.listdir(ORIGINAL_IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    if not image_files:
        st.error(f"錯誤：在資料夾 '{ORIGINAL_IMAGE_DIR}' 中找不到任何影像檔案。")
        st.stop()
except FileNotFoundError:
    st.error(f"錯誤：找不到影像資料夾 '{ORIGINAL_IMAGE_DIR}'。")
    st.stop()

# --- 【修改點】初始化 Session State ---
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
# 將 results 從 list 改為 dict，用於儲存可編輯的審核結果
if 'results' not in st.session_state:
    st.session_state.results = {}

# 檢查是否所有影像都已審核完畢
if st.session_state.current_index >= len(image_files):
    st.success("🎉 所有影像皆已審核完畢！感謝您的辛勞。")
    st.balloons()

    if st.session_state.results:
        st.subheader("最終審核結果預覽：")
        # --- 【修改點】從字典整理最終結果以建立 DataFrame ---
        final_data = []
        for filename, review_data in st.session_state.results.items():
            final_data.append({
                "影像檔名 (Filename)": filename,
                "審核結果 (Review)": "; ".join(review_data['options']),
                "醫師備註 (Notes)": review_data['notes'],
                "審核時間 (Timestamp)": review_data['timestamp']
            })
        final_df = pd.DataFrame(final_data)
        st.dataframe(final_df)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Sheet1')
        excel_data = output.getvalue()
        st.download_button(
            label="下載審核結果 (Excel)",
            data=excel_data,
            file_name=OUTPUT_EXCEL_PATH,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    st.stop()

# 獲取當前影像資訊
current_image_name = image_files[st.session_state.current_index]

# --- 【修改點】讀取此影像之前的審核記錄，用於恢復介面狀態 ---
previous_review = st.session_state.results.get(current_image_name, {"options": [], "notes": ""})

# --- 3. 介面佈局 ---
progress_text = f"進度： {st.session_state.current_index + 1} / {len(image_files)}"
st.info(progress_text)

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"原始影像： {current_image_name}")
    st.image(os.path.join(ORIGINAL_IMAGE_DIR, current_image_name), use_container_width=True)
with col2:
    st.subheader(f"模型標記影像： {current_image_name}")
    st.image(os.path.join(PREDICTED_IMAGE_DIR, current_image_name), use_container_width=True)
st.markdown("---")

# --- 【修改點】將表單與按鈕分離 ---
# 表單僅用於收集當前頁面的輸入
with st.form(key=f"review_form_{st.session_state.current_index}"):
    st.subheader("請勾選所有適用的審核項目 (可複選)：")

    # 使用字典來收集 checkbox 的狀態
    review_status = {}
    for option in REVIEW_OPTIONS:
        # 使用 previous_review 來設定 checkbox 的預設狀態
        review_status[option] = st.checkbox(
            option, 
            value=(option in previous_review["options"]), # 恢復勾選狀態
            key=f"cb_{option}_{st.session_state.current_index}"
        )
    
    # 使用 previous_review 來設定 text_area 的預設狀態
    notes = st.text_area("補充說明 (選填)", value=previous_review["notes"])

    # 表單內不再需要提交按鈕，但 st.form 要求至少有一個按鈕，所以放一個隱形的
    st.form_submit_button(label='儲存選填結果', help='此按鈕僅用於儲存此張影像審核狀態', type="primary", use_container_width=True)


# --- 【修改點】將導航按鈕放在表單外部 ---
nav_cols = st.columns(7)
with nav_cols[0]:
    # "返回上一張" 按鈕
    if st.button("上一張", use_container_width=True):
        if st.session_state.current_index > 0:
            st.session_state.current_index -= 1
            st.rerun()

with nav_cols[6]:
    # "儲存並下一張" 按鈕
    if st.button("下一張", type="primary", use_container_width=True):
        # 從 review_status 字典中收集勾選的項目
        selected_options = [option for option, checked in review_status.items() if checked]
        
        # 檢查是否至少勾選一項或填寫備註
        if not selected_options and not notes:
            st.warning("請至少選填一個審核項目後儲存再繼續。")
        else:
            # 更新或新增這張圖片的審核結果到 results 字典
            st.session_state.results[current_image_name] = {
                "options": selected_options,
                "notes": notes,
                "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            # 前進到下一張
            st.session_state.current_index += 1
            st.rerun()