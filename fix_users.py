"""Fix users: rename logins and set correct password — run once inside Docker."""
import bcrypt, sqlite3

pw = "Wendrink2026!"
h = lambda: bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

conn = sqlite3.connect("/app/wendrink.db")

updates = [
    ("gauhar",    h(), "aigul"),
    ("makhambет", h(), "partner1"),
    ("aika",      h(), "partner2"),
]

for new_login, new_hash, old_login in updates:
    conn.execute(
        "UPDATE users SET login=?, password_hash=? WHERE login=?",
        (new_login, new_hash, old_login)
    )
    print(f"  {old_login} → {new_login} / {pw}")

conn.commit()
conn.close()
print("Done!")
