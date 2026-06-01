# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Lê Xuân Tiến Đạt
- **Student ID**: 2A202600549
- **Date**: 2026-06-01
- **Team**: 16383

---

## I. Technical Contribution (15 Points)

Tôi phụ trách **Tools (bộ công cụ), Telemetry chi phí & Provider/Key management**.

- **Modules Implemented**:
  - `src/tools/basic_tools.py`: mở rộng dataset từ 4 → 16 sản phẩm, 8 mã giảm giá, 11 thành phố ship; thêm tool `check_stock`, `get_product_weight` (tổng 6 tool). **Gia cố tool `calculator`: bỏ `eval()`, chuyển sang trình phân tích AST an toàn** (chặn DoS như `2**99999`, truy cập biến/hàm).
  - `src/telemetry/metrics.py`: **thay cost giả bằng cost thật theo bảng giá từng model** (tách giá input/output token), thêm chỉ số `completion_ratio` và `session_summary()` tổng hợp token/chi phí/latency cả phiên.
  - `src/core/mimo_provider.py` và `src/core/router_provider.py`: 2 provider mới (MiMo Xiaomi và 9router gateway) tương thích OpenAI.
  - `src/core/key_manager.py`: cơ chế xoay vòng nhiều API key chống rate limit.

- **Code Highlights**:
  ```python
  # calculator: AST thay cho eval() -> chỉ cho phép các phép toán cơ bản,
  # KHÔNG có ** nên chặn được biểu thức gây treo máy (DoS) như 2**99999.
  def _safe_eval(node):
      if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
          return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
      if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
          return node.value
      raise ValueError("unsupported expression")
  ```
  ```python
  # Cost thật: tính riêng token input và output theo bảng giá từng model.
  def _calculate_cost(self, model, usage):
      p = self._lookup_pricing(model)
      return round(usage.get("prompt_tokens",0)/1000*p["input"]
                 + usage.get("completion_tokens",0)/1000*p["output"], 6)
  ```
  ```python
  def rotate(self):  # KeyManager: nhảy sang key kế tiếp khi rate limit
      with self._lock:
          self._index = (self._index + 1) % len(self._keys)
          return self._keys[self._index]
  ```

- **Documentation**: Mô tả tool (`description`) được viết kỹ kèm ví dụ gọi, vì LLM chỉ "hiểu" tool qua chuỗi mô tả này. Provider Pattern cho phép đổi `cx/gpt-5.5` ↔ `mimo` ↔ Gemini chỉ qua `.env`.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: Khi mới cấu hình, gọi Gemini bị lỗi liên tục dù key xác thực được. Sau đó là lỗi quota.
- **Log/Error Source**:
  ```
  404 models/gemini-1.5-flash is not found for API version v1beta ...
  429 ... Quota exceeded ... limit: 0, model: gemini-2.0-flash
  ```
- **Diagnosis**: Hai lỗi khác nhau: (1) tên model `gemini-1.5-flash` đã ngừng hỗ trợ → phải đổi sang `gemini-2.0-flash`; (2) các key dạng OAuth `AQ.Ab8...` gắn với project có `limit: 0` (không có quota free tier) nên xoay vòng key cũng vô ích. Đây là minh chứng: xoay vòng key chỉ giúp khi các key có quota độc lập.
- **Solution**: Chuyển provider chính sang `cx/gpt-5.5` qua 9router (chạy local, latency ~5s) và MiMo cho bộ đánh giá. Giữ Gemini như tuỳ chọn demo đổi provider khi có key chuẩn `AIza...`.

### Case study phụ: lỗ hổng `eval()` trong tool calculator

- **Problem**: Tool `calculator` ban đầu dùng `eval(expression)`. Dù đã whitelist ký tự, biểu thức `2**99999999` vẫn lọt qua và khiến tiến trình **treo cứng** (Python cố tính số nguyên khổng lồ) — một dạng DoS do chính LLM có thể vô tình sinh ra.
- **Diagnosis**: Whitelist ký tự không đủ; toán tử luỹ thừa `**` hợp lệ về mặt cú pháp nhưng nguy hiểm. `eval` còn cho phép truy cập cấu trúc Python ngoài ý muốn.
- **Solution**: Viết lại bằng **AST parser** (`ast.parse` + duyệt cây), chỉ cho phép `+ - * / % //` và số. Loại bỏ hoàn toàn `**` và mọi `Name/Call/Attribute`. Kết quả: `2**99999999` → trả `"unsupported expression"` thay vì treo; chia 0 → báo lỗi rõ ràng. Đây là minh chứng trực tiếp cho nguyên tắc "tool không được làm sập cả vòng lặp agent".

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: Chất lượng tool quyết định chất lượng agent. Mô tả tool mơ hồ khiến LLM gọi sai tham số; mô tả rõ + ví dụ giúp nó gọi đúng ngay.
2. **Reliability**: Agent chỉ đáng tin khi tool trả dữ liệu thật. Tool `check_stock` (có hàng hết) tạo tình huống agent phải xử lý "out of stock" thay vì cứ tính tiền — điều Chatbot không bao giờ kiểm tra.
3. **Observation**: Khi tool trả về thông báo lỗi thân thiện ("Tool not found", "No price found"), agent có cơ hội tự sửa ở bước sau; nếu tool crash thì cả vòng lặp hỏng.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Khi số tool lớn, dùng Vector DB để truy hồi tool liên quan thay vì nhét hết mô tả vào prompt.
- **Safety (đã làm một phần)**: Tool `calculator` đã được gia cố bằng AST parser. Bước tiếp theo: validate & chuẩn hóa tham số (tên sản phẩm "iPhone 15" → `iphone`, tên thành phố) trước khi tra cứu.
- **Cost-aware routing**: Đã có cost thật theo từng model (`metrics.py`). Hướng phát triển: dựa vào `session_summary()` để tự chọn model flash giá rẻ cho bước đơn giản và model mạnh cho bước suy luận — tối ưu chi phí/ROI cho hệ production.
- **Performance**: Chọn model flash (vd `ag/gemini-3-flash`) cho các bước đơn giản để giảm latency.
