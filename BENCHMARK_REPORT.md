# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Lê Thái Dương (2A202603415)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows + Ubuntu WSL2 (Python 3.14.4), Docker Desktop 29.9.3

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | `< 500 ms` | Đảm bảo 95% người dùng nhận phản hồi dưới 0.5 giây, giữ trải nghiệm hội thoại mượt mà. |
| Error rate `/ask` | `< 2.0 %` | Cho phép error budget 2% để chịu lỗi mạng/upstream ngắn hạn mà không báo động giả. |
| Accuracy trên golden dataset | `≥ 80 %` | Đảm bảo chất lượng trả lời đạt chuẩn tối thiểu và không bị regression khi thay đổi code/KB. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.69 | 190.9 | 221.1 | 1680.2 | 2.00% | PASS |
| 10 | 38.89 | 194.5 | 231.5 | 1687.0 | 2.33% | FAIL |
| 50 | 77.85 | 240.0 | 1635.8 | 1858.4 | 0.33% | FAIL |
| 100 | 47.95 | 845.4 | 4227.3 | 4709.7 | 0.33% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. RPS tăng từ `4.69` (c=1) lên `38.89` (c=10) và đạt đỉnh `77.85` ở `c=50`, nhưng đến `c=100` thì **giảm xuống `47.95` req/s** và p95 tăng vọt lên `4227.3 ms`. Nguyên nhân là khi concurrency vượt quá khả năng xử lý của một process đơn lẻ (event loop / CPU / context switching), các request phải xếp hàng chờ nhau, làm latency tăng mạnh và throughput giảm.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 200.3 | 243.1 | 266.9 |
| 0.03 (mặc định) | 247.8 | 278.6 | 1714.9 |
| 0.1 | 334.8 | 1674.2 | 1699.4 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

**p99** (và **p95** khi tỷ lệ chậm tăng lên 10%) nhạy nhất với request chậm: ở `MOCK_SLOW_RATE=0.03`, `avg` chỉ nhích từ `200.3 ms` lên `247.8 ms` trong khi `p99` nhảy vọt từ `266.9 ms` lên `1714.9 ms` (gấp ~6.4 lần). Nếu đặt SLO theo `average`, hệ thống vẫn trông "khỏe" dù thực tế cứ 100 người lại có người phải chờ gần 2 giây.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.8 | 109.1 | 113.3 |
| Tổng cost (USD) | $0.000414 | $0.000762 | $0.000787 |
| Cost / câu đúng (USD) | $0.00041415 | $0.00003627 | $0.00003423 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "xác thực"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` giải thích JWT tự chứa thông tin, có chữ ký (signature) và thời gian hết hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` nêu rõ HPA scale dựa trên CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v2 thêm bước retrieval từ `KNOWLEDGE_BASE` nên tốn thêm một chút latency (~20 ms) và gần gấp đôi số token/câu (`109.1–113.3` so với `57.8`), làm tổng cost cao hơn (`$0.000787` vs `$0.000414`). Tuy nhiên accuracy tăng vọt từ `4.35%` lên `100%`, khiến **cost / câu đúng** của v2 (`$0.00003423`) **rẻ hơn ~12 lần** so với v1 (`$0.00041415`). Trong CI/CD, dùng exit code của `run_eval.py` (`--min-accuracy` + `--baseline`) giúp tự động chặn merge/deploy nếu bản mới làm giảm accuracy (regression).

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.25` (có tải Locust) | `AgentHighErrorRate` | ~60 giây (`for: 1m`) | Error Rate (%) / HTTP 5xx rate |
| B | `MOCK_SLOW_RATE=0.3` (lý thuyết theo rule) | `AgentHighLatencyP95` | ~120 giây (`for: 2m`) | Latency p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` (khi tải đủ lớn) | `LLMCostBurnRateHigh` | ~120 giây (`for: 2m`) | LLM Cost Burn Rate ($/h) |
| D | `docker pause` 1 instance (`agent-2`) | `AgentInstanceDown` | ~30 giây (`for: 30s`) | Up / Active Instances |
| E | `AGENT_VERSION=v1` | Không có alert nào | N/A | Chỉ phát hiện qua Eval (`accuracy`) |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy **automated evaluation trên golden dataset** (`eval/run_eval.py`) trong CI/CD quality gate trước khi deploy (so sánh accuracy với baseline và chặn nếu có regression), kết hợp theo dõi feedback người dùng (thumbs up/down) hoặc LLM-as-a-judge sampling trên traffic thật trong production.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `2d6258a0971d0a2236106d03e6f2d997`
- Tổng thời gian: `1663.9 ms`
- Span chiếm nhiều thời gian nhất: `llm.generate` (~1600 ms, ~96% tổng thời gian — do `MOCK_SLOW_RATE` tạo tail latency ở bước gọi LLM)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T10:32:34.254183+00:00", "level": "INFO", "service": "observable-agent", "instance": "39819e3cd7b5", "event": "http_request", "trace_id": "2d6258a0971d0a2236106d03e6f2d997", "span_id": "e7c87269a434a4af", "request_id": "de614892fe9d", "method": "POST", "route": "/ask", "status": 200, "ms": 1663.9}
```

*(Trace lỗi tham khảo: `trace_id = 7be2907beeeed4cd482488e9b1cbd968`, `status = 503`, `ms = 111.1`)*

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.87 | 190 | 230 | 1700 | 74 (1.04%) |
| 3 | 59.86 | 190 | 220 | 1700 | 72 (1.01%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Scale từ 1 lên 3 instance chỉ giảm nhẹ `p95` từ `230 ms` xuống `220 ms` nhưng **RPS gần như giữ nguyên (~59.9 req/s)**. Lý do là ở mức tải 100 users của Locust (có `wait_time` giữa các request), 1 instance async FastAPI đã đủ dư sức phục vụ hết lượng traffic này (`p95 = 230 ms`), nên **nút thắt nằm ở phía tải sinh ra từ Locust (số lượng user & `wait_time`)**, không phải CPU của `agent`. Nếu tăng số user Locust lên cao hơn nữa (làm bão hoà 1 instance) thì 3 instance mới thể hiện rõ sự vượt trội về RPS và p95.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
