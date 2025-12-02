# Yahoo Finance 股價與股息資料
import yfinance as yf
# 股息記錄表格（時間序列 -> 表格）
import pandas as pd
# 用來繪製股息收入圖表
import matplotlib.pyplot as plt
from matplotlib import rcParams

# 設定全域字型，支援中文
rcParams['font.sans-serif'] = ['Microsoft YaHei']
# 避免負號顯示成方塊
rcParams['axes.unicode_minus'] = False

# 地區字典
region_suffix ={
    "TW": ".TW", #台灣
    "HK": ".HK", #香港
    "US": "", #美國
    "JP": "T", #日本
    "SH": "SS", #上海
    "SZ": ".SZ", #深圳
    "UK": ".L", #英國
    "DE": ".DE", #德國
    "CA": ".TO", #加拿大
    "AU": ".AX" #澳洲
}

# 輸入股票代號和投資金額
# 股票代號需
symbol = input("請輸入股票代號：")
region = input("請輸入地區（TW/HK/US/JP/SH/SZ/UK/DE/CA/AU）：")
shares = int(input("請輸入持有股數：").strip())

# 自動補上後綴
stock_symbol = symbol + region_suffix.get(region, "")

# 取得股票資料
stock = yf.Ticker(stock_symbol)

# 嘗試取得股價與股息率
info = stock.info

# 股價
price = info.get("currentPrice")
if price is None:
    hist = stock.history(period="5d") # 最近五日的收盤價 
    if not hist.empty:
        price = float(hist["Close"][-1])
    else:
        price = None

# 取得股息記錄
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
    trailing_12m_div = 0.0

# 計算股息
if (price is not None) and (trailing_12m_div > 0):
    # 年股息收入 = 股數 x 近一年每股股息總額
    annual_dividend_income = shares * trailing_12m_div
    # 月股息收入 = 年度股息 / 12
    monthly_dividend_income = annual_dividend_income / 12
    # 股息率 近一年每股股息 / 股價
    dividend_yield = trailing_12m_div / price

    # 輸出股息記錄表
    print("\n=== 股息紀錄（近365天） ===")
    div_table = recent_dividends.to_frame(name="每股股息").reset_index()
    div_table.rename(columns={"Date": "派息日期"}, inplace = True)
    # 美觀處理：金額四捨五入
    div_table["每股股息"] = div_table["每股股息"].round(4)
    div_table["實際股息收入"] = (div_table["每股股息"] * shares).round(2)
    print(div_table.to_string(index=False))

    print("\n=== 計算結果 ===")
    print(f"股票：{stock_symbol}")
    print(f"股價：{round(price,4)}")
    print(f"近12個月每股股息總額：{round(trailing_12m_div, 4)}")
    print(f"年度股息率：{round(dividend_yield * 100, 2)}")
    print(f"持有股數：{shares}")
    print(f"每年股息：{round(annual_dividend_income, 2)}")
    print(f"每月平均股息：{round(monthly_dividend_income, 2)}")

    # 顯示最近一次除息日（如有）
    last_div_date = dividends.index.max().strftime("%Y-%m-%d") if not dividends.empty else "無資料"
    print(f"最近一次派息日期（近似除息）：{last_div_date}")

    # 視覺化：每次派息收入柱狀圖 + 年/月股息比較
    plt.figure(figsize=(10,5))

    # 子圖1：每次派息收入
    plt.subplot(1,2,1)
    plt.bar(div_table["派息日期"], div_table["實際股息收入"], color="skyblue")
    plt.title("近一年每次派息收入")
    plt.xlabel("派息日期")
    plt.ylabel("股息收入（元）")
    plt.xticks(rotation=45)

    # 子圖2：年度 vs 月度派息
    plt.subplot(1,2,2)
    plt.bar(["年度股息", "月度股息"], [annual_dividend_income, monthly_dividend_income], color=["lightgreen", "orange"])
    plt.title("年度 vs 月度股息收入")
    plt.ylabel("金額（元）")

    plt.tight_layout()
    plt.show()

else:
    print("\n=== 計算結果 ===")
    if price is None:
        print("股價資料不可用（可能為冷門或資料暫時缺失）。")
    if trailing_12m_div == 0:
        print("近12個月沒有派息記錄，或股息資料不可用。")
    print(f"股票：{stock_symbol}")