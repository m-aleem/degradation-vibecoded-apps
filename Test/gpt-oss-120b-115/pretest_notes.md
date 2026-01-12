docker exec -it <container ID> sh -c 'node -e "
const sqlite3 = require(\"sqlite3\").verbose();
const bcrypt = require(\"bcryptjs\");
const db = new sqlite3.Database(\"./data/app.db\");
const users = [
  { username: \"testuser1\", password: \"pass123\"},
  { username: \"testuser2\", password: \"pass1232\"},
  { username: \"testuser3\", password: \"pass1233\"},
  { username: \"testuser4\", password: \"pass1234\"},
  { username: \"testuser5\", password: \"pass1235\"},
  { username: \"testuser6\", password: \"pass1236\"},
  { username: \"testuser7\", password: \"pass1237\"},
  { username: \"testuser8\", password: \"pass1238\"}
];
users.forEach(u => {
  const hashed = bcrypt.hashSync(u.password, 10);
  db.run(\"INSERT INTO users (username, password) VALUES (?, ?)\", [u.username, hashed], (err) => {
    if(err) console.error(err); else console.log(\"Inserted\", u.username);
  });
});
db.close();
"'