import sqlite3

conn = sqlite3.connect("store.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""")

for table_name, schema in cursor.fetchall():
    print(f"\n=== {table_name} ===")
    print(schema)

conn.close()
