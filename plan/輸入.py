import streamlit as st
import sqlite3
import time
import io
import csv
import json
from datetime import datetime
import html

def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        # 使用 st.query_params 作為 fallback，賦值新 dict 以觸發 rerun
        st.query_params = {"_rerun": int(time.time())}

# 頁面設定
st.set_page_config(page_title="股票清單管理", page_icon="📈", layout="wide")
st.title("股票清單管理（中文介面）")

# SQLite 連線與資料表建立
conn = sqlite3.connect("portfolio.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    region TEXT NOT NULL
)
""")
conn.commit()

# 啟動時從資料庫載入到 session_state
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []
    c.execute("SELECT id, symbol, shares, region FROM portfolio ORDER BY id")
    rows = c.fetchall()
    for r in rows:
        st.session_state.portfolio.append({
            "id": r[0],
            "symbol": r[1],
            "shares": r[2],
            "region": r[3]
        })

# 用來記錄目前正在編輯的項目 id 與暫存編輯值
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "edit_shares" not in st.session_state:
    st.session_state.edit_shares = 0

# 輸入區塊（三欄）
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    new_symbol = st.text_input("股票代號")

with col2:
    region = st.radio("選擇市場", [
        "台股",
        "港股",
        "美股",
        "日股",
        "中國A股-深圳",
        "中國A股-上海",
        "英股",
        "德股",
        "法股",
        "新加坡",
        "澳洲",
        "加拿大",
    ])

with col3:
    new_shares = st.number_input("持股數量", min_value=1, value=100, step=1)

# 後綴對應表
suffix_map = {
    "台股": ".TW",
    "港股": ".HK",
    "美股": "",
    "日股": ".T",
    "中國A股-深圳": ".SZ",
    "中國A股-上海": ".SS",
    "英股": ".L",
    "德股": ".DE",
    "法股": ".PA",
    "新加坡": ".SI",
    "澳洲": ".AX",
    "加拿大": ".TO",
}

# 添加函式
def add_item():
    symbol_raw = new_symbol.strip()
    if not symbol_raw:
        st.warning("請輸入股票代號")
        return

    suffix = suffix_map.get(region, "")
    full_symbol = symbol_raw.upper() + suffix

    # 重複檢查
    exists = any(item["symbol"] == full_symbol for item in st.session_state.portfolio)
    if exists:
        st.warning(f"{full_symbol} 已在清單中，若要更新持股請先刪除再重新加入")
        return

    # 寫入 SQLite
    c.execute("INSERT INTO portfolio (symbol, shares, region) VALUES (?, ?, ?)",
              (full_symbol, int(new_shares), region))
    conn.commit()
    new_id = c.lastrowid

    # 同步寫入 session_state
    st.session_state.portfolio.append({
        "id": new_id,
        "symbol": full_symbol,
        "shares": int(new_shares),
        "region": region
    })
    st.success(f"已添加：{full_symbol}，持股 {new_shares} 股")

if st.button("+ 新增到清單"):
    add_item()

st.markdown("---")

# ---------- 新增：把整個清單寫入查詢隊列（放在 app.py，DB 已連線後） ----------
def push_portfolio_to_query_queue():
    """
    將目前 session_state.portfolio 的內容寫入資料庫的 query_queue 表。
    若表不存在會建立。每次呼叫會先清空舊的 queue，再寫入最新清單。
    """
    # 建表（若不存在）
    c.execute("""
    CREATE TABLE IF NOT EXISTS query_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        shares INTEGER NOT NULL,
        region TEXT
    )
    """)
    conn.commit()

    # 清空舊的 queue
    c.execute("DELETE FROM query_queue")
    conn.commit()

    # 寫入新的 queue
    for p in st.session_state.portfolio:
        c.execute("INSERT INTO query_queue (symbol, shares, region) VALUES (?, ?, ?)",
                  (p["symbol"], p["shares"], p.get("region", "")))
    conn.commit()

# 在 UI 放一個按鈕讓使用者把整個清單送去查詢
if st.button("🔁 將整個清單送去股票查詢"):
    if not st.session_state.portfolio:
        st.warning("清單為空，無法送出查詢。")
    else:
        push_portfolio_to_query_queue()
        st.success("已將清單寫入查詢隊列。請切換到「股票查詢」頁面查看結果。")

# 顯示清單（中文欄位標題）
st.markdown("### 已加入的股票清單")
if st.session_state.portfolio:
    display_rows = []
    for p in st.session_state.portfolio:
        display_rows.append({
            "編號": p["id"],
            "代號": p["symbol"],
            "持股數": p["shares"],
            "市場": p["region"]
        })
    st.table(display_rows)

    # 單筆操作區塊 包含編輯與刪除
    st.markdown("#### 編輯或刪除項目")
    for item in list(st.session_state.portfolio):
        col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
        with col_a:
            st.write(f"**{item['symbol']}**  持股 {item['shares']}  市場 {item['region']}")
        with col_b:
            # 編輯按鈕：設定 edit_id 與預設編輯值
            if st.button("編輯持股數", key=f"edit_{item['id']}"):
                st.session_state.edit_id = item["id"]
                st.session_state.edit_shares = item["shares"]
                safe_rerun()
        with col_c:
            # 刪除按鈕
            if st.button("刪除", key=f"del_{item['id']}"):
                c.execute("DELETE FROM portfolio WHERE id = ?", (item["id"],))
                conn.commit()
                st.session_state.portfolio = [p for p in st.session_state.portfolio if p["id"] != item["id"]]
                safe_rerun()
        with col_d:
            st.write("")

    # 若有正在編輯的項目，顯示編輯表單
    if st.session_state.edit_id is not None:
        st.markdown("---")
        st.markdown("###編輯持股數")
        # 找到正在編輯的項目
        edit_item = next((p for p in st.session_state.portfolio if p["id"] == st.session_state.edit_id), None)
        if edit_item:
            st.write(f"編輯項目  **{edit_item['symbol']}**  市場 {edit_item['region']}")
            # 顯示可編輯的數字欄位，預設為目前持股數
            new_value = st.number_input("新的持股數", min_value=1, value=int(st.session_state.edit_shares), step=1, key=f"edit_input_{edit_item['id']}")
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                if st.button("儲存變更", key=f"save_{edit_item['id']}"):
                    # 更新 SQLite
                    c.execute("UPDATE portfolio SET shares = ? WHERE id = ?", (int(new_value), edit_item["id"]))
                    conn.commit()
                    # 更新 session_state
                    for p in st.session_state.portfolio:
                        if p["id"] == edit_item["id"]:
                            p["shares"] = int(new_value)
                            break
                    st.session_state.edit_id = None
                    st.session_state.edit_shares = 0
                    st.success("已更新持股數")
                    safe_rerun()
            with col_cancel:
                if st.button("取消", key=f"cancel_{edit_item['id']}"):
                    st.session_state.edit_id = None
                    st.session_state.edit_shares = 0
                    st.info("已取消編輯")
                    safe_rerun()
        else:
            # 若找不到該 id，清除編輯狀態
            st.session_state.edit_id = None
            st.session_state.edit_shares = 0
else:
    st.info("目前清單為空，請新增股票。")

st.markdown("---")

# ---------- 匯出 CSV ----------
def export_csv():
    # 從資料庫讀取最新資料，確保匯出為真實來源
    c.execute("SELECT id, symbol, shares, region FROM portfolio ORDER BY id")
    rows = c.fetchall()

    # 建立 CSV 內容（使用 in-memory buffer）
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    # 標頭（中文）
    writer.writerow(["編號", "代號", "持股數", "市場"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3]])

    buffer.seek(0)
    # 產生檔名
    filename = f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return filename, buffer.getvalue()

# ---------- 匯入 CSV ----------
# 修改：支援 mode 的匯入函式（替換原本的 import_csv）
def import_csv_with_mode(uploaded_file, mode="skip"):
    """
    mode:
      - "skip"     : 若衝突則略過（預設）
      - "overwrite": 若衝突則用匯入資料覆蓋現有（UPDATE）
      - "append"   : 不檢查衝突，全部 INSERT（可能造成重複）
    回傳 (added_count, updated_count, skipped_count)
    """
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        added = updated = skipped = 0

        # 建立現有索引（symbol+region -> item）
        existing_index = {f"{p['symbol'].strip()}||{p['region'].strip()}": p for p in st.session_state.portfolio}

        for row in reader:
            symbol = (row.get("代號") or row.get("symbol") or "").strip()
            shares_raw = row.get("持股數") or row.get("shares")
            region = (row.get("市場") or row.get("region") or "").strip()
            if not symbol or not shares_raw:
                skipped += 1
                continue
            try:
                shares_int = int(float(shares_raw))
            except Exception:
                skipped += 1
                continue

            key = f"{symbol}||{region}"
            existing = existing_index.get(key)

            if existing:
                if mode == "skip":
                    skipped += 1
                    continue
                elif mode == "overwrite":
                    # 更新 SQLite 與 session_state
                    c.execute("UPDATE portfolio SET shares = ?, region = ? WHERE id = ?", (shares_int, region, existing["id"]))
                    conn.commit()
                    # 更新 session_state 中的物件
                    for p in st.session_state.portfolio:
                        if p["id"] == existing["id"]:
                            p["shares"] = shares_int
                            p["region"] = region
                            break
                    updated += 1
                elif mode == "append":
                    # 仍然 INSERT（會造成重複）
                    c.execute("INSERT INTO portfolio (symbol, shares, region) VALUES (?, ?, ?)",
                              (symbol, shares_int, region))
                    conn.commit()
                    new_id = c.lastrowid
                    st.session_state.portfolio.append({"id": new_id, "symbol": symbol, "shares": shares_int, "region": region})
                    added += 1
            else:
                # 不存在則新增
                c.execute("INSERT INTO portfolio (symbol, shares, region) VALUES (?, ?, ?)",
                          (symbol, shares_int, region))
                conn.commit()
                new_id = c.lastrowid
                st.session_state.portfolio.append({"id": new_id, "symbol": symbol, "shares": shares_int, "region": region})
                added += 1

        return added, updated, skipped
    except Exception:
        st.error("匯入 CSV 發生錯誤")
        return 0, 0, 0

# ---------- 匯出 JSON ----------
def export_json():
    c.execute("SELECT id, symbol, shares, region FROM portfolio ORDER BY id")
    rows = c.fetchall()
    data = []
    for r in rows:
        data.append({"id": r[0], "symbol": r[1], "shares": r[2], "region": r[3]})
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return filename, json_text

# ---------- 匯入 JSON ----------
def import_json_with_mode(uploaded_file, mode="skip"):
    """
    匯入 JSON（陣列），mode 同 CSV：
      - "skip"     : 衝突則略過（預設）
      - "overwrite": 衝突則覆蓋（UPDATE）
      - "append"   : 全部新增（不檢查衝突）
    回傳 (added_count, updated_count, skipped_count)
    """
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        data = json.loads(content)
        if not isinstance(data, list):
            st.error("JSON 必須為陣列格式")
            return 0, 0, 0

        added = updated = skipped = 0
        # 建立現有索引（symbol||region -> item）
        existing_index = {f"{p['symbol'].strip()}||{p['region'].strip()}": p for p in st.session_state.portfolio}

        for entry in data:
            symbol = (entry.get("symbol") or entry.get("代號") or "").strip()
            shares_raw = entry.get("shares") or entry.get("持股數")
            region = (entry.get("region") or entry.get("市場") or "").strip()
            if not symbol or shares_raw is None:
                skipped += 1
                continue
            try:
                shares_int = int(shares_raw)
            except Exception:
                # 若 shares 不是整數，嘗試轉 float 再取整數
                try:
                    shares_int = int(float(shares_raw))
                except Exception:
                    skipped += 1
                    continue

            key = f"{symbol}||{region}"
            existing = existing_index.get(key)

            if existing:
                if mode == "skip":
                    skipped += 1
                    continue
                elif mode == "overwrite":
                    # 更新 SQLite 與 session_state
                    c.execute("UPDATE portfolio SET shares = ?, region = ? WHERE id = ?", (shares_int, region, existing["id"]))
                    conn.commit()
                    for p in st.session_state.portfolio:
                        if p["id"] == existing["id"]:
                            p["shares"] = shares_int
                            p["region"] = region
                            break
                    updated += 1
                elif mode == "append":
                    c.execute("INSERT INTO portfolio (symbol, shares, region) VALUES (?, ?, ?)",
                              (symbol, shares_int, region))
                    conn.commit()
                    new_id = c.lastrowid
                    st.session_state.portfolio.append({"id": new_id, "symbol": symbol, "shares": shares_int, "region": region})
                    added += 1
            else:
                # 新增
                c.execute("INSERT INTO portfolio (symbol, shares, region) VALUES (?, ?, ?)",
                          (symbol, shares_int, region))
                conn.commit()
                new_id = c.lastrowid
                st.session_state.portfolio.append({"id": new_id, "symbol": symbol, "shares": shares_int, "region": region})
                added += 1

        return added, updated, skipped
    except json.JSONDecodeError:
        st.error("JSON 解析錯誤：請確認檔案為有效的 JSON 格式（陣列）。")
        return 0, 0, 0
    except Exception:
        st.error("匯入 JSON 發生錯誤")
        return 0, 0, 0

st.markdown("### 匯出與匯入")

# 匯出按鈕（CSV）
if st.button("⬇️ 匯出 CSV"):
    fname, csv_text = export_csv()
    st.download_button(label="下載 CSV 檔案", data=csv_text, file_name=fname, mime="text/csv")

def preview_csv_with_conflicts(uploaded_file):
    """
    解析上傳的 CSV，回傳 preview_list（每項包含 incoming 與 existing）
    並在 UI 顯示預覽，衝突（symbol+region 相同）以紅色標示。
    放置位置 建議：在 import_csv / import_json 定義附近或工具函式區。
    """
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            st.info("CSV 檔案為空或無可讀取列。")
            return []

        # 建立現有索引以加速比對（key = symbol + '||' + region）
        existing_index = {}
        for p in st.session_state.portfolio:
            key = f"{p['symbol'].strip()}||{p['region'].strip()}"
            existing_index[key] = p

        preview_list = []
        st.markdown("#### 匯入預覽（紅色表示與現有資料發生衝突）")
        for i, row in enumerate(rows, start=1):
            symbol = (row.get("代號") or row.get("symbol") or "").strip()
            shares = row.get("持股數") or row.get("shares") or ""
            region = (row.get("市場") or row.get("region") or "").strip()
            incoming = {"symbol": symbol, "shares": shares, "region": region}
            key = f"{symbol}||{region}"
            existing_item = existing_index.get(key)

            # 建立顯示字串，若衝突則顯示現有資料並以紅色標示
            if existing_item:
                exist_sym = html.escape(str(existing_item["symbol"]))
                exist_shares = html.escape(str(existing_item["shares"]))
                exist_region = html.escape(str(existing_item["region"]))
                html_line = (
                    f"<div style='font-family: monospace; color: #FF8040;'>"
                    f"{i}. 匯入 -> 代號: {html.escape(symbol)}  持股: {html.escape(str(shares))}  市場: {html.escape(region)} "
                    f"<span style='color: darkred;'>【衝突】現有 -> 代號: {exist_sym} 持股: {exist_shares} 市場: {exist_region}</span>"
                    f"</div>"
                )
            else:
                html_line = (
                    f"<div style='font-family: monospace; color: black;'>"
                    f"{i}. 代號: {html.escape(symbol)}  持股: {html.escape(str(shares))}  市場: {html.escape(region)}</div>"
                )

            st.markdown(html_line, unsafe_allow_html=True)
            preview_list.append({"incoming": incoming, "existing": existing_item})
        return preview_list
    except Exception:
        st.error("解析 CSV 預覽時發生錯誤")
        return []

def preview_json_with_conflicts(uploaded_file):
    """
    解析上傳的 JSON（預期為陣列），顯示預覽並標示與現有資料衝突（symbol + region 同時相同）。
    回傳 preview_list（每項包含 incoming 與 existing）。
    """
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        data = json.loads(content)  # 預期 data 為 list of dict
        if not isinstance(data, list) or len(data) == 0:
            st.info("JSON 檔案不是陣列或為空。請上傳包含多筆物件的 JSON 陣列。")
            return []

        # 建立現有索引（key = symbol||region）
        existing_index = {f"{p['symbol'].strip()}||{p['region'].strip()}": p for p in st.session_state.portfolio}

        preview_list = []
        st.markdown("#### JSON 匯入預覽（紅色表示與現有資料發生衝突）")
        for i, entry in enumerate(data, start=1):
            # 支援中文或英文欄位名
            symbol = (entry.get("symbol") or entry.get("代號") or "").strip()
            shares = entry.get("shares") or entry.get("持股數") or ""
            region = (entry.get("region") or entry.get("市場") or "").strip()
            incoming = {"symbol": symbol, "shares": shares, "region": region}
            key = f"{symbol}||{region}"
            existing_item = existing_index.get(key)

            # 顯示：若衝突則紅色並顯示現有資料
            if existing_item:
                exist_sym = html.escape(str(existing_item["symbol"]))
                exist_shares = html.escape(str(existing_item["shares"]))
                exist_region = html.escape(str(existing_item["region"]))
                html_line = (
                    f"<div style='font-family: monospace; color: #FF8040;'>"
                    f"{i}. 匯入 -> 代號: {html.escape(symbol)}  持股: {html.escape(str(shares))}  市場: {html.escape(region)} "
                    f"<span style='color: darkred;'>【衝突】現有 -> 代號: {exist_sym} 持股: {exist_shares} 市場: {exist_region}</span>"
                    f"</div>"
                )
            else:
                html_line = (
                    f"<div style='font-family: monospace; color: black;'>"
                    f"{i}. 代號: {html.escape(symbol)}  持股: {html.escape(str(shares))}  市場: {html.escape(region)}</div>"
                )

            st.markdown(html_line, unsafe_allow_html=True)
            preview_list.append({"incoming": incoming, "existing": existing_item})
        return preview_list
    except json.JSONDecodeError:
        st.error("JSON 解析錯誤：請確認檔案為有效的 JSON 格式（陣列）。")
        return []
    except Exception:
        st.error("解析 JSON 預覽時發生錯誤")
        return []

# 匯入上傳（CSV）
uploaded_csv = st.file_uploader("上傳 CSV 以匯入（欄位：代號, 持股數, 市場）", type=["csv"])
if uploaded_csv is not None:
    # 先顯示預覽並標示與現有資料衝突的列
    preview_rows = preview_csv_with_conflicts(uploaded_csv)

    # 顯示匯入策略按鈕
    st.markdown("請選擇匯入策略（衝突定義：symbol 與 region 同時相同）")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("匯入並略過衝突"):
            a, u, s = import_csv_with_mode(uploaded_csv, mode="skip")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()
    with col_b:
        if st.button("匯入並覆蓋衝突"):
            a, u, s = import_csv_with_mode(uploaded_csv, mode="overwrite")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()
    with col_c:
        if st.button("全部新增（不檢查衝突）"):
            a, u, s = import_csv_with_mode(uploaded_csv, mode="append")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()

# 匯出 JSON
if st.button("⬇️ 匯出 JSON"):
    fname, json_text = export_json()
    st.download_button(label="下載 JSON 檔案", data=json_text, file_name=fname, mime="application/json")

# 匯入 JSON
uploaded_json = st.file_uploader("上傳 JSON 以匯入（格式為陣列，每筆包含 symbol/代號, shares/持股數, region/市場）", type=["json"])
if uploaded_json is not None:
    # 先顯示預覽並標示衝突
    preview_rows = preview_json_with_conflicts(uploaded_json)

    # 顯示匯入策略按鈕（與 CSV 相同）
    st.markdown("請選擇匯入策略（衝突定義：symbol 與 region 同時相同）")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("匯入並略過衝突（JSON）"):
            a, u, s = import_json_with_mode(uploaded_json, mode="skip")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()
    with col_b:
        if st.button("匯入並覆蓋衝突（JSON）"):
            a, u, s = import_json_with_mode(uploaded_json, mode="overwrite")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()
    with col_c:
        if st.button("全部新增（不檢查衝突，JSON）"):
            a, u, s = import_json_with_mode(uploaded_json, mode="append")
            st.success(f"新增 {a} 筆，更新 {u} 筆，略過 {s} 筆")
            safe_rerun()

# 清空清單與二次確認
if st.button("清空全部"):
    st.warning("⚠️ 確認要刪除資料庫中所有項目？此操作無法復原。")
    if st.button("確認清空"):
        c.execute("DELETE FROM portfolio")
        conn.commit()
        st.session_state.portfolio = []
        st.info("股票清單已清空")
        safe_rerun()
