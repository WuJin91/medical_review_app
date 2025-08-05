# --------------------------------------------------------------------------
# 醫療影像審核系統 by Streamlit (V11 - 介面佈局與影像縮放優化)
#
# 更新日誌:
# - 修正了因影像原始尺寸過大導致畫布無法渲染的問題。
# - 新增影像縮放邏輯：將所有影像縮放到固定寬度，並按比例換算標註座標。
# - 優化介面佈局：將所有控制按鈕（儲存、導覽）集中到右側欄，避免滾動。
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
CANVAS_DISPLAY_WIDTH = 800 # 【新增】設定畫布在介面上的固定顯示寬度 (像素)

# ... (check_password, hex_to_rgba, convert_canvas_to_df 等函數與之前版本相同，此處省略) ...
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

# --- 3. 核心繪圖與資料轉換函數 ---
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
                # 【修改】將畫布上的座標按比例換算回原始座標再儲存
                records.append({
                    "影像檔名 (Filename)": image_filename,
                    "類別 (Label)": label,
                    "x": int(obj['left'] / scaling_ratio),
                    "y": int(obj['top'] / scaling_ratio),
                    "width": int(obj['width'] / scaling_ratio),
                    "height": int(obj['height'] / scaling_ratio),
                    "審核時間 (Timestamp)": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                })
    return pd.DataFrame(records)

def load_yolo_predictions(image_filename, image_width, image_height, class_map):
    # ... (此函數內容與之前完全相同，為節省空間此處省略) ...
    predictions = []
    base_filename = os.path.splitext(image_filename)[0]
    label_path = os.path.join(LABEL_DIR, f"{base_filename}.txt")
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    class_index, x_center_norm, y_center_norm, width_norm, height_norm = map(float, parts)
                    abs_width = width_norm * image_width
                    abs_height = height_norm * image_height
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
            # 【修改】將讀取到的原始座標按比例縮小以適應畫布
            rects.append({
                "type": "rect", 
                "left": row['x'] * scaling_ratio, "top": row['y'] * scaling_ratio,
                "width": row['width'] * scaling_ratio, "height": row['height'] * scaling_ratio,
                "stroke": stroke_color, "strokeWidth": 2, "fill": hex_to_rgba(stroke_color)
            })
    elif model_predictions:
        source = "模型預測"
        for pred in model_predictions:
            label, box = pred['label'], pred['box']
            stroke_color = label_color_map.get(label, "#FFFFFF")
            # 【修改】將讀取到的原始座標按比例縮小以適應畫布
            rects.append({
                "type": "rect", 
                "left": box[0] * scaling_ratio, "top": box[1] * scaling_ratio,
                "width": box[2] * scaling_ratio, "height": box[3] * scaling_ratio,
                "stroke": stroke_color, "strokeWidth": 2, "fill": hex_to_rgba(stroke_color)
            })
    return {"objects": rects}, source

# --- Streamlit App 主體 ---
st.set_page_config(layout="wide", page_title="互動式影像標註系統")

if not check_password():
    st.stop()

st.title("互動式病兆標註介面")

CLASS_MAP = {0: "polyp", 1: "tumor"}
LABEL_COLORS = {"polyp": "#51FF00", "tumor": "#0000FF"}

# ... (GSheet 連接與影像列表讀取的程式碼與之前版本相同) ...
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    gsheet_df = conn.read(worksheet="Sheet1", ttl=5).dropna(how='all')
except Exception as e:
    st.error(f"無法連接或讀取 Google Sheets。錯誤：{e}")
    gsheet_df = pd.DataFrame()

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

# --- 主要介面佈局 ---
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

# --- 中間欄：畫布工作區 ---
with col2:
    st.info(f"進度: {current_index + 1} / {total_files} | 目前影像: {current_image_name}")
    try:
        image_path = os.path.join(ORIGINAL_IMAGE_DIR, current_image_name)
        bg_image = Image.open(image_path)
        
        # --- 【主要修改點】影像縮放與座標換算 ---
        # 1. 計算縮放比例與畫布的新高度
        scaling_ratio = CANVAS_DISPLAY_WIDTH / bg_image.width
        display_height = int(bg_image.height * scaling_ratio)
        
        # 2. 載入模型預測 (傳入原始尺寸)
        model_predictions = load_yolo_predictions(current_image_name, bg_image.width, bg_image.height, CLASS_MAP)
        
        # 3. 載入初始標註框 (傳入縮放比例)
        initial_drawing, source = load_initial_rects(current_image_name, gsheet_df, model_predictions, LABEL_COLORS, scaling_ratio)
        
        # 4. 建立畫布 (使用計算後的顯示尺寸)
        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color=stroke_color,
            background_image=bg_image, # Streamlit 1.31.0 會自動處理縮放
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

# --- 右側欄：資料與控制 ---
with col3:
    st.subheader("目前標註結果")
    
    if canvas_result and canvas_result.json_data:
        # 【修改】顯示時也需要換算回原始座標
        display_df = convert_canvas_to_df(current_image_name, canvas_result.json_data, LABEL_COLORS, scaling_ratio)
        st.dataframe(display_df, use_container_width=True, height=300)
    else:
        st.write("畫布上沒有標註。")

    st.divider()
    st.write(f"初始標註來源: **{source}**")
    
    # --- 【修改點】將所有控制按鈕移到此處 ---
    if st.button("儲存本張標註", type="primary", use_container_width=True):
        if canvas_result and canvas_result.json_data:
            with st.spinner("正在儲存結果至 Google Sheets..."):
                # 【修改】儲存時傳入縮放比例，以換算回原始座標
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