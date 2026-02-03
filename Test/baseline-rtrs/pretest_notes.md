Baseline (human-written): restaurant-table-reservation-system

1) Create env:
cp applications/apps/baseline-rtrs/back-end/.env.example applications/apps/baseline-rtrs/back-end/.env

2) Start the stack:
cd applications/apps/baseline-rtrs
docker compose down -v
docker compose up --build

If port 5000 is busy on your machine, run:
HOST_PORT=5001 docker compose up --build
(and use http://localhost:5001)

3) Verify:
curl -i http://localhost:${HOST_PORT:-5000}/

4) Reset DB between runs:
docker compose down -v
