# Deployment Information

## Public URL
https://k5-l3-day14-lethaiduong-2a202603415.onrender.com

## Platform
Render (Web Service - Docker + Render Key Value / Redis)

## Test Commands

### Health & Readiness Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3-day14-lethaiduong-2a202603415.onrender.com/health"
# Expected: 200

curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3-day14-lethaiduong-2a202603415.onrender.com/ready"
# Expected: 200
```

### API Test (without & with authentication)
```bash
# Không có API key -> 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://k5-l3-day14-lethaiduong-2a202603415.onrender.com/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Có API key -> 200
curl -X POST "https://k5-l3-day14-lethaiduong-2a202603415.onrender.com/ask" \
  -H "X-API-Key: <YOUR_AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

## Observed Output
```text
health: 200
ready: 200
ask_no_key: 401
ask_with_key: 200
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

## Environment Variables Set (trên Render Dashboard)
- `ENVIRONMENT`
- `AGENT_API_KEY`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
