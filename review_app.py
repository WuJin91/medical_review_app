# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit (V9 - 互動式標註最終版)
#
# 更新日誌:
# - 引入 streamlit-drawable-canvas 實現影像標註與修正功能。
# - 採用三欄式佈局，將工具、畫布、控制面板整合在單一畫面。
# - 實作了完整的 GSheet 儲存邏輯，以「一個標註框一列」的形式儲存，並支援覆蓋更新。
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit (V10 - 動態讀取 YOLO 預測)
#
# 更新日誌:
# - 移除寫死的 MOCK_PREDICTIONS。
# - 新增 load_yolo_predictions 函數，用於讀取、解析、轉換真實的 YOLO .txt 預測檔。
# - 主程式流程現在會為每一張圖片動態載入其對應的預測作為初始標註框。
# --------------------------------------------------------------------------
import streamlit as st
import pandas as pd
import os
from PIL import Image
from streamlit_gsheets import GSheetsConnection
from streamlit_drawable_canvas import st_canvas

# --- 1. 設定區 ---
ORIGINAL_IMAGE_DIR = "images"
YOLO_LABELS_DIR = "yolo_labels" # <--- 新增：YOLO 預測檔的路徑

# --- 2. 密碼驗證 (與之前版本相同，此處省略) ---
def check_password():
    # ... (您的 check_password 函數) ...
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True
    st.header("病兆標記審核介面 登入")
    password = st.text_input("輸入密碼 (Password)", type="password")
    correct_password = st.secrets.get("APP_PASSWORD", "123")
    if password and password == correct_password:
        st.session_state["password_correct"] = True
        st.rerun()
        return True
    elif password: st.error("密碼錯誤")
    return False

# --- 3. 核心繪圖與資料轉換函數 (新增 load_yolo_predictions) ---

def load_yolo_predictions(image_filename, image_width, image_height, class_map):
    """從 .txt 檔案讀取 YOLO 預測，並轉換為絕對像素座標"""
    label_path = os.path.join(YOLO_LABELS_DIR, os.path.splitext(image_filename)[0] + '.txt')
    predictions = []
    if not os.path.exists(label_path):
        return predictions # 如果沒有對應的預測檔，返回空列表

    with open(label_path, 'r') as f:
        for line in f.readlines():
            try:
                class_id, x_center, y_center, width, height = map(float, line.strip().split())
                
                # 將標準化座標轉換為絕對像素座標
                abs_width = width * image_width
                abs_height = height * image_height
                abs_x = (x_center * image_width) - (abs_width / 2)
                abs_y = (y_center * image_height) - (abs_height / 2)
                
                label = class_map.get(int(class_id), "unknown") # 從 class_id 查找類別名稱
                
                predictions.append({
                    "label": label,
                    "box": [abs_x, abs_y, abs_width, abs_height]
                })
            except ValueError:
                # 忽略格式不正確的行
                continue
    return predictions

def hex_to_rgba(hex_color, alpha=0.3):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"

def convert_canvas_to_df(image_filename, canvas_json_data, label_color_map):
    # ... (此函數與 V9 版本相同) ...
    records = []
    color_label_map = {v.upper(): k for k, v in label_color_map.items()}
    if canvas_json_data and 'objects' in canvas_json_data:
        for obj in canvas_json_data['objects']:
            if obj['type'] == 'rect':
                label = color_label_map.get(obj['stroke'].upper(), "unknown")
                records.append({
                    "影像檔名 (Filename)": image_filename, "類別 (Label)": label,
                    "x": int(obj['left']), "y": int(obj['top']),
                    "width": int(obj['width']), "height": int(obj['height']),
                    "審核時間 (Timestamp)": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                })
    return pd.DataFrame(records)

def load_initial_rects(image_filename, gsheet_df, predictions_for_image, label_color_map):
    # ... (此函數與 V9 版本相同，但傳入的 predictions 參數已是動態的) ...
    rects = []
    source = "無"
    if not gsheet_df.empty and image_filename in gsheet_df['影像檔名 (Filename)'].values:
        source = "Google Sheet"
        image_annotations = gsheet_df[gsheet_df['影像檔名 (Filename)'] == image_filename]
        for _, row in image_annotations.iterrows():
            stroke_color = label_color_map.get(row['類別 (Label)'], "#FFFFFF")
            rects.append({
                "type": "rect", "left": row['x'], "top": row['y'],
                "width": row['width'], "height": row['height'],
                "stroke": stroke_color, "strokeWidth": 2, 
                "fill": hex_to_rgba(stroke_color)
            })
    elif predictions_for_image:
        source = "模型預測"
        for pred in predictions_for_image:
            label, box = pred['label'], pred['box']
            stroke_color = label_color_map.get(label, "#FFFFFF")
            rects.append({
                "type": "rect", "left": box[0], "top": box[1],
                "width": box[2], "height": box[3],
                "stroke": stroke_color, "strokeWidth": 2, 
                "fill": hex_to_rgba(stroke_color)
            })
    return {"objects": rects}, source

# --- Streamlit App 主體 ---
st.set_page_config(layout="wide", page_title="互動式影像標註系統")

if not check_password():
    st.stop()

st.title("互動式病兆標註介面")

# --- 設定類別與顏色的對應 ---
CLASS_MAP = {0: "polyp", 1: "tumor"} # <--- 重要：請根據您的 YOLO 模型設定
LABEL_COLORS = {"polyp": "#FF0000", "tumor": "#0000FF"}

# --- 連接 GSheet 並讀取資料 ... (與 V9 版本相同) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    gsheet_df = conn.read(worksheet="Sheet1_BBOX", ttl=5).dropna(how='all')
except Exception as e:
    st.error(f"無法連接或讀取 Google Sheets。請檢查您的 secrets.toml 和工作表名稱 'Sheet1_BBOX' 是否正確。錯誤：{e}")
    gsheet_df = pd.DataFrame() # 如果讀取失敗，則建立一個空的 DataFrame

# --- 讀取本地影像檔案列表 ---
try:
    image_files = sorted([f for f in os.listdir(ORIGINAL_IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    total_files = len(image_files)
    if total_files == 0:
        st.error(f"錯誤：在資料夾 '{ORIGINAL_IMAGE_DIR}' 中找不到任何影像檔案。")
        st.stop()
except FileNotFoundError:
    st.error(f"錯誤：找不到本地影像資料夾 '{ORIGINAL_IMAGE_DIR}'。")
    st.stop()
    
# --- Session State 管理當前頁碼 ... (與 V9 版本相同) ---
# ...
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

current_index = st.session_state.current_index
current_image_name = image_files[current_index]

# --- 主要介面佈局 (與 V9 版本相同) ---
col1, col2, col3 = st.columns([0.2, 0.55, 0.25])

# --- 左側欄：工具箱 (與 V9 版本相同) ---
with col1:
    st.subheader("🛠️ 工具箱")
    drawing_mode = st.radio("工具:", ("transform", "rect"), horizontal=True, captions=["移動/編輯", "畫新矩形"])
    selected_label = st.radio("標註類別:", list(LABEL_COLORS.keys()))
    stroke_color = LABEL_COLORS[selected_label]
    st.write(f"目前顏色: <span style='color:{stroke_color}'>██</span> ({selected_label})", unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    **操作說明:**
    1. **移動/編輯**: 點選、移動、縮放現有標註框。
    2. **畫新矩形**: 先選好上方類別，再畫出新的標註框。
    3. **刪除**: 點選一個標註框後，按下鍵盤上的 `Delete` 鍵。
    4. **儲存**: 完成後點擊右方的儲存按鈕。
    """)

# --- 中間欄：畫布工作區 ---
with col2:
    st.info(f"進度: {current_index + 1} / {total_files} | 目前影像: {current_image_name}")
    
    try:
        bg_image = Image.open(os.path.join(ORIGINAL_IMAGE_DIR, current_image_name))
        
        # --- 【主要修改點】動態載入真實預測 ---
        # 1. 取得圖片實際尺寸
        img_width, img_height = bg_image.size
        # 2. 呼叫新函數，讀取此圖片的 YOLO 預測
        predictions_for_image = load_yolo_predictions(current_image_name, img_width, img_height, CLASS_MAP)
        # 3. 將真實預測傳入，以載入初始標註框
        initial_drawing, source = load_initial_rects(current_image_name, gsheet_df, predictions_for_image, LABEL_COLORS)
        
        canvas_result = st_canvas(
            # ... (canvas 參數與 V9 版本相同) ...
            stroke_width=2,
            stroke_color=stroke_color,
            background_image=bg_image,
            update_streamlit=True,
            height=img_height,
            width=img_width,
            drawing_mode=drawing_mode,
            initial_drawing=initial_drawing,
            key=f"canvas_{current_image_name}",
        )
    except FileNotFoundError:
        st.error(f"找不到背景圖片: {current_image_name}")
        canvas_result = None

# --- 右側欄：資料與控制 (與 V9 版本相同) ---
with col3:
    st.subheader("📊 目前標註結果")
    
    if canvas_result and canvas_result.json_data:
        display_df = convert_canvas_to_df(current_image_name, canvas_result.json_data, LABEL_COLORS)
        st.dataframe(display_df, use_container_width=True, height=300)
    else:
        st.write("畫布上沒有標註。")

    st.divider()
    st.write(f"初始標註來源: **{source}**")
    
    if st.button("💾 儲存本張標註", type="primary", use_container_width=True):
        if canvas_result and canvas_result.json_data:
            with st.spinner("正在儲存結果至 Google Sheets..."):
                new_annotations_df = convert_canvas_to_df(current_image_name, canvas_result.json_data, LABEL_COLORS)
                
                # 讀取 GSheet 現有全部資料
                all_gsheet_data = conn.read(worksheet="Sheet1_BBOX", ttl=0).dropna(how='all')
                
                # 刪除其中屬於 current_image_name 的所有舊紀錄
                filtered_data = all_gsheet_data[all_gsheet_data['影像檔名 (Filename)'] != current_image_name]
                
                # 將新的標註資料與過濾後的舊資料合併
                updated_gsheet_data = pd.concat([filtered_data, new_annotations_df], ignore_index=True)
                
                # 將合併後的完整資料寫回 GSheet
                conn.update(worksheet="Sheet1_BBOX", data=updated_gsheet_data)
                
                st.success(f"影像 {current_image_name} 的標註已儲存！")
        else:
            st.warning("畫布上沒有可儲存的標註。")

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("⬅️ 上一張", use_container_width=True):
            if st.session_state.current_index > 0:
                st.session_state.current_index -= 1
                st.rerun()
    with nav_cols[1]:
        if st.button("下一張 ➡️", use_container_width=True):
            if st.session_state.current_index < total_files - 1:
                st.session_state.current_index += 1
                st.rerun()