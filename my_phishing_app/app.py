import streamlit as st
import joblib
import pandas as pd
import os

# 0. 網頁基本設定 (放在最前面)
@st.cache_resource
def load_model():
    # 1. 獲取當前 app.py 檔案所在的資料夾路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 拼接出模型與特徵清單的完整絕對路徑
    model_path = os.path.join(current_dir, 'phishing_rf_model.pkl')
    features_path = os.path.join(current_dir, 'feature_names.pkl')
    
    # 3. 使用完整路徑載入檔案
    model = joblib.load(model_path)
    features = joblib.load(features_path)
    
    return model, features

# 執行載入
model, feature_names = load_model()

# --- 側邊欄 (Sidebar) ---
with st.sidebar:
    st.header("📖 術語小辭典")
    st.info("""
    **1. SSL 狀態 (SSLfinal_State)**
    - **1**: 擁有可信賴的憑證（綠色鎖頭）。
    - **0**: 憑證異常或過期。
    - **-1**: 完全沒有憑證（極度危險）。

    **2. URL 錨點 (URL_of_Anchor)**
    - 指的是網頁中的超連結文字。
    - 釣魚網站常會隱藏真實連結，讓顯示文字與實際跳轉網址不符。
    """)
    st.write("---")
    st.write("💡 *提示：調整右側滑桿後點擊「開始偵測」看看 AI 的判斷結果。*")

# --- 主介面 ---
st.title("🛡️ AI 釣魚網站偵測實驗室")
st.write("這是一個基於機器學習（隨機森林）的資安技術展示工具。")

st.markdown("### 請調整網站特徵數值：")

# 加入 help 參數後，滑桿旁邊會出現一個問號氣泡
ssl_state = st.slider("SSL 狀態 (SSLfinal_State):", -1, 1, 0, 
                      help="判斷網站是否擁有合法的安全加密憑證 (HTTPS)")
url_anchor = st.slider("URL 錨點 (URL_of_Anchor):", -1, 1, 0, 
                       help="判斷網頁中的超連結是否指向可疑網域")

# 3. 當按下按鈕時，進行預測
if st.button("開始偵測", type="primary"): # 加入 type="primary" 會變成醒目的藍色按鈕
    # 建立與訓練時格式一致的數據
    input_data = [0] * len(feature_names) 
    
    if 'SSLfinal_State' in feature_names:
        input_data[feature_names.index('SSLfinal_State')] = ssl_state
    if 'URL_of_Anchor' in feature_names:
        input_data[feature_names.index('URL_of_Anchor')] = url_anchor

    # 進行推論 (Inference)
    prediction = model.predict([input_data])
    
    st.subheader("分析結果：")
    if prediction[0] == 1:
        st.success("✅ **這是正常網站！** 模型判斷該特徵組合風險較低。")
    else:
        st.error("🚨 **警告：這極可能是釣魚網站！** 模型偵測到惡意特徵模式。")

# --- 底部聲明 (Footer) ---
st.divider()
st.caption("""
**⚠️ 開發者聲明與免責聲明：**
- **數據來源**：本工具基於 [Kaggle Phishing Website Dataset](https://www.kaggle.com/datasets/akashkr/phishing-website-dataset) 進行訓練。
- **用途說明**：本專案僅供機器學習自學練習與技術展示使用，無任何商業用途。
- **準確度提示**：模型在測試集上的正確率約為 96%。但網路犯罪手法不斷演進，本工具結果僅供參考，不代表絕對的安全性保證。
""")