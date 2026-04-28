"""
독립적으로 실행 가능한 DB 초기화 스크립트
Usage: python init_db.py
"""
import sqlite3
import os

DATABASE = "vuln_app.db"

def init_db():
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
        print(f"[*] Removed existing {DATABASE}")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    """)
    c.executemany("INSERT INTO users (username, password, email, role) VALUES (?,?,?,?)", [
        ("admin",   "admin123",   "admin@vuln-app.local",  "admin"),
        ("alice",   "password1",  "alice@example.com",     "user"),
        ("bob",     "qwerty",     "bob@example.com",       "user"),
        ("charlie", "letmein",    "charlie@example.com",   "user"),
    ])

    c.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT
        )
    """)
    c.executemany("INSERT INTO products (name, price, description) VALUES (?,?,?)", [
        ("Laptop Pro",          1299.99, "High-performance laptop"),
        ("Wireless Mouse",        29.99, "Ergonomic wireless mouse"),
        ("USB-C Hub",             49.99, "7-in-1 USB-C hub"),
        ("Mechanical Keyboard",   89.99, "RGB mechanical keyboard"),
    ])

    c.execute("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.executemany("INSERT INTO comments (author, content) VALUES (?,?)", [
        ("admin", "Welcome to the vulnerable comment board!"),
        ("alice", "This is a test comment."),
    ])

    c.execute("""
        CREATE TABLE csrf_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"[+] Database '{DATABASE}' initialized successfully.")
    print("[+] Sample data inserted:")
    print("    Users  : admin/admin123, alice/password1, bob/qwerty, charlie/letmein")
    print("    Products: 4 items")
    print("    Comments: 2 items")


if __name__ == "__main__":
    init_db()
