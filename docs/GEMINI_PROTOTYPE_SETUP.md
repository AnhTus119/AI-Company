# Kết nối Gemini cho thử nghiệm một Story Bible thật

Luồng này chỉ tạo **Story Bible + kế hoạch 20 chương + Hook–Story Contract** từ một `user_idea`. Nó chưa viết 20 chương thật, chưa tạo video thật và không được tính `production_ready`.

## 1. Tạo API key

1. Mở [Google AI Studio](https://aistudio.google.com/) bằng tài khoản của bạn.
2. Tạo/chọn project và tạo Gemini API key.
3. Xem model mà project thực sự truy cập được tại [Gemini models](https://ai.google.dev/gemini-api/docs/models).
4. Xem quota hiện tại trong AI Studio và giá tại [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

Không gửi key qua chat, ảnh chụp hoặc commit Git. Nếu key từng bị lộ, hãy thu hồi và tạo key mới.

## 2. Tạo `.env`

Trong thư mục dự án, sao chép `.env.example` thành `.env`, rồi điền các dòng sau:

```dotenv
AI_COMPANY_REAL_AI_ENABLED=true
GEMINI_API_KEY=key-cua-ban
GEMINI_MODEL=model-id-chinh-xac-tu-AI-Studio

AI_COMPANY_POLICY_VERSION=gemini-prototype-policy-v1
AI_COMPANY_ASSIGNMENT_VERSION=gemini-prototype-models-v1
AI_COMPANY_BUDGET_VERSION=gemini-prototype-budget-v1

AI_COMPANY_DAILY_BUDGET_MINOR=100
AI_COMPANY_BUDGET_CURRENCY=USD
AI_COMPANY_GEMINI_RATE_CARD_VERSION=ngay-va-ten-tier-ban-da-kiem-tra
AI_COMPANY_GEMINI_INPUT_MINOR_PER_MILLION=gia-input
AI_COMPANY_GEMINI_OUTPUT_MINOR_PER_MILLION=gia-output
AI_COMPANY_GEMINI_MAX_OUTPUT_TOKENS=6000
AI_COMPANY_GEMINI_TIMEOUT_SECONDS=60
```

`minor unit` là cent khi currency là USD: `100` tương đương trần nội bộ USD 1.00/ngày. Giá token cũng nhập bằng cent trên một triệu token. Ví dụ, giá USD 0.75 và USD 3.75 tương ứng `75` và `375`; đây chỉ là cách quy đổi, hãy dùng đúng giá hiện tại của model/tier bạn chọn.

Nếu AI Studio xác nhận request của bạn thuộc free tier, hai giá token có thể đặt `0`. Trần tiền local khi đó không thay thế quota RPM/TPM/RPD của Google. Dữ liệu free tier có thể có điều khoản xử lý khác paid tier; chỉ dùng premise không nhạy cảm cho prototype.

## 3. Ghi phê duyệt bất biến

Nhấp đúp `Setup-Gemini.cmd` đúng một lần. Lệnh này:

- kiểm tra toàn bộ cấu hình bắt buộc;
- không gọi Gemini và không tiêu quota;
- không lưu API key vào database;
- ghi policy Cloud Boundary cho `synthetic_prompt` và `story_text`;
- kích hoạt model assignment đúng model ID trong `.env`;
- kích hoạt trần chi phí theo ngày Việt Nam.

Các version đã kích hoạt là bất biến. Khi đổi model, giá hoặc policy, hãy đổi tên version (`...-v2`) rồi chạy setup lại; không sửa lịch sử cũ.

## 4. Kiểm tra và chạy

```powershell
python launch_local.py --check
```

Sau đó nhấp đúp `Start-AI-Company.cmd`, tạo một bản nháp từ ý tưởng và bấm **Tạo dàn ý AI thật (dùng quota/chi phí)**. Worker sẽ:

1. kiểm tra policy/model assignment;
2. giữ trước mức chi phí tối đa;
3. gọi Gemini bằng structured JSON;
4. xác thực đúng 20 chapter objectives;
5. ghi usage, latency và actual cost;
6. giải phóng phần tiền giữ dư.

Nếu key sai, quota hết, response sai schema hoặc budget không đủ, task fail-closed và không được xem là nội dung hoàn tất.

## 5. Những giới hạn cần nhớ

- API chỉ bind `127.0.0.1`; không mở port ra LAN/Internet.
- `.env` đã được Git ignore. Luôn kiểm tra `git status` trước khi push.
- Chưa đưa reference video hoặc dữ liệu cá nhân lên provider.
- Model/rate limit có thể thay đổi; kiểm tra AI Studio trước khi tạo version mới.
- Trần local là lớp bảo vệ bổ sung. Nếu bật billing, hãy đặt budget/alert ở tài khoản Google Cloud nữa.
