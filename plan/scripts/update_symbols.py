import pandas as pd
import json
from pathlib import Path
import requests   # 用 requests 抓取網頁內容，避免 SSL 驗證問題
import certifi    # 提供最新的憑證庫，確保 HTTPS 驗證正確

# 先找到專案根目錄，再指定到 pages/symbols.json
SYMBOLS_PATH = Path(__file__).parent.parent / "pages" / "symbols.json"

def get_twse_names():
    """
    抓取台灣證交所股票代號與名稱
    使用 requests.get() 搭配 certifi 來處理 SSL 驗證
    """
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        # 使用 certifi 的憑證庫驗證 SSL
        resp = requests.get(url, verify=certifi.where())
    except Exception:
        # 如果驗證失敗，暫時跳過 SSL 驗證（安全性較低，但能避免自簽憑證阻擋）
        resp = requests.get(url, verify=False)

    # 用 pandas 解析 HTML 表格
    dfs = pd.read_html(resp.text)
    df = dfs[0]
    df.columns = df.iloc[0]   # 第一列是欄位名稱
    df = df.drop(0)           # 刪掉欄位列
    df = df.rename(columns={"有價證券代號": "symbol", "有價證券名稱": "name"})
    return {f"{s}.TW": n for s, n in zip(df["symbol"], df["name"])}

def get_hkex_names():
    """
    抓取香港交易所股票代號與名稱
    """
    url = "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities?sc_lang=en"
    try:
        resp = requests.get(url, verify=certifi.where())
    except Exception:
        resp = requests.get(url, verify=False)

    dfs = pd.read_html(resp.text)
    df = dfs[0]
    df = df.rename(columns={"Stock Code": "symbol", "Name of Securities": "name"})
    return {f"{s}.HK": n for s, n in zip(df["symbol"].astype(str), df["name"])}

def get_us_names():
    """
    抓取美股 (NASDAQ + NYSE) 股票代號與名稱
    """
    try:
        nasdaq_url = "https://stockanalysis.com/list/nasdaq-stocks/"
        nyse_url = "https://stockanalysis.com/list/nyse-stocks/"

        resp_nasdaq = requests.get(nasdaq_url, verify=certifi.where())
        resp_nyse = requests.get(nyse_url, verify=certifi.where())

        dfs_nasdaq = pd.read_html(resp_nasdaq.text)
        dfs_nyse = pd.read_html(resp_nyse.text)

        df_nasdaq = dfs_nasdaq[0]
        df_nyse = dfs_nyse[0]

        nasdaq_map = dict(zip(df_nasdaq["Symbol"], df_nasdaq["Company Name"]))
        nyse_map = dict(zip(df_nyse["Symbol"], df_nyse["Company Name"]))

        return {**nasdaq_map, **nyse_map}
    except Exception:
        # 如果抓取失敗，回傳空字典
        return {}

def update_symbols(limit=None):
    """
    主流程：
    1. 抓取 TWSE、HKEX、美股清單
    2. 合併成一個字典
    3. 轉成 JSON 格式
    4. 寫入 symbols.json
    limit: 如果設定數字，則只取前 N 筆（方便測試）
    """
    try:
        twse_map = get_twse_names()
    except Exception as e:
        print("TWSE 抓取失敗:", e)
        twse_map = {}

    try:
        hkex_map = get_hkex_names()
    except Exception as e:
        print("HKEX 抓取失敗:", e)
        hkex_map = {}

    try:
        us_map = get_us_names()
    except Exception as e:
        print("美股抓取失敗:", e)
        us_map = {}

    # 合併所有市場的股票代號與名稱
    all_symbols = {**twse_map, **hkex_map, **us_map}

    # 如果有設定 limit，就只取前 N 筆（測試模式）
    if limit:
        all_symbols = dict(list(all_symbols.items())[:limit])

    # 轉成 JSON 格式
    data = [{"symbol": s, "name": n} for s, n in all_symbols.items()]

    # 寫入 symbols.json
    SYMBOLS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"更新完成，共 {len(data)} 筆股票代號寫入 {SYMBOLS_PATH}")

if __name__ == "__main__":
    # 正式模式：抓完整清單
    update_symbols()

    # 如果要測試，只抓前 10 筆，改成：
    # update_symbols(limit=10)
