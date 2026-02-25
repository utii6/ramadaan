import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    schedule_hours INTEGER DEFAULT 6
)
""")

conn.commit()


def add_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()


def get_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


def set_schedule(user_id: int, hours: int):
    cursor.execute("UPDATE users SET schedule_hours=? WHERE user_id=?", (hours, user_id))
    conn.commit()


def get_schedule(user_id: int):
    cursor.execute("SELECT schedule_hours FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 6
