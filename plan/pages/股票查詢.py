# 股票查詢.py
# 功能：讀取主頁寫入的查詢隊列（query_queue），對每檔股票抓取即時價格並計算持有市值，
#       依市場（region）分表顯示，每表計算總市值，並在每筆顯示該筆佔該市場總市值的百分比。
#
# 使用說明：
# 1. 與 app.py 放在同一個資料夾，且兩者共用同一個 SQLite 檔案（預設為 portfolio.db）。
# 2. 在 app.py 按下「將整個清單送去股票查詢」會把資料寫入 query_queue 表，
#    然後到此頁面重新整理即可看到查詢結果。
# 3. 需要安裝套件：streamlit, yfinance, pandas
#    pip install streamlit yfinance pandas

import streamlit as st
import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
import altair as alt
import matplotlib.pyplot as plt

# -------------------------
# 頁面設定
# -------------------------
st.set_page_config(page_title="股票查詢", page_icon="🔎", layout="wide")
st.title("🔎 股票查詢與持有市值（依市場分表）")

# -------------------------
# 與 app.py 共用的資料庫連線
# -------------------------
# 假設 app.py 與此檔案共用同一個 SQLite 檔案（例如 portfolio.db）
conn = sqlite3.connect("portfolio.db", check_same_thread=False)
c = conn.cursor()

# -------------------------
# 讀取查詢隊列（query_queue）
# -------------------------
def read_query_queue():
    """
    從 query_queue 表讀取要查詢的清單。
    若表不存在或為空，回傳空 list。
    每筆為 dict: {"symbol":..., "shares":..., "region":...}
    """
    try:
        c.execute("SELECT symbol, shares, region FROM query_queue ORDER BY id")
        rows = c.fetchall()
        return [{"symbol": r[0], "shares": r[1], "region": r[2] or ""} for r in rows]
    except Exception:
        return []

# -------------------------
# 抓取單檔價格（快取）
# -------------------------
@st.cache_data(ttl=60)
def fetch_price(symbol: str):
    """
    使用 yfinance 抓取單檔價格與前收。
    回傳 dict: {"price": float or None, "previous": float or None}
    若抓取失敗，price 為 None。
    ttl=60 秒快取，避免短時間內重複請求。
    """
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
        # 若 info 沒有價格，使用 history 做 fallback
        if price is None:
            hist = t.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None
        return {"price": price, "previous": prev}
    except Exception:
        return {"price": None, "previous": None}

# -------------------------
# 主流程：讀取 queue 並逐檔查詢
# -------------------------
queue = read_query_queue()

if not queue:
    st.info("查詢隊列為空。請在主頁（app.py）按「將整個清單送去股票查詢」後再回到此頁。")
else:
    st.markdown(f"**查詢時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
    results = []
    total_value_all = 0.0   # 全部市場總市值
    missing = []

    # 逐檔查詢並計算持有市值
    for item in queue:
        symbol = item.get("symbol")
        shares = item.get("shares") or 0
        region = item.get("region") or "未知"   # 若沒有 region，標為 "未知"
        price_info = fetch_price(symbol)
        price = price_info.get("price")
        if price is None:
            missing.append(symbol)
            market_value = None
        else:
            market_value = price * shares
            total_value_all += market_value

        results.append({
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "market_value": market_value,
            "region": region
        })

    # 轉成 DataFrame 方便處理
    df = pd.DataFrame(results)

    # 若 df 為空（理論上不會），顯示提示
    if df.empty:
        st.info("查詢結果為空。")
    else:
        # -------------------------
        # 依 region 分組計算每個市場的總市值
        # -------------------------
        # 先把 None 的 market_value 視為 0 做 groupby 計算（但顯示時仍保留 N/A）
        df_for_group = df.copy()
        df_for_group["market_value_filled"] = df_for_group["market_value"].fillna(0.0)

        # groupby 計算每個 region 的總市值
        region_totals = df_for_group.groupby("region", dropna=False)["market_value_filled"].sum().to_dict()
        # region_totals 範例: {"台股 .TW": 123456.0, "美股": 98765.0, ...}

        # -------------------------
        # 在原 DataFrame 中加入「佔該市場百分比」欄位
        # -------------------------
        def compute_pct(row):
            mv = row["market_value"]
            reg = row["region"]
            total = region_totals.get(reg, 0.0)
            if mv is None or total == 0:
                return None
            return mv / total * 100.0

        df["pct_of_region"] = df.apply(compute_pct, axis=1)

        # -------------------------
        # 針對每個 region 顯示一個獨立表格與小計
        # -------------------------
        st.markdown("## 依市場分表（每表顯示該市場內各檔持有市值與佔比）")

        # 依 region 排序顯示（可改為自訂順序）
        for region, total in region_totals.items():
            st.markdown(f"### 市場：**{region}** 　｜　市場總持有市值：**{total:,.2f}**")
            # --- 在 for region, total in region_totals.items(): 迴圈內，標題之後插入以下程式 ---
            # 取出該 region 的 rows（與原本相同）
            df_region = df[df["region"] == region].copy()

            # 準備繪圖用的資料：把 None 的 market_value 視為 0（但顯示時仍保留 N/A）
            plot_df = df_region.copy()
            plot_df["market_value_filled"] = plot_df["market_value"].fillna(0.0)

            # 若該市場所有市值皆為 0（或沒有可用價格），顯示提示並跳過餅圖
            if plot_df["market_value_filled"].sum() == 0:
                st.info(f"市場 {region} 無可用持有市值資料，無法繪製餅形圖。")
            else:
                # 建立顯示用的欄位：代號與市值（數值型）
                pie_df = plot_df[["symbol", "market_value_filled"]].copy()
                pie_df = pie_df.rename(columns={"symbol": "代號", "market_value_filled": "持有市值"})

                # --- Altair 互動餅圖（首選） ---
                try:
                    # 計算百分比欄位（Altair 顯示 tooltip）
                    pie_df["pct"] = pie_df["持有市值"] / pie_df["持有市值"].sum() * 100.0
                    chart = alt.Chart(pie_df).mark_arc(innerRadius=40).encode(
                        theta=alt.Theta(field="持有市值", type="quantitative"),
                        color=alt.Color(field="代號", type="nominal", legend=alt.Legend(title="代號")),
                        tooltip=[alt.Tooltip("代號:N"), alt.Tooltip("持有市值:Q", format=",.2f"), alt.Tooltip("pct:Q", format=".2f")]
                    ).properties(width=350, height=300)
                    st.altair_chart(chart, use_container_width=False)
                except Exception:
                    # --- Matplotlib 備援餅圖 ---
                    fig, ax = plt.subplots(figsize=(4, 4))
                    labels = pie_df["代號"].tolist()
                    sizes = pie_df["持有市值"].tolist()
                    # autopct 顯示百分比，若數量多會自動縮短標籤
                    ax.pie(sizes, labels=labels, autopct=lambda p: f'{p:.2f}%' if p > 0 else '', startangle=90)
                    ax.axis('equal')  # 圓形
                    st.pyplot(fig)
                    
            # 取出該 region 的 rows，並格式化顯示欄位
            df_region = df[df["region"] == region].copy()

            # 建顯示用欄位（中文）
            df_region_display = df_region.copy()
            # 格式化 price 與 market_value 與 pct_of_region
            df_region_display["price"] = df_region_display["price"].apply(lambda x: f"{x:,.2f}" if x is not None else "N/A")
            df_region_display["market_value"] = df_region_display["market_value"].apply(lambda x: f"{x:,.2f}" if x is not None else "N/A")
            df_region_display["pct_of_region"] = df_region_display["pct_of_region"].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")

            # 重新命名欄位為中文並指定顯示順序
            df_region_display = df_region_display.rename(columns={
                "symbol": "代號",
                "shares": "持股數",
                "price": "單股價格",
                "market_value": "持有市值",
                "pct_of_region": "佔該市場總市值比例",
                "region": "市場"
            })[["代號", "持股數", "單股價格", "持有市值", "佔該市場總市值比例"]]

            # 顯示表格
            st.dataframe(df_region_display, use_container_width=True)

            # 提供該市場的下載按鈕（CSV，中文欄位）
            csv_region = df_region.copy()
            csv_region["price"] = csv_region["price"].apply(lambda x: f"{x:.6f}" if x is not None else "")
            csv_region["market_value"] = csv_region["market_value"].apply(lambda x: f"{x:.6f}" if x is not None else "")
            csv_region["pct_of_region"] = csv_region["pct_of_region"].apply(lambda x: f"{x:.6f}" if x is not None else "")
            csv_region = csv_region.rename(columns={
                "symbol": "代號",
                "shares": "持股數",
                "price": "單股價格",
                "market_value": "持有市值",
                "pct_of_region": "佔該市場總市值比例",
                "region": "市場"
            })
            csv_text_region = csv_region.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label=f"⬇️ 下載 {region} 查詢結果 CSV",
                data=csv_text_region,
                file_name=f"查詢結果_{region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

            st.markdown("---")

        # -------------------------
        # 顯示整體總市值（所有市場合計）
        # -------------------------
        st.markdown("## 全部市場總覽")
        # st.markdown(f"**全部市場總持有市值：{total_value_all:,.2f}**")

        # 顯示每個市場的小計（表格形式）
        region_summary = pd.DataFrame([
            {"市場": reg, "市場總持有市值": val} for reg, val in region_totals.items()
        ])
        # 格式化數值
        region_summary["市場總持有市值"] = region_summary["市場總持有市值"].apply(lambda x: f"{x:,.2f}")
        st.dataframe(region_summary, use_container_width=True)

        # -------------------------
        # 下載整體查詢結果（含 region 與百分比）
        # -------------------------
        # 產生 CSV（中文欄位）
        csv_all = df.copy()
        csv_all["price"] = csv_all["price"].apply(lambda x: f"{x:.6f}" if x is not None else "")
        csv_all["market_value"] = csv_all["market_value"].apply(lambda x: f"{x:.6f}" if x is not None else "")
        csv_all["pct_of_region"] = csv_all["pct_of_region"].apply(lambda x: f"{x:.6f}" if x is not None else "")
        csv_all = csv_all.rename(columns={
            "symbol": "代號",
            "shares": "持股數",
            "price": "單股價格",
            "market_value": "持有市值",
            "pct_of_region": "佔該市場總市值比例",
            "region": "市場"
        })
        csv_text_all = csv_all.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ 下載全部查詢結果 CSV（含市場與佔比）",
            data=csv_text_all,
            file_name=f"查詢結果_全部_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    # 顯示缺失清單（中文提示）
    if missing:
        st.warning(f"以下代號無法取得價格，請確認代號或稍後重試：{', '.join(missing)}")
