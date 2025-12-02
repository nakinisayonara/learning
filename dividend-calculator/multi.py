# Yahoo Finance 股價與股息資料
import yfinance as yf
# 股息記錄表格（時間序列 -> 表格）
import pandas as pd
# 用來繪製股息收入圖表
import matplotlib.pyplot as plt
from matplotlib import rcParams
import numpy as np
import matplotlib.dates as mdates

# 設定全域字型，支援中文
rcParams['font.sans-serif'] = ['Microsoft YaHei']
# 避免負號顯示成方塊
rcParams['axes.unicode_minus'] = False

# 地區字典
region_suffix ={
    "TW": ".TW", #台灣
    "HK": ".HK", #香港
    "US": "", #美國
    "JP": ".T", #日本
    "SH": ".SS", #上海
    "SZ": ".SZ", #深圳
    "UK": ".L", #英國
    "DE": ".DE", #德國
    "CA": ".TO", #加拿大
    "AU": ".AX" #澳洲
}

# 對應幣別（用來做港幣換算）
region_CCY = {
    "TW": "TWD",
    "HK": "HKD",
    "US": "USD",
    "JP": "JPY",
    "SH": "CNY",
    "UK": "GBP",
    "DE": "EUR",
    "CA": "CAD",
    "AU": "AUD"
}

# 使用者輸入股票清單
symbols_input = input("請輸入股票代號（用逗號分隔，例如 2330.TW, 0005.HK, AAPL）：")
symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]

# 使用者輸入持有股數
shares = int(input("請輸入持有股數（每檔股票相同股數）：").strip())

# 即時匯率轉換器
# 判斷股票屬於哪個市場
def infer_region(ticker: str) -> str:
    """根據股票代號後綴推斷市場"""
    for region, suffix in region_suffix.items():
        if suffix and ticker.endswith(suffix):
            return region
    # 無後綴預設美股
    return "US"

# 找出該市場的類別
def get_currency(region: str) -> str:
    """依市場回傳幣別"""
    return region_CCY.get(region, "USD")

def get_fx_rate(base: str, quote: str = "HKD") -> float:
    """
    使用yfinance抓取匯率,例如 USDHKD=X
    base: 原始幣別
    quote:目標幣別(預設HKD)
    """

    if base == quote:
        return 1.0
    ticker = f"{base}{quote}=X"
    fx = yf.Ticker(ticker)
    hist = fx.history(period="1d")
    if not hist.empty:
        return float(hist["Close"].iloc[-1])
    else:
        # 抓不到回傳1.0
        return 1.0


# 存放每檔股票的計算結果
results = []
detail_tables = {}

# 逐一處理每檔股票
for stock_symbol in symbols:
    # 判斷市場
    region = infer_region(stock_symbol)
    # 判斷幣別
    ccy = get_currency(region)

    stock = yf.Ticker(stock_symbol)

    # 取得股價（先嘗試info.currentPrice，若無則用最近收盤價）
    price = stock.info.get("currentPrice")
    if price is None:
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist["Close"][-1])

    # 取得股息紀錄
    dividends = stock.dividends # 股息歷史記錄
    if not dividends.empty:
        # 最近一次派息日期
        end_date = dividends.index.max()
        # 最近一次派息往回推365天
        start_date = end_date - pd.DateOffset(days=365)
        # 取近一年内股息紀錄
        mask = (dividends.index > start_date) & (dividends.index <= end_date)
        recent_dividends = dividends[mask]
        # 近12個月的股息總額
        trailing_12m_div = float(recent_dividends.sum())
    else:
        recent_dividends = pd.Series(dtype="float64")
        trailing_12m_div = 0.0

    # 計算股息率與收入
    if (price is not None) and (trailing_12m_div > 0):
        # 年度股息收入
        annual_income_local = shares * trailing_12m_div
        # 月度股息收入
        monthly_income_local = annual_income_local / 12
        # 股息率
        dividends_yield = trailing_12m_div / price

        # 即時匯率轉換 -> 港幣
        rate = get_fx_rate(ccy, "HKD")
        annual_income_hkd = annual_income_local * rate
        monthly_income_hkd = monthly_income_local * rate

        # 匯率敏感度分析（+—5%）
        # 港幣不變
        if ccy == "HKD":
            annual_income_hkd_up = annual_income_hkd
            annual_income_hkd_down = annual_income_hkd
        else:
            annual_income_hkd_up = annual_income_hkd * 1.05
            annual_income_hkd_down = annual_income_hkd * 0.95

        # 股息明細表
        if not recent_dividends.empty:
            div_table = recent_dividends.to_frame(name="每股股息").reset_index()
            div_table.rename(columns={"Date": "派息日期"}, inplace=True)
            div_table["每股股息"] = div_table["每股股息"].round(6)
            div_table["持有股數"] = shares
            div_table["本幣收入"] = (div_table["每股股息"] * shares).round(4)
            div_table["HKD收入"] = (div_table["本幣收入"] * rate).round(4)
            detail_tables[stock_symbol] = div_table

        # 股息穩定度指標：近36個月
        div36 = dividends[-36:]
        if not div36.empty:
            # 股息標準差
            std_dev = np.std(div36.values)
            growth_rate = (div36.values[-1] / div36.values[0] - 1) * 100 if div36.values[0] > 0 else None
        else:
            std_dev, growth_rate = None, None

        results.append({
            "股票": stock_symbol,
            "市場": region,
            "幣別": ccy,
            "股價": round(price, 4),
            "近12月每月股息": round(trailing_12m_div, 6),
            "股息率(%)": round(dividends_yield * 100, 2),
            "年度股息(HKD)": round(annual_income_hkd, 2),
            "月度股息(HKD)": round(monthly_income_hkd, 2),
            "年度股息(HKD)+5%匯率": round(annual_income_hkd_up, 2),
            "年度股息(HKD)-5%匯率": round(annual_income_hkd_down, 2),
            "股息標準差": round(std_dev, 4) if std_dev is not None else None,
            "股息成長率(%)": round(growth_rate, 2) if growth_rate is not None else None
        })
    else:
        results.append({
            "股票": stock_symbol,
            "市場": region,
            "幣別": ccy,
            "股價": round(price, 4) if price is not None else None,
            "近12月每月股息": round(trailing_12m_div, 6),
            "股息率(%)": None,
            "年度股息(HKD)": None,
            "月度股息(HKD)": None
        })    

# 輸出表格
df = pd.DataFrame(results)
print("\n=== 多股票比較表（已換算為港幣 HKD，含匯率敏感度分析 & 股息穩定度指標） ===")
print(df.to_string(index=False))

for sym, tbl in detail_tables.items():
    print(f"\n--- {sym}近12個月派息明細(本幣 & HKD) ---")
    print(tbl.to_string(index=False))

# 視覺化：年度股息收入比較
# 刪除空值
plot_df = df.dropna(subset=["年度股息(HKD)"])
# 檢查plot_df是否為空
if not plot_df.empty:
    plt.figure(figsize=(10,6))
    plt.bar(plot_df["股票"], plot_df["年度股息(HKD)"], color="skyblue", label="現行匯率")
    plt.bar(plot_df["股票"], plot_df["年度股息(HKD)+5%匯率"], color="lightgreen", alpha=0.5, label="匯率升值 5%")
    plt.bar(plot_df["股票"], plot_df["年度股息(HKD)-5%匯率"], color="orange", alpha=0.8, label="匯率貶值 5%")
    plt.title("多股票年度股息比較(港幣HKD, 含匯率敏感度分析)")
    plt.xlabel("股票")
    plt.ylabel("年度股息(港幣HKD)")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.show()

# 36個月股息趨勢圖
for stock_symbol in symbols:
    stock = yf.Ticker(stock_symbol)
    dividends = stock.dividends
    if not dividends.empty:
        # 最近36個月
        recent_dividends = dividends[-36:]
        plt.figure(figsize=(10,5))
        plt.plot(recent_dividends.index, recent_dividends.values, marker="o", linestyle="-")
        plt.title(f"{stock_symbol} 近36個月股息趨勢")
        plt.xlabel("日期")
        plt.ylabel("每股股息(本幣)")
        plt.grid(True)
        # 設定日期格式顯示為年月
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        # 每3個月顯示一次刻度
        plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.show()