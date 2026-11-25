# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found (`01-localhost-vs-production/develop/app.py`)
1. **Hardcode secret trong source code (dòng 17–18):** `OPENAI_API_KEY` và `DATABASE_URL` viết thẳng trong code; nếu push lên GitHub sẽ lộ secret ngay lập tức.
2. **Không quản lý cấu hình qua biến môi trường (dòng 21–22):** `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng, không linh hoạt theo từng môi trường (dev/staging/prod).
3. **Dùng `print()` thay cho structured logging và log cả secret (dòng 33–38):** `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` làm lộ API key ra stdout và khó parse trong các hệ thống log aggregator.
4. **Thiếu health check / readiness endpoint (dòng 42–43):** Không có `/health` hay `/ready`, nên nền tảng cloud/load balancer không biết khi nào container sống hay sẵn sàng nhận traffic.
5. **Bind cứng `host="localhost"`, `port=8000` và bật `reload=True` (dòng 49–54):** Chỉ nhận kết nối từ chính máy local (không chạy được trong container/cloud), không đọc biến `PORT` do nền tảng inject, và bật auto-reload trong production gây tốn tài nguyên/rủi ro ổn định.
6. **Không xử lý graceful shutdown:** Không bắt tín hiệu `SIGTERM` hay quản lý vòng đời (`lifespan`), khiến request đang chạy có thể bị ngắt đột ngột khi tắt/restart server.

### Exercise 1.2: Kết quả chạy bản `develop`
Chạy bằng `uvicorn app:app --port 8005` (tránh đụng cổng 8000 đang chạy dịch vụ khác) và gọi `curl -i -sS -X POST "http://localhost:8005/ask?question=Hello"`:

```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:14:08 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 1.3: Comparison table (`develop/app.py` vs `production/app.py`)
| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Why Important? |
|---------|----------------------------|----------------------------------|----------------|
| Config & Secrets | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `port=8000` (dòng 17–22, 51–53) | Đọc từ biến môi trường qua `settings` (`config.py`), bind `settings.host` (`0.0.0.0`) và `settings.port` (dòng 24, 196–198) | Tránh lộ secret trên Git và cho phép đổi cấu hình theo môi trường (staging/prod) mà không cần sửa code. |
| Health check | Không có (dòng 42–43) | Có `GET /health` (liveness, dòng 135–149) và `GET /ready` (readiness, trả 503 khi `is_ready=False`, dòng 152–161) | Platform/Load Balancer biết khi nào container sống để restart và khi nào sẵn sàng để route traffic vào. |
| Logging | Dùng `print()` và in thẳng `OPENAI_API_KEY` (dòng 33–38) | Structured JSON logging qua `logging` + `json.dumps()`, chỉ log metadata (`question_length`, `client_ip`), không log secret (dòng 28–32, 111–122) | Bảo mật thông tin nhạy cảm và dễ tìm kiếm/phân tích trên hệ thống tập trung (Datadog, Loki). |
| Shutdown | Tắt đột ngột, không xử lý signal | Có `lifespan` (đặt `is_ready = False` trước khi tắt, dòng 40–68) và `signal.signal(signal.SIGTERM, handle_sigterm)` (dòng 180–189) | Cho phép các request đang xử lý hoàn tất trước khi container dừng, tránh lỗi 502/cắt ngang người dùng. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)
1. **Base image:** `python:3.11` (bản phân phối Python đầy đủ trên Debian, dung lượng lớn ~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` trước `COPY . .` (hoặc copy code):** Để tận dụng **Docker layer cache**. `requirements.txt` ít thay đổi hơn code `app.py`; khi chỉ sửa code, Docker sẽ dùng lại layer đã cài pip trước đó thay vì tải và cài lại toàn bộ thư viện.
4. **CMD vs ENTRYPOINT khác nhau thế nào:**
   - `ENTRYPOINT` định nghĩa tiến trình chính cố định của container (khó bị ghi đè khi chạy `docker run <image> <args>`, các tham số truyền thêm sẽ nối vào sau `ENTRYPOINT`).
   - `CMD` cung cấp lệnh mặc định (hoặc tham số mặc định cho `ENTRYPOINT`) và **dễ dàng bị ghi đè** khi truyền lệnh ở cuối `docker run`.

### Exercise 2.2: Kết quả chạy container `my-agent:develop`
Chạy `docker run -d --rm -p 8005:8000 --name test-dev my-agent:develop` (ánh xạ sang cổng 8005 để tránh trùng cổng 8000) và gọi `POST /ask?question=What%20is%20Docker%3F`:

```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:21:10 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & Image size comparison
- **Stage 1 (`builder`):** Dùng `python:3.11-slim`, cài các thư viện Python vào `/root/.local` qua `pip install --no-cache-dir --user`.
- **Stage 2 (`runtime`):** Dùng lại `python:3.11-slim` sạch sẽ, tạo non-root user `appuser`, chỉ `COPY --from=builder /root/.local /home/appuser/.local` cùng source code cần chạy, cấu hình `HEALTHCHECK` và `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]`.
- **Tại sao nhỏ hơn:** Stage `runtime` không chứa base Debian đầy đủ của `python:3.11` và loại bỏ toàn bộ công cụ/cache build ở Stage 1.
- **Số đo thực tế (`docker images my-agent`):**
  - Develop (`my-agent:develop`): **1.67 GB (1,670 MB)** disk usage (*426 MB content size*)
  - Production (`my-agent:advanced`): **240 MB** disk usage (*57.4 MB content size*)
  - Difference: Giảm **~85.6%** disk usage (và **~86.5%** content size).

### Exercise 2.4: Docker Compose stack & Nginx test
- **Sơ đồ services & giao tiếp (mạng nội bộ `internal`):**
  - `Client` → cổng `80`/`443` → **`nginx`** (Reverse Proxy / Load Balancer) → chuyển tiếp nội bộ tới **`agent`** (FastAPI, không mở port trực tiếp ra host).
  - **`agent`** kết nối nội bộ tới **`redis:6379`** (cache/rate limit) và **`qdrant:6333`** (vector DB), dùng `depends_on` với `condition: service_healthy`.
- **Kết quả test qua Nginx (`GET /health` và `POST /ask`):**
```text
GET http://localhost/health -> 200 OK
{"status":"ok","uptime_seconds":14.4,"version":"2.0.0","timestamp":"2026-11-25T09:22:13.373072"}

POST http://localhost/ask -> 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deployment (agent Part 6)
- Platform: *(Railway / Render)*
- Public URL: *(TODO)*
- Screenshot: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

### So sánh `railway.toml` vs `render.yaml`
- **`railway.toml`** (định dạng TOML): Cấu hình gọn cho **1 service** hiện tại (`[build] builder = "DOCKERFILE"`, `[deploy] healthcheckPath = "/health"`, `restartPolicyType`), không khai báo trực tiếp env vars hay database đi kèm trong file mà cấu hình qua Railway Dashboard/CLI.
- **`render.yaml`** (định dạng YAML — Blueprint / Infrastructure-as-Code): Mô tả **toàn bộ kiến trúc nhiều service** trong cùng repo (`services:` gồm `type: web`, `runtime: docker`, `healthCheckPath: /health`, có thể khai báo kèm Redis/DB) và khai báo tường minh `envVars` ngay trong file (hỗ trợ `generateValue: true` để tự sinh secret hoặc `sync: false` để nhập tay trên dashboard).

### Exercise 3.3: Cloud Run CI/CD pipeline (`cloudbuild.yaml` & `service.yaml`)
Pipeline CI/CD trong `cloudbuild.yaml` tự động kích hoạt khi push lên nhánh `main` và chạy tuần tự 4 bước: (1) `test` — cài dependencies và chạy `pytest`; (2) `build` — build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng cache); (3) `push` — đẩy image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`); (4) `deploy` — triển khai lên Cloud Run (`asia-southeast1`) với `min-instances=1`, `max-instances=10`, lấy secret từ Secret Manager. File `service.yaml` định nghĩa cấu hình Knative/Cloud Run dạng IaC gồm tài nguyên (1 CPU, 512Mi RAM), concurrency 80, secret từ Secret Manager và hai probe `/health`, `/ready`.

---

## Part 4: API Security

### Exercise 4.1–4.3: Test results (đã che token)

#### Exercise 4.1 — API Key Authentication (`04-api-gateway/develop/app.py`)
- **Kiểm tra ở đâu:** Dependency `verify_api_key` đọc header `X-API-Key` và gắn vào `POST /ask` qua `Depends(verify_api_key)` (dòng 39–54, 70).
- **Khi thiếu/sai key:** Thiếu key trả về `401 Unauthorized`; sai key trả về `403 Forbidden`.
- **Cách rotate key:** Đổi giá trị biến môi trường `AGENT_API_KEY` trên nền tảng rồi restart/rollout (hoặc hỗ trợ danh sách gồm key cũ + key mới trong thời gian chuyển tiếp để không gián đoạn client).

```text
--- KHÔNG CÓ KEY (401) ---
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

--- CÓ KEY (200) ---
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

#### Exercise 4.2 & 4.3 — JWT Auth & Rate Limiting (`04-api-gateway/production/`)
- **Algorithm:** `RateLimiter` trong `rate_limiter.py` dùng **Sliding Window Counter** (lưu `deque` các timestamp theo `user_id`, loại bỏ timestamp cũ hơn `window_seconds = 60`).
- **Limit:** `student` (`user`) giới hạn **10 requests / 60 giây**; `teacher` (`admin`) có tier riêng **100 requests / 60 giây**.
- **Output test với tài khoản `student` (`POST /auth/token`, token đã che `eyJhbGciOiJI***`):**

```text
Got token (masked): eyJhbGciOiJI***
Request 1 -> HTTP 200
{"question":"Test 1","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
Request 2..10 -> HTTP 200
Request 11 -> HTTP 429
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 12 -> HTTP 429
```

### Exercise 4.4: Cost guard implementation & Phân biệt với Rate limit
- **Rate limit** bảo vệ **tốc độ** (số request/phút, chống spam/DoS, trả về `429`).
- **Cost guard** bảo vệ **tiền / ngân sách** (tổng chi phí token tích luỹ theo ngày/tháng, trả về `402 Payment Required` khi vượt budget user hoặc `503` khi vượt global budget). Cần cả hai vì một request hợp lệ trong rate limit vẫn có thể tiêu tốn rất nhiều token/tiền nếu prompt dài.
- **Cách implement (`cost_guard.py`):** Trước khi gọi LLM gọi `check_budget(user_id)` kiểm tra chi phí hiện tại (`total_cost_usd` hoặc key `budget:{user_id}:{YYYY-MM}` trong Redis ở bản production) so với ngưỡng; sau khi gọi LLM xong gọi `record_usage(user_id, input_tokens, output_tokens)` để cộng dồn chi phí.

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes & `test_stateless.py`
- **Phân biệt `/health` (Liveness) và `/ready` (Readiness):**
  - `/health`: Kiểm tra **process còn sống hay không** (trả 200 kể cả khi Redis/DB tạm thời mất kết nối; nếu fail thì orchestrator restart container).
  - `/ready`: Kiểm tra **service có sẵn sàng nhận traffic không** (ping Redis/DB; nếu mất kết nối thì trả `503 Service Unavailable` để Load Balancer tạm ngừng route traffic vào instance đó).
- **Graceful shutdown:** Khi nhận `SIGTERM`, chuyển trạng thái sang not-ready, ngừng nhận request mới, chờ các request đang xử lý hoàn tất rồi mới đóng kết nối và thoát với exit code `0`.
- **Vì sao state trong RAM bị lỗi khi scale nhiều instance:** Mỗi container có bộ nhớ RAM riêng; khi Nginx chia tải (round-robin) qua 3 instance, request 1 và request 2 cùng 1 user có thể rơi vào 2 instance khác nhau nên không thấy lịch sử hội thoại của nhau. Lưu state (session history, rate limit, budget) vào **Redis** dùng chung giúp mọi instance chia sẻ cùng một trạng thái (*stateless design*).
- **Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python3 test_stateless.py`:**

```text
Session ID: c1124276-ec26-4e2b-b037-de3e677e2d32
Request 1: [instance-b55e57] -> What is Docker?
Request 2: [instance-7c4ee4] -> Why do we need containers?
Request 3: [instance-860629] -> What is Kubernetes?
Request 4: [instance-b55e57] -> How does load balancing work?
Request 5: [instance-7c4ee4] -> What is Redis used for?

Total requests: 5
Instances used: {'instance-7c4ee4', 'instance-860629', 'instance-b55e57'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

---

## Part 6: Final Project (`06-lab-complete/`)

### Output `check_production_ready.py` (phần `📋 Checklist Deliverable`)
```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

---

## AI log
- **Part 1 (Exercise 1.1 & 1.3):**
  - *Hỏi gì:* Nhờ đọc tài liệu repo, xác định các bước làm đầu tiên và hỗ trợ hoàn thành Part 1.
  - *Nhận gì:* Đã tạo khung `MISSION_ANSWERS.md`, phân tích 6 anti-patterns, lập bảng so sánh và chạy test `develop` trên cổng 8005.
  - *Tự sửa & kiểm tra:* Đã kiểm tra output HTTP 200 từ `POST /ask?question=Hello`.
- **Part 2 (Docker):**
  - *Hỏi gì:* Nhờ hướng dẫn & chạy build, đo dung lượng image và test Docker Compose stack.
  - *Nhận gì:* Phát hiện lỗi proxy 401 khi `apt-get` trong `02-docker/production/Dockerfile`, bỏ bước `apt-get` không cần thiết, build `my-agent:develop` (1.67 GB) và `my-agent:advanced` (240 MB), test qua Nginx.
  - *Tự sửa & kiểm tra:* Đã kiểm tra `docker images my-agent` và xác nhận `GET /health`, `POST /ask` trả 200 qua Nginx.
- **Part 4 (API Security) & Part 5 (Scaling & Reliability):**
  - *Hỏi gì:* Nhờ chạy test auth/rate-limit/stateless trên WSL2 và tổng hợp kết quả.
  - *Nhận gì:* Đã test 401/200 (API key), JWT + rate limit 429 sau 10 request, và chạy `test_stateless.py` qua 3 instance Docker + Redis.
  - *Tự sửa & kiểm tra:* Đã kiểm tra tất cả output HTTP và xác nhận `test_stateless.py` lưu đủ 10 message qua 3 instance.
- **Part 6 (`06-lab-complete/`) & Part 3 (phần phân tích):**
  - *Hỏi gì:* Nhờ hoàn thiện các file TODO trong `06-lab-complete/` và chạy `check_production_ready.py`.
  - *Nhận gì:* Đã implement `config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml` và viết phần so sánh Part 3.
  - *Tự sửa & kiểm tra:* Đã chạy `python3 check_production_ready.py` trên WSL2 có Docker và đạt `PASS 12/12` (43/43 checks).
