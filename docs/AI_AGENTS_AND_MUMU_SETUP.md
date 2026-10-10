# Thiết lập OpenAI/Gemini agent và MuMuAINovel

Hệ thống không thay ChatGPT bằng Gemini. Vai `story_architect` có một provider chính và các provider dự phòng đã được chủ dự án duyệt. Fallback chỉ chạy khi lỗi có thể thử lại (mất kết nối, dịch vụ tạm lỗi, rate/quota limit); lỗi key, policy, schema hoặc nội dung bị từ chối không tự chuyển provider.

## 1. Chọn route agent

Trong `.env`, chọn một trong các cấu hình sau.

OpenAI làm chính, Gemini dự phòng:

```dotenv
AI_COMPANY_REAL_AI_ENABLED=true
AI_COMPANY_STORY_ARCHITECT_PROVIDER=openai
AI_COMPANY_STORY_ARCHITECT_FALLBACKS=gemini

OPENAI_API_KEY=key-openai-cua-ban
OPENAI_MODEL=model-id-chinh-xac
OPENAI_BASE_URL=https://api.openai.com/v1

GEMINI_API_KEY=key-gemini-cua-ban
GEMINI_MODEL=model-id-chinh-xac
```

Chỉ dùng OpenAI thì để `AI_COMPANY_STORY_ARCHITECT_FALLBACKS=`. Chỉ dùng Gemini thì đặt provider chính là `gemini`. Không nhập tên `chatgpt`; provider tự động là `openai`, còn model phải là model ID mà tài khoản API truy cập được.

Với từng provider được đưa vào route, điền rate card, giới hạn output và timeout tương ứng trong `.env`. Giá là **cent USD trên một triệu token**. Sao chép giá hiện tại từ trang chính thức của provider, không dùng số ví dụ cũ.

```dotenv
AI_COMPANY_POLICY_VERSION=story-agents-policy-v1
AI_COMPANY_ASSIGNMENT_VERSION=story-agents-models-v1
AI_COMPANY_BUDGET_VERSION=story-agents-budget-v1
AI_COMPANY_DAILY_BUDGET_MINOR=100
AI_COMPANY_BUDGET_CURRENCY=USD

AI_COMPANY_OPENAI_RATE_CARD_VERSION=ten-va-ngay-rate-card
AI_COMPANY_OPENAI_INPUT_MINOR_PER_MILLION=gia-input
AI_COMPANY_OPENAI_OUTPUT_MINOR_PER_MILLION=gia-output
AI_COMPANY_OPENAI_MAX_OUTPUT_TOKENS=6000
AI_COMPANY_OPENAI_TIMEOUT_SECONDS=60
```

Gemini dùng nhóm biến tương tự đã có trong `.env.example`. Sau khi kiểm tra, chạy `Setup-AI-Agents.cmd` đúng một lần. Khi đổi route/model/giá/policy, tăng cả ba version lên `v2` rồi chạy setup lại; snapshot cũ là bất biến.

Kiểm tra trước khi chạy:

```powershell
python launch_local.py --check
```

Nút **Tạo dàn ý AI thật** trên dashboard sẽ gọi provider chính đã duyệt. Audit của kết quả ghi provider, model và việc có dùng fallback hay không. Mọi lần thử, kể cả fallback, đều qua Cloud Boundary và giữ ngân sách trước khi gọi.

## 2. Cài MuMuAINovel như workspace riêng

MuMuAINovel là ứng dụng viết tiểu thuyết, không phải model provider. Giữ nó thành service riêng để tránh trộn mã GPLv3 và database của hai dự án.

1. Cài Docker Desktop.
2. Clone repository chính thức `https://github.com/xiamuceer-j/MuMuAINovel.git` vào một thư mục ngoài AI Company.
3. Sao chép `backend/.env.example` thành `.env` trong thư mục MuMuAINovel.
4. Đổi `APP_PORT=8800`, đặt mật khẩu PostgreSQL mạnh, bật local auth và đổi username/password mặc định. Vì chạy HTTP local, đặt `SESSION_COOKIE_SECURE=false`.
5. Điền ít nhất một AI provider vào `.env` của MuMuAINovel, rồi chạy `docker compose up -d` theo README upstream.
6. Mở `http://127.0.0.1:8800` và xác nhận đăng nhập được.

Lưu ý: các cuộc gọi model do MuMuAINovel tự thực hiện **không nằm trong budget ledger của AI Company**. Đặt spend limit riêng ở provider hoặc chỉ dùng MuMu để biên tập/viết tiếp sau khi AI Company đã tạo blueprint.

## 3. Nối AI Company với MuMuAINovel

Thêm vào `.env` của AI Company:

```dotenv
MUMUAINOVEL_BASE_URL=http://127.0.0.1:8800
MUMUAINOVEL_USERNAME=ten-local-cua-ban
MUMUAINOVEL_PASSWORD=mat-khau-local-cua-ban
```

Kiểm tra service:

```powershell
python -m ai_company.application.mumu_cli status
```

Sau khi một real blueprint hoàn tất, lấy story ID trên dashboard/API và xuất file tương thích schema MuMuAINovel v1.1.0:

```powershell
python -m ai_company.application.mumu_cli export --story-id STORY_ID --output ".\mumu-project.json"
```

Hoặc đăng nhập local, validate rồi import trực tiếp:

```powershell
python -m ai_company.application.mumu_cli push --story-id STORY_ID --output ".\mumu-project.json"
```

Cầu nối chỉ cho phép `http://127.0.0.1`/`localhost`, không gửi mật khẩu MuMu lên server khác. Nó chuyển title, Story Bible, nhân vật và đúng 20 chapter objectives thành project/characters/outlines; MuMu tiếp tục quản lý quan hệ, chương, ký ức, foreshadow và biên tập.
