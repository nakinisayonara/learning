import sqlite3

conn = sqlite3.connect("portfolio.db")
cursor = conn.cursor()

# 建立必要的表格（這裡以 query_queue 為例）
cursor.execute("""
CREATE TABLE IF NOT EXISTS query_queue (
    symbol TEXT,
    shares INTEGER,
    region TEXT
)
""")

conn.commit()
conn.close()
print("初始化 portfolio.db 完成")
