# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit (V12 - 修正 GSheet 名稱與畫布渲染問題)
#
# 更新日誌:
# - 修正 WorksheetNotFound 錯誤的提示。
# - 修正畫布渲染問題：在傳入 st_canvas 前，明確地將背景圖片縮放至與畫布相同的尺寸。
# --------------------------------------------------------------------------
import streamlit as st
import pandas as pd
import os
from PIL import Image
from streamlit_gsheets import GSheetsConnection
from streamlit_drawable_canvas import st_canvas

# --- 1. 設定區 ---
ORIGINAL_IMAGE_DIR = "images"
LABEL_DIR = "labels"
CANVAS_DISPLAY_WIDTH = 800 # 設定畫布在介面上的固定顯示寬度 (像素)

# --- 2. 密碼驗證 (與之前版本相同) ---
def check_password():
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True
    st.header("病兆標記審核介面 登入")
    password = st.text_input("輸入密碼 (Password)", type="password")
    correct_password = st.secrets.get("APP_PASSWORD", "123")
    if password and password == correct_password:
        st.session_state["password_correct"] = True
        st.rerun()
        return True
    elif password: st.error("密碼錯誤，請重新輸入。")
    return False

# --- 3. 核心繪圖與資料轉換函數 (與之前版本相同) ---
def hex_to_rgba(hex_color, alpha=0.3):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"

def convert_canvas_to_df(image_filename, canvas_json_data, label_color_map, scaling_ratio):
    records = []
    color_label_map = {v.upper(): k for k, v in label_color_map.items()}
    if canvas_json_data and 'objects' in canvas_json_data:
        for obj in canvas_json_data['objects']:
            if obj['type'] == 'rect':
                label = color_label_map.get(obj['stroke'].upper(), "unknown")
                records.append({
                    "影像檔名 (Filename)": image_filename,
                    "類別 (Label)": label,
                    "x": int(obj['left'] / scaling_ratio), "y": int(obj['top'] / scaling_ratio),
                    "width": int(obj['width'] / scaling_ratio), "height": int(obj['height'] / scaling_ratio),
                    "審核時間 (Timestamp)": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                })
    return pd.DataFrame(records)

def load_yolo_predictions(image_filename, image_width, image_height, class_map):
    predictions = []
    base_filename = os.path.splitext(image_filename)[0]
    label_path = os.path.join(LABEL_DIR, f"{base_filename}.txt")
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    class_index, x_center_norm, y_center_norm, width_norm, height_norm = map(float, parts)
                    abs_width = width_norm * image_width; abs_height = height_norm * image_height
                    left = (x_center_norm * image_width) - (abs_width / 2)
                    top = (y_center_norm * image_height) - (abs_height / 2)
                    label = class_map.get(int(class_index), "unknown")
                    predictions.append({"label": label, "box": [left, top, abs_width, abs_height]})
    return predictions

def load_initial_rects(image_filename, gsheet_df, model_predictions, label_color_map, scaling_ratio):
    rects = []
    source = "無"
    if not gsheet_df.empty and image_filename in gsheet_df['影像檔名 (Filename)'].values:
        source = "Google Sheet"
        image_annotations = gsheet_df[gsheet_df['影像檔名 (Filename)'] == image_filename]
        for _, row in image_annotations.iterrows():
            stroke_color = label_color_map.get(row['類別 (Label)'], "#FFFFFF")
            rects.append({"type": "rect", "left": row['x'] * scaling_ratio, "top": row['y'] * scaling_ratio, "width": row['width'] * scaling_ratio, "height": row['height'] * scaling_ratio, "stroke": stroke_color, "strokeWidth": 2, "fill": hex_to_rgba(stroke_color)})
    elif model_predictions:
        source = "模型預測"
        for pred in model_predictions:
            label, box = pred['label'], pred['box']
            stroke_color = label_color_map.get(label, "#FFFFFF")
            rects.append({"type": "rect", "left": box[0] * scaling_ratio, "top": box[1] * scaling_ratio, "width": box[2] * scaling_ratio, "height": box[3] * scaling_ratio, "stroke": stroke_color, "strokeWidth": 2, "fill": hex_to_rgba(stroke_color)})
    return {"objects": rects}, source

# --- Streamlit App 主體 ---
st.set_page_config(layout="wide", page_title="互動式影像標註系統")

if not check_password():
    st.stop()

st.title("互動式病兆標註介面")

CLASS_MAP = {0: "polyp", 1: "tumor"}
LABEL_COLORS = {"polyp": "#FF0000", "tumor": "#0000FF"}

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    gsheet_df = conn.read(worksheet="Sheet1_BBOX", ttl=5).dropna(how='all')
except gspread.exceptions.WorksheetNotFound:
    st.error("錯誤：在您的 Google Sheet 中找不到名為 'Sheet1_BBOX' 的工作表。請建立它或檢查名稱是否完全相符。")
    st.stop()
except Exception as e:
    st.error(f"無法連接或讀取 Google Sheets。請檢查您的 secrets.toml 設定。錯誤：{e}")
    st.stop()

try:
    image_files = sorted([f for f in os.listdir(ORIGINAL_IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    total_files = len(image_files)
    if total_files == 0: st.stop()
except FileNotFoundError:
    st.error(f"錯誤：找不到本地影像資料夾 '{ORIGINAL_IMAGE_DIR}'。")
    st.stop()

if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

current_index = st.session_state.current_index
current_image_name = image_files[current_index]

col1, col2, col3 = st.columns([0.2, 0.55, 0.25])

with col1:
    # ... (左側工具箱的程式碼與之前版本相同) ...
    st.subheader("🛠️ 工具箱")
    drawing_mode = st.radio("工具:", ("transform", "rect"), horizontal=True, captions=["移動/編輯", "畫新矩形"])
    selected_label = st.radio("標註類別:", list(LABEL_COLORS.keys()))
    stroke_color = LABEL_COLORS[selected_label]
    st.write(f"目前顏色: <span style='color:{stroke_color}'>██</span> ({selected_label})", unsafe_allow_html=True)
    st.divider()
    st.markdown("""**操作說明:**\n1. **移動/編輯**: 點選、移動、縮放現有標註框。\n2. **畫新矩形**: 先選好上方類別，再畫出新的標註框。\n3. **刪除**: 點選一個標註框後，按下鍵盤上的 `Delete` 鍵。\n4. **儲存**: 完成後點擊右方的儲存按鈕。""")

with col2:
    st.info(f"進度: {current_index + 1} / {total_files} | 目前影像: {current_image_name}")
    try:
        image_path = os.path.join(ORIGINAL_IMAGE_DIR, current_image_name)
        bg_image_original = Image.open(image_path)
        
        # --- 【主要修正點】明確地縮放圖片 ---
        # 1. 計算縮放比例與畫布的新高度
        scaling_ratio = CANVAS_DISPLAY_WIDTH / bg_image_original.width
        display_height = int(bg_image_original.height * scaling_ratio)
        
        # 2. 建立一個縮放後的圖片物件
        bg_image_resized = bg_image_original.resize((CANVAS_DISPLAY_WIDTH, display_height))
        
        model_predictions = load_yolo_predictions(current_image_name, bg_image_original.width, bg_image_original.height, CLASS_MAP)
        initial_drawing, source = load_initial_rects(current_image_name, gsheet_df, model_predictions, LABEL_COLORS, scaling_ratio)
        
        # 3. 將【縮放後】的圖片作為背景傳入畫布
        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color=stroke_color,
            background_image=bg_image_resized, # <-- 使用縮放後的圖片
            update_streamlit=True,
            height=display_height,
            width=CANVAS_DISPLAY_WIDTH,
            drawing_mode=drawing_mode,
            initial_drawing=initial_drawing,
            key=f"canvas_{current_image_name}",
        )
    except FileNotFoundError:
        st.error(f"找不到背景圖片: {current_image_name}")
        canvas_result = None

with col3:
    # ... (右側欄位的程式碼與之前版本相同) ...
    st.subheader("目前標註結果")
    if canvas_result and canvas_result.json_data:
        display_df = convert_canvas_to_df(current_image_name, canvas_result.json_data, LABEL_COLORS, scaling_ratio)
        st.dataframe(display_df, use_container_width=True, height=300)
    else:
        st.write("畫布上沒有標註。")

    st.divider()
    st.write(f"初始標註來源: **{source}**")
    
    if st.button("儲存本張標註", type="primary", use_container_width=True):
        if canvas_result and canvas_result.json_data:
            with st.spinner("正在儲存結果至 Google Sheets..."):
                final_df = convert_canvas_to_df(current_image_name, canvas_result.json_data, LABEL_COLORS, scaling_ratio)
                all_gsheet_data = conn.read(worksheet="Sheet1_BBOX", ttl=0).dropna(how='all')
                filtered_data = all_gsheet_data[all_gsheet_data['影像檔名 (Filename)'] != current_image_name]
                updated_gsheet_data = pd.concat([filtered_data, final_df], ignore_index=True)
                conn.update(worksheet="Sheet1_BBOX", data=updated_gsheet_data)
                st.success(f"影像 {current_image_name} 的標註已儲存！")
        else:
            st.warning("畫布上沒有可儲存的標註。")
    
    st.divider()

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("上一張", use_container_width=True):
            if st.session_state.current_index > 0:
                st.session_state.current_index -= 1
                st.rerun()
    with nav_cols[1]:
        if st.button("下一張", use_container_width=True):
            if st.session_state.current_index < total_files - 1:
                st.session_state.current_index += 1
                st.rerun()