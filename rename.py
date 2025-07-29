# 說明：
# 用來增加影像名稱，將辨別標籤增加在影像原名稱前面，如 WLI_001.jpg -> polyp_WLI_001.jpg (標籤類別自行輸入文字)
#  --------------------------------------------------------------------------
# 如何執行：
# 1. 開啟 Anaconda Prompt
# 2. conda activate yolov8
# 3. cd C:\Users\julia\Desktop\LAB\yolov8\medical_review_system
# 4. python rename.py
# --------------------------------------------------------------------------


import os
import shutil
import tkinter as tk
from tkinter import filedialog

def rename_and_copy_images():
    """
    依序提示使用者選擇來源資料夾、輸入檔名前綴、選擇目標資料夾，
    然後將檔案加上前綴後複製到目標資料夾。
    """
    # 步驟 1: 初始化 Tkinter 並隱藏主視窗
    # 我們只需要檔案對話方塊，不需要顯示一個完整的 GUI 視窗
    root = tk.Tk()
    root.withdraw()

    # 步驟 2: 要求使用者選擇來源資料夾
    print("程式啟動：請選擇要讀取影像的來源資料夾...")
    source_dir = filedialog.askdirectory(title="請選擇來源資料夾")

    if not source_dir:
        print("操作已取消：未選擇來源資料夾，程式結束。")
        return

    print(f"已選擇來源資料夾: {source_dir}")

    # 步驟 3: 要求使用者輸入要增加的文字 (前綴)
    prefix = input("請輸入要加在檔名前面的文字，然後按下 Enter：")

    if not prefix.strip():
        print("操作已取消：未輸入任何文字，程式結束。")
        return

    # 步驟 4: 要求使用者選擇目標資料夾
    print("\n請選擇要儲存更名後檔案的目標資料夾...")
    dest_dir = filedialog.askdirectory(title="請選擇目標資料夾")

    if not dest_dir:
        print("操作已取消：未選擇目標資料夾，程式結束。")
        return

    print(f"已選擇目標資料夾: {dest_dir}")

    # 如果目標資料夾不存在，則自動建立
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"已自動建立目標資料夾: {dest_dir}")

    # 步驟 5: 執行檔案重新命名與複製
    try:
        processed_count = 0
        print("\n--- 開始處理檔案 ---")
        
        # 遍歷來源資料夾中的所有項目
        for filename in os.listdir(source_dir):
            source_file_path = os.path.join(source_dir, filename)

            # 確保處理的是檔案而不是子資料夾
            if os.path.isfile(source_file_path):
                # 建立新的檔案名稱
                new_filename = f"{prefix}_{filename}"
                
                # 建立完整的目標檔案路徑
                dest_file_path = os.path.join(dest_dir, new_filename)

                # 複製檔案並保留元數據 (如建立日期)
                shutil.copy2(source_file_path, dest_file_path)
                print(f"成功: {filename}  ->  {new_filename}")
                processed_count += 1

        if processed_count == 0:
            print("\n處理完成：但來源資料夾中沒有找到任何檔案。")
        else:
            print(f"\n--- 處理完成！ ---\n總共有 {processed_count} 個檔案被複製並重新命名至目標資料夾。")

    except Exception as e:
        print(f"\n處理過程中發生錯誤: {e}")

# 主程式入口點
if __name__ == "__main__":
    rename_and_copy_images()