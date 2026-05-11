import streamlit as st
import joblib
import pandas as pd
import os
import re # 用於判斷網址格式

# 1. 載入模型
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

# --- 簡化版介面 ---
st.set_page_config(page_title="快速釣魚偵測器", page_icon="🔍")
st.title("🔍 快速釣魚網站偵測器")
st.write("只需輸入網址，AI 將為您評估風險。")

# 使用者只需輸入網址
url_input = st.text_input("請貼上網址 (URL):", placeholder="https://www.example.com")

# --- 自動特徵提取邏輯 ---
def extract_features(url):
    # 建立一個全為 0 的 30 維列表
    features = [0] * len(feature_names)
    
    # 這裡我們模擬自動抓取最重要的特徵
    # 1. 檢查 SSL (HTTPS)
    if url.startswith("https"):
        ssl_val = 1
    elif url.startswith("http"):
        ssl_val = -1
    else:
        ssl_val = 0
        
    # 2. 檢查網址長度 (模擬 dataset.csv 的邏輯)
    length_val = 1 if len(url) < 54 else (-1 if len(url) > 75 else 0)
    
    # 3. 檢查是否有前綴後綴 (例如包含 "-")
    prefix_val = -1 if "-" in url else 1

    # 將提取到的特徵填入對應位置 (根據 feature_names.pkl)
    if 'SSLfinal_State' in feature_names:
        features[feature_names.index('SSLfinal_State')] = ssl_val
    if 'URL_Length' in feature_names:
        features[feature_names.index('URL_Length')] = length_val
    if 'Prefix_Suffix' in feature_names:
        features[feature_names.index('Prefix_Suffix')] = prefix_val
        
    return features

# --- 點擊預測 ---
if st.button("開始檢查", type="primary"):
    if url_input:
        with st.spinner('AI 正在掃描網址特徵...'):
            # 1. 自動提取特徵
            features_list = extract_features(url_input)
            
            # 2. 餵給模型
            prediction = model.predict([features_list])
            
            # 3. 顯示結果
            st.subheader("偵測報告：")
            if prediction[0] == 1:
                st.success(f"✅ **安全無虞**：網址 '{url_input}' 暫未發現釣魚特徵。")
            else:
                st.error(f"🚨 **危險警告**：網址 '{url_input}' 具備釣魚網站的高度嫌疑，請勿輸入任何個人資料！")
                st.warning("偵測依據：SSL 證書缺失或網址結構異常。")
    else:
        st.warning("請先輸入網址。")

# 頁尾聲明
st.divider()
st.caption("本工具僅供教學研究，不保證 100% 準確率。數據來源：[Kaggle Phishing Website Dataset](https://www.kaggle.com/datasets/akashkr/phishing-website-dataset)")