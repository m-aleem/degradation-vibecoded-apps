curl -X POST http://localhost:8888/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"adminpassword"}'
# Save the token to TOKEN

curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser1", "password": "pass123", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser2", "password": "pass1232", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser3", "password": "pass1233", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser4", "password": "pass1234", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser5", "password": "pass1235", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser6", "password": "pass1236", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser7", "password": "pass1237", "role": "admin"}' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8888/users -H "Content-Type: application/json" -d '{"username": "testuser8", "password": "pass1238", "role": "admin"}' -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8888/restaurants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Cafe A", "description": "Great coffee and snacks", "address": "123 Main St"}'

curl -X POST http://localhost:8888/restaurants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Bistro B", "description": "Healthy meals", "address": "456 Oak Ave"}'

# Ensure the IDs from above are 1 and 2

curl -X POST http://localhost:8888/restaurants/1/menus \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Lunch Menu"}'

curl -X POST http://localhost:8888/restaurants/2/menus \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Dinner Menu"}'

# Ensure the IDs from above are 1 and 2

curl -X POST http://localhost:8888/menus/1/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Burger", "description": "Classic beef burger", "price": 12.50}'

curl -X POST http://localhost:8888/menus/1/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Fries", "description": "Crispy fries", "price": 5.00}'

curl -X POST http://localhost:8888/menus/2/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Salad", "description": "Fresh garden salad", "price": 10.00}'


# Ensure the IDs from above are 1 and 2 and 3