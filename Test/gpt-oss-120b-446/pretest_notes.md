docker exec -it <container ID> python
# In Python:
import sqlite3
import bcrypt
conn = sqlite3.connect("data/reservations.db")
c = conn.cursor()
usernames = ["testuser1", "testuser2", "testuser3", "testuser4", "testuser5", "testuser6", "testuser7", "testuser8"]
passwords =[b"pass123", b"pass1232", b"pass1233", b"pass1234", b"pass1235", b"pass1236", b"pass1237", b"pass1238"]
for i, username in enumerate(usernames):
    c.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, bcrypt.hashpw(passwords[i], bcrypt.gensalt()).decode(), "admin")
    )
conn.commit()
conn.close()