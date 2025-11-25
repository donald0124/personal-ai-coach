import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime
import json

# --- 1. 設定頁面與樣式 ---
st.set_page_config(page_title="VibeFit Coach", page_icon="🏋️", layout="wide")

# 隱藏 Streamlit 預設選單，讓介面更像 App
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {padding-top: 50px;}
    .stButton>button {width: 100%; border-radius: 20px; height: 3em;}
    div[data-testid="stExpander"] {background-color: #f0f2f6; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 2. 連結 Google 服務 (Gemini & Sheets) ---

# 讀取 Secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("請在 .streamlit/secrets.toml 設定 GEMINI_API_KEY")
    st.stop()

# 設定 Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 設定 Google Sheets (需在 secrets.toml 設定 gcp_service_account)
# 格式範例：
# [gcp_service_account]
# type = "service_account"
# project_id = "..."
# ... (整個 JSON 內容)
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 這裡假設你把 json 內容拆解放在 secrets 或者直接讀取 json 檔案
    # 為了方便 codespace 開發，建議直接把 json 內容貼到 st.secrets["gcp_service_account"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# 嘗試連線資料庫
try:
    client = get_google_sheet_client()
    # 請將 'Workout_Logs' 替換成你的 Google Sheet 名稱
    sheet = client.open("Workout_Logs").sheet1 
except Exception as e:
    st.warning(f"資料庫連線失敗 (僅開啟 AI 功能): {e}")
    sheet = None

# --- 3. AI 角色設定與初始化 ---

SYSTEM_PROMPT = """
(這裡保留原本的詳細 Prompt，為了版面簡潔我省略，請務必貼回原本那一大段 Role Definition)
...
重點補充：
當用戶透過「快速回報按鈕」傳送數據時（格式如：[紀錄] 深蹲 100kg 5下），
請直接記錄並給予簡短回饋，評估是否力竭，並建議下一組重量或休息時間。
不要每次都問器材，除非用戶是第一次開始對話。
"""

# 初始化 Session State
if "chat_session" not in st.session_state:
    model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=SYSTEM_PROMPT) # 建議用 1.5 flash 比較快且便宜
    st.session_state.chat_session = model.start_chat(history=[])

if "messages" not in st.session_state:
    st.session_state.messages = []

if "workout_start_time" not in st.session_state:
    st.session_state.workout_start_time = time.time()

if 'rest_end_time' not in st.session_state:
    st.session_state.rest_end_time = 0.0

# --- 4. 功能區塊：JavaScript 懸浮計時器 & 總時間 ---

# 計算總運動時間
total_elapsed = int(time.time() - st.session_state.workout_start_time)
total_mins, total_secs = divmod(total_elapsed, 60)

# 準備計時器的參數
now_ts = time.time()
rest_remaining = max(0, st.session_state.rest_end_time - now_ts)
end_time_str = f"{st.session_state.rest_end_time:.3f}"

# 注入 JS 程式碼 (修復版)
timer_html = f"""
<div id="sticky-header" style="
    position: fixed; top: 0; left: 0; width: 100%; background: #0E1117; 
    z-index: 9999; border-bottom: 2px solid #FF4B4B; padding: 10px 20px;
    display: flex; justify-content: space-between; align-items: center; color: white; font-family: monospace;">
    
    <div>
        <span style="font-size: 12px; color: #aaa;">總時間</span><br>
        <span id="total-timer" style="font-size: 18px; font-weight: bold;">{total_mins:02d}:{total_secs:02d}</span>
    </div>
    
    <div style="text-align: right;">
        <span style="font-size: 12px; color: #aaa;">組間休息</span><br>
        <span id="rest-timer" style="font-size: 24px; font-weight: bold; color: {'#00FF00' if rest_remaining == 0 else '#FF4B4B'};">
            --:--
        </span>
    </div>
</div>
<div style="height: 60px;"></div> <script>
(function() {{
    const restEndTime = {end_time_str};
    const startTime = {st.session_state.workout_start_time};
    
    function updateTimers() {{
        const now = Date.now() / 1000;
        
        // 1. 更新總時間
        const totalElapsed = Math.floor(now - startTime);
        const tMins = Math.floor(totalElapsed / 60);
        const tSecs = Math.floor(totalElapsed % 60);
        const tEl = document.getElementById("total-timer");
        if(tEl) tEl.innerText = 
            (tMins < 10 ? "0" : "") + tMins + ":" + (tSecs < 10 ? "0" : "") + tSecs;

        // 2. 更新倒數計時
        const rEl = document.getElementById("rest-timer");
        const remaining = restEndTime - now;
        
        if (remaining <= 0) {{
            if(rEl) {{
                rEl.innerText = "READY";
                rEl.style.color = "#00FF00";
            }}
        }} else {{
            const rMins = Math.floor(remaining / 60);
            const rSecs = Math.floor(remaining % 60);
            if(rEl) {{
                rEl.innerText = (rMins < 10 ? "0" : "") + rMins + ":" + (rSecs < 10 ? "0" : "") + rSecs;
                rEl.style.color = "#FF4B4B";
            }}
        }}
    }}
    
    setInterval(updateTimers, 1000);
    updateTimers();
}})();
</script>
"""
st.markdown(timer_html, unsafe_allow_html=True)

# --- 5. 核心介面 ---

st.title("🦴 OrthoFit Coach")

# --- 區塊 A: 快速輸入 (取代一直打字) ---
with st.expander("📝 快速記錄 & 啟動休息", expanded=True):
    with st.form("log_form"):
        c1, c2 = st.columns(2)
        with c1:
            exercise = st.selectbox("動作", ["深蹲", "硬舉", "臥推", "肩推", "划船", "分腿蹲", "跑步"])
            weight = st.number_input("重量 (kg)", min_value=0.0, step=2.5, value=0.0)
        with c2:
            reps = st.number_input("次數 / 時間", min_value=0, step=1, value=0)
            rpe = st.slider("自覺強度 (RPE)", 1, 10, 8)
        
        is_failure = st.checkbox("💀 力竭 (Failure)")
        
        # 休息時間選擇
        rest_select = st.select_slider("休息時間", options=[30, 60, 90, 120, 180, 240, 300], value=120)
        
        submitted = st.form_submit_button("✅ 記錄並發送給 AI")

    if submitted:
        # 1. 組裝訊息
        fail_str = "(力竭)" if is_failure else ""
        user_msg = f"[紀錄] {exercise} {weight}kg x {reps}下, RPE {rpe} {fail_str}。"
        
        # 2. 寫入 Google Sheet
        if sheet:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.append_row([timestamp, exercise, weight, reps, rpe, is_failure])
                st.toast(f"已儲存至資料庫: {exercise}", icon="💾")
            except Exception as e:
                st.error(f"寫入失敗: {e}")
        
        # 3. 設定倒數計時器
        st.session_state.rest_end_time = time.time() + rest_select
        
        # 4. 更新對話狀態，觸發 AI 回應
        st.session_state.messages.append({"role": "user", "content": user_msg})
        
        # 強制觸發 Rerun 以更新聊天室與計時器
        st.rerun()

# --- 區塊 B: 對話視窗 ---
st.subheader("💬 AI 教練回饋")

# 顯示歷史訊息
for msg in st.session_state.messages:
    role = "user" if msg["role"] == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(msg["content"])

# 處理 AI 回應 (當最後一條訊息是 user 時觸發)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("思考下一步建議..."):
            try:
                # 使用 chat_session 保持上下文
                user_content = st.session_state.messages[-1]["content"]
                response = st.session_state.chat_session.send_message(user_content)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"AI 連線錯誤: {e}")

# 傳統輸入框 (補救用，或問其他問題)
if prompt := st.chat_input("輸入其他問題 (例如: 膝蓋有點不舒服怎麼辦?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()