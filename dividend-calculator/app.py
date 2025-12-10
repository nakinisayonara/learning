import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
# 對函式結果做快取 避免重複抓匯率
from functools import lru_cache
# 控制日期刻度與格式
import matplotlib.dates as mdates

# 設定全域字型，支援中文
rcParams['font.sans-serif'] = ['Microsoft YaHei']
# 避免負號顯示成方塊
rcParams['axes.unicode_minus'] = False

### 匯率與市場邏輯模組

# 匯率轉換：抓取股票本幣對港幣的匯率
currency_map = {
    ".TW": "TWDHKD=X",
    # 港幣不需轉換
    ".HK": None,
    ".T": "JPYHKD=X",
    ".SZ": "CNYHKD=X",
    ".SS": "CNYHKD=X",   
    ".L": "GBPHKD=X",
    ".DE": "EURHKD=X",
    ".PA": "EURHKD=X",
    ".SI": "SGDHKD=X",
    ".AX": "AUDHKD=X",
    ".TO": "CADHKD=X",
}

def get_fx_symbol(ticker: str) -> str | None:
    """根據股票代號後綴，回傳對港幣的匯率代號；港股回傳 None；美股預設 USDHKD。"""
    # .strip() 清除空白
    # .upper() 轉大寫
    t = ticker.strip().upper()
    if t.endswith(".HK"):
        return None
    for suffix, fx in currency_map.items():
        if t.endswith(suffix):
            return fx
    # 美股（通常無後綴）→ USD→HKD
    return "USDHKD=X"

# Least-Recently-Used
# 相同匯率代號fx_symbol重複查詢時直接使用快取結果
@lru_cache(maxsize=64)
def fetch_latest_fx(fx_symbol: str) -> float:
    """抓最新匯率（過去一年最後一筆收盤價）。加快取避免重複請求。"""
    # 抓1年歷史
    hist = yf.Ticker(fx_symbol).history(period="1y")
    # 如果資料為空
    # raise ValueError 抛出異常提示
    if hist.empty:
        raise ValueError(f"匯率資料缺失：{fx_symbol}")
    # 取最後一筆當作最新匯率
    return float(hist["Close"][-1])

def convert_series_to_hkd(series_local: pd.Series, fx_symbol: str | None) -> pd.Series:
    """將本幣金額序列用最新匯率換算成港幣；港幣（None）則直接回傳。"""
    # None為港幣 直接回傳
    if fx_symbol is None:
        return series_local
    latest_fx = fetch_latest_fx(fx_symbol)
    return series_local * latest_fx

def annual_dividend_income_hkd(ticker: str, dividends_series: pd.Series, shares: int) -> pd.Series:
    """輸出「年度總現金股息（HKD）」序列：年度加總→乘股數→依市場兌港幣。"""
    # 取出日期索引年份
    # groupby(...).sum() 派息加總
    annual_div_local = dividends_series.groupby(dividends_series.index.year).sum()
    # 按股計算現金收入
    annual_income_local = annual_div_local * shares
    # 呼叫def get_fx_symbol
    fx_symbol = get_fx_symbol(ticker)
    # 呼叫def convert_series_to_hkd
    annual_income_hkd = convert_series_to_hkd(annual_income_local, fx_symbol)
    annual_income_hkd.name = "Annual Dividend Income (HKD)"
    return annual_income_hkd

# Streamlit 介面

# 初始化股票清單
if "symbols" not in st.session_state:
    st.session_state.symbols = []

st.set_page_config(page_title="多市場股息分析工具(HKD)", page_icon="💹", layout="wide")
st.title("多市場股息分析工具（港幣換算版）")

with st.sidebar:
    st.markdown("### 設定")
    new_symbol = st.text_input("輸入股票代號（例如 2330.TW, AAPL）")

    if st.button("+ 添加"):
        if new_symbol.strip():
            st.session_state.symbols.append(new_symbol.strip().upper())
            st.success(f"已添加：{new_symbol.strip().upper()}")

    if st.session_state.symbols:
        st.write("已添加股票：", st.session_state.symbols)
        if st.button("清空清單"):
            st.session_state.symbols = []
            st.info("股票清單已清空")

    shares = st.number_input("持股數量（每檔同一數量）", min_value=1, value=100)
    # checkbox 勾選
    show_trend = st.checkbox("顯示近 36 個月股息趨勢（本幣）", value=True)
    # selectbox 下拉選單
    interval_months = st.selectbox("X 軸刻度（月間隔）", options=[1, 3, 6, 12, 24], index=1)
    run = st.button("開始分析")

if run and st.session_state.symbols:
    # 拆分代號, 去空白
    tickers_list = st.session_state.symbols
    # {} dict 以字典資料類型收集結果
    results = {}
    st.markdown("### 分析結果")

    # 每股股息時間序列數據
    for t in tickers_list:
        try:
            div = yf.Ticker(t).dividends
        # 有異常
        except Exception as e:
            st.warning(f"{t} 下載股息資料失敗：{e}")
            continue

        # 無紀錄
        if div.empty:
            st.warning(f"{t} 沒有股息紀錄")
            continue

        # 年度股息收入（HKD）
        # 呼叫 def annual_dividend_income_hkd
        annual_hkd = annual_dividend_income_hkd(t, div, shares)
        # t=股票代號 作爲字典的key
        results[t] = annual_hkd

        # 年度柱狀圖（HKD）
        col1, col2 = st.columns([1, 1])
        with col1:
            fig, ax = plt.subplots(figsize=(7, 4))
            annual_hkd.plot(kind="bar", ax=ax, color="steelblue")
            ax.set_title(f"{t} 年度股息收入（HKD）")
            ax.set_ylabel("港幣")
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            plt.tight_layout()
            st.pyplot(fig)

        # 近 36 個月股息趨勢（本幣）
        if show_trend:
            recent = div[-36:]
            with col2:
                fig2, ax2 = plt.subplots(figsize=(7, 4))
                ax2.plot(recent.index, recent.values, marker="o", linestyle="-", color="orange")
                ax2.set_title(f"{t} 近 36 個月股息趨勢（每股，本幣）")
                ax2.set_xlabel("日期")
                ax2.set_ylabel("每股股息（本幣）")
                ax2.grid(True, linestyle="--", alpha=0.4)
                # 顯示年月 + 每 interval_months 個月一刻度
                ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
                ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=interval_months))
                # x刻度旋轉度數
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig2)

    # 比較總表（HKD）
    if results:
        df = pd.DataFrame(results)
        st.subheader("年度股息比較（HKD）")
        st.dataframe(df.style.format("{:,.0f}"))

        # 匯率敏感度（±5%）
        st.subheader("匯率敏感度（±5%）")
        delta = 0.05
        sens_low = df * (1 - delta)
        sens_high = df * (1 + delta)
        st.markdown("**說明:** 顯示在最新匯率基準下，匯率波動 ±5% 時的年度收入範圍。")
        st.write("下限（-5%）")
        st.dataframe(sens_low.style.format("{:,.0f}"))
        st.write("上限（+5%）")
        st.dataframe(sens_high.style.format("{:,.0f}"))

# 未觸發分析提示
else:
    st.info("請在左側輸入股票代號與持股數量，然後點擊「開始分析」。")