# Rate Limiter Using Python and Redis

**Student:** AABIR DAS  
**Roll number:** UG/SOET/30/24/123  
**Course:** B.Tech CSE, 5th Semester

## Project overview

This project demonstrates a request rate limiter built with Python and Redis. A user is allowed five requests in a rolling 60-second window. The seventh-request demonstration shows how later requests are rejected until earlier requests leave the window.

## Working principle

Each user has a separate Redis Sorted Set. Every accepted request is stored as a unique member, with its request timestamp as the score. Before checking a new request, old scores are removed. The remaining members are counted. A request is accepted when the count is below five; otherwise it is rejected and the program reports an approximate retry time.

The check, cleanup, count, insert, and expiry operations run together in one Redis Lua script. Redis server time is used, so different client machine clocks do not affect the result.

## Algorithm and data model

The project uses the Sliding Window Log algorithm. Redis ZSET is suitable because timestamps can be removed by score and counted efficiently. Keys follow the pattern `udb:rate-limit:<user-id>`. Keys expire after the configured window when the user becomes inactive.

## Technologies

- Python 3.9 or newer
- Redis 6 or newer
- `redis` Python client
- Python `unittest`

## Folder structure

```text
UDB/
├── .gitignore
├── LICENSE
├── README.md
├── Redis.py
├── requirements.txt
└── test_redis.py
```

## Installation and Redis setup

Create a virtual environment and install the one required Python package:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start a local Redis server on port 6379. For a Docker installation:

```bash
docker run --name udb-redis -p 6379:6379 -d redis:7-alpine
```

The program uses `redis://localhost:6379/0` by default. Set `REDIS_URL` if another Redis-compatible server is required.

## Running the demonstration

```bash
python Redis.py
```

The output contains five `ALLOWED` lines followed by two `REJECTED` lines. Rejected lines include the active request count and approximate retry time.

## Testing

The tests use the running Redis server and create isolated, temporary key prefixes:

```bash
python -m unittest -v test_redis.py
```

They cover the five-request limit, independent users, expiry cleanup, retry calculation, and concurrent requests.

## Limitations

This is a command-line demonstration rather than a web API. The default limit and window are configured when the `RateLimiter` is created. A very high number of active users will create more Redis keys, although inactive keys expire automatically.

## Conclusion

The project shows how Redis Sorted Sets and the Sliding Window Log algorithm can enforce a simple, atomic rate limit. It also demonstrates why server-side time and a Lua script are useful when several requests arrive at the same time.

## Repository

GitHub: https://github.com/Aabir2006/UDB
