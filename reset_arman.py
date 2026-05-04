"""Reset arman password to Wendrink2026! — run once inside Docker container."""
import bcrypt, sqlite3

pw = "Wendrink2026!"
h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

conn = sqlite3.connect("/app/wendrink.db")
conn.execute("UPDATE users SET password_hash=? WHERE login=?", (h, "arman"))
conn.commit()
conn.close()
print("OK — arman password reset to Wendrink2026!")
