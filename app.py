import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import json

# --- 1. 設定與資料庫連線 ---
st.set_page_config(page_title="QuickFit Buttons", page_icon="⚡", layout="centered")

# 定義你的「訓練菜單」與「重量範圍」
# 格式： "動作名稱": [重量選項清單]
MENU_CONFIG = {
    # --- 下肢與核心 (Lower Body & Core) ---
    "深蹲 (Squat)": [40, 50, 55, 60, 65, 70, 75, 80, 85, 90],
    "硬舉 (Deadlift)": [60, 70, 80, 90, 100, 110, 120],
    "羅馬尼亞硬舉 (RDL)": [40, 50, 60, 70, 80, 90], 
    "保加利亞分腿蹲 (Bulgarian Split Squat)": [8, 10, 12.5, 15, 17.5, 20, 22.5], # 單手重量(kg)
    "農夫走路 (Farmer's Walk)": [16, 20, 24, 28, 32, 36, 40], # 單手重量(kg)
    "壺鈴擺盪 (Kettlebell Swing)": [12, 16, 20, 24, 28, 32],
    
    # --- 上肢推力與肩部 (Upper Body Push & Shoulder) ---
    "臥推 (Bench Press)": [30, 35, 40, 45, 50, 55, 60, 70],
    "肩推 (OHP)": [20, 25, 30, 35, 40, 45, 50],
    "三頭下壓 (Tricep Pushdown)": [15, 20, 25, 30, 35, 40, 45],

    # --- 上肢拉力與背部 (Upper Body Pull & Back) ---
    "單槓引體向上": [0],
    "滑輪下拉 (Lat Pulldown)": [25, 30, 35, 40, 45, 50, 55, 60],
    "啞鈴划船 (Row)": [12.5, 15, 17.5, 20, 22.5, 25, 30],
    "臉拉 (Face Pull)": [15, 20, 25, 30, 35],
    "二頭彎舉 (Curl)": [5, 7.5, 10, 12.5, 15],

    "其他": [] 
}

# 初始化 Session State
if "local_logs" not in st.session_state:
    st.session_state.local_logs = []
if "selected_exercise" not in st.session_state:
    st.session_state.selected_exercise = "深蹲 (Squat)" # 預設動作
if "selected_weight" not in st.session_state:
    st.session_state.selected_weight = 50.0 # 預設重量

# 連線 Google Sheets (保持原樣)
def get_sheet():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Workout_Logs").sheet1
    except Exception:
        return None

sheet = get_sheet()

# --- Helper Functions: 按鈕回呼函式 ---
def set_exercise(ex_name):
    st.session_state.selected_exercise = ex_name
    # 切換動作時，預設重量歸零或設為該動作的第一個選項
    weights = MENU_CONFIG[ex_name]
    if weights:
        st.session_state.selected_weight = float(weights[0])
    else:
        st.session_state.selected_weight = 0.0

def set_weight(w_val):
    st.session_state.selected_weight = float(w_val)

# --- 2. 介面設計 ---
st.title("⚡ QuickFit 極速紀錄")

# === A. 動作快選區 ===
st.caption("1️⃣ 選擇動作")
exercises = list(MENU_CONFIG.keys())
# 建立 4 欄的按鈕網格
cols = st.columns(4)
for i, ex in enumerate(exercises):
    with cols[i % 4]:
        # 依據是否被選中來改變按鈕樣式 (Streamlit 按鈕無法直接變色，但我們可以用 type="primary" 來標示)
        is_selected = (ex == st.session_state.selected_exercise)
        st.button(
            ex.split()[0], # 按鈕上只顯示中文簡稱，比較整齊
            key=f"btn_ex_{i}",
            type="primary" if is_selected else "secondary",
            on_click=set_exercise,
            args=(ex,),
            use_container_width=True
        )

# === B. 重量快選區 (動態生成) ===
current_ex = st.session_state.selected_exercise
weight_options = MENU_CONFIG[current_ex]

if weight_options:
    st.caption(f"2️⃣ 選擇重量 (目前動作: {current_ex})")
    w_cols = st.columns(5) # 5 欄網格
    for i, w in enumerate(weight_options):
        with w_cols[i % 5]:
            is_w_selected = (float(w) == st.session_state.selected_weight)
            st.button(
                f"{w}",
                key=f"btn_w_{current_ex}_{w}", # Key 必須唯一
                type="primary" if is_w_selected else "secondary",
                on_click=set_weight,
                args=(w,),
                use_container_width=True
            )
else:
    st.caption("請直接在下方輸入重量")

st.divider()

# === C. 最終確認與送出表單 ===
st.caption("3️⃣ 確認與微調細節")

with st.form("final_check_form", clear_on_submit=False):
    c1, c2 = st.columns([2, 1])
    with c1:
        # 這裡的 value 會自動讀取剛剛按鈕點選後的 session_state
        # 如果選「其他」，允許使用者自己打字
        if current_ex == "其他":
             final_exercise = st.text_input("輸入動作名稱", value="")
        else:
             # 這裡用 text_input 設為 disabled 讓它顯示但不能改，或者允許改都可以
             final_exercise = st.text_input("動作", value=current_ex)
             
    with c2:
        # 允許手動微調重量 (例如想做 62.5kg，但按鈕只有 60 和 65)
        final_weight = st.number_input(
            "重量 (kg)", 
            value=st.session_state.selected_weight, 
            step=1.25
        )

    c3, c4, c5 = st.columns(3)
    with c3:
        final_reps = st.number_input("次數", value=8, step=1)
    with c4:
        final_rpe = st.number_input("RPE (強度)", value=8, min_value=1, max_value=10)
    with c5:
        final_failure = st.checkbox("💀 力竭", value=False)

    submit_btn = st.form_submit_button("✅ 確認紀錄", type="primary", use_container_width=True)

# === D. 處理送出邏輯 ===
if submit_btn:
    if not final_exercise:
        st.error("動作名稱不能為空")
    else:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_today = datetime.now().strftime("%Y-%m-%d")
        
        # 資料物件
        entry = {
            "Time": ts,
            "Date": date_today,
            "Exercise": final_exercise,
            "Weight": final_weight,
            "Reps": final_reps,
            "RPE": final_rpe,
            "Failure": "Yes" if final_failure else "No"
        }
        
        # 1. 存入 Session State (本地清單)
        st.session_state.local_logs.append(entry)
        
        # 2. 存入 Google Sheets
        if sheet:
            try:
                sheet.append_row(list(entry.values()))
                st.toast(f"已儲存: {final_exercise} {final_weight}kg", icon="☁️")
            except Exception as e:
                st.error(f"雲端錯誤: {e}")
        else:
             st.toast(f"已暫存 (無雲端): {final_exercise}", icon="💾")

# === E. 顯示結果與 RPE 說明 ===

# RPE 說明摺疊區
with st.expander("❓ RPE 是什麼？ (點擊展開說明)"):
    st.markdown("""
    **RPE (自覺強度量表) 1-10 分：**
    * **10**: 極限，完全做不動下一標準下 (力竭)。
    * **9**: 很重，大概還能勉強做 1 下。
    * **8**: 重，但還有保留，大概還能做 2 下。 (增肌甜蜜點)
    * **7**: 還算輕鬆，大概還能做 3 下。
    """)

# 顯示今日紀錄表格
if st.session_state.local_logs:
    st.subheader("📊 今日紀錄")
    df = pd.DataFrame(st.session_state.local_logs)
    # 只顯示重要欄位
    st.dataframe(df[["Exercise", "Weight", "Reps", "RPE"]], use_container_width=True)
    
    # JSON 輸出
    st.subheader("📋 JSON 匯出")
    json_str = json.dumps(st.session_state.local_logs, ensure_ascii=False, indent=2)
    st.code(json_str, language="json")
    
    if st.button("清除所有紀錄"):
        st.session_state.local_logs = []
        st.rerun()