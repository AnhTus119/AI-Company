# Thiết lập OpenAI/Gemini agent và MuMuAINovel

Hệ thống không thay ChatGPT bằng Gemini. Các vai `story_architect`, `chapter_writer`, `editor` và `continuity_qc` đều có provider chính và các provider dự phòng đã được chủ dự án duyệt. Fallback chỉ chạy khi lỗi có thể thử lại (mất kết nối, dịch vụ tạm lỗi, rate/quota limit); lỗi key, policy, schema hoặc nội dung bị từ chối không tự chuyển provider.

## 1. Chọn route agent

Trong `.env`, chọn một trong các cấu hình sau.

Model mặc định đã được điền trong `.env.example` theo tài liệu chính thức ngày 2026-10-10:

- OpenAI: `gpt-6.1-sol`, cân bằng chất lượng/chi phí cho production qua Responses API.
- Gemini: `gemini-3.8-flash`, model Flash stable hiện hành.

Giá trong file mẫu là bảng giá standard tại ngày ghi trong `RATE_CARD_VERSION`; luôn đối chiếu lại trước khi duyệt vì provider có thể đổi giá.

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

Ba vai viết chương mặc định kế thừa route trên. Nếu muốn phân vai, thêm các dòng sau; để trống nghĩa là kế thừa Story Architect:

```dotenv
AI_COMPANY_CHAPTER_WRITER_PROVIDER=gemini
AI_COMPANY_CHAPTER_WRITER_FALLBACKS=openai
AI_COMPANY_EDITOR_PROVIDER=openai
AI_COMPANY_EDITOR_FALLBACKS=gemini
AI_COMPANY_CONTINUITY_QC_PROVIDER=openai
AI_COMPANY_CONTINUITY_QC_FALLBACKS=gemini
```

Ví dụ này để Gemini viết nháp, còn OpenAI biên tập và kiểm tra continuity. Chỉ các provider xuất hiện trong route mới cần key/model/rate card.

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

Gemini dùng nhóm biến tương tự đã có trong `.env.example`. Sau khi kiểm tra, chạy `Setup-AI-Agents.cmd` đúng một lần. Khi đổi route/model/giá/policy, tăng cả ba version sang một tên chưa từng dùng (ví dụ `v2`, rồi `v3`) trước khi chạy setup lại; snapshot cũ là bất biến.

Trước khi duyệt snapshot, có thể chạy `Test-AI-Providers.cmd`. Lệnh này chỉ gọi endpoint metadata model để xác nhận key được chấp nhận và model nhìn thấy được; nó không gửi premise/chương và không lưu key. `Setup-AI-Agents.cmd` cũng tự chạy kiểm tra này trước khi ghi approval.

Kiểm tra trước khi chạy:

```powershell
python launch_local.py --check
```

Nút **Tạo dàn ý AI thật** trên dashboard sẽ gọi provider chính đã duyệt. Sau khi tạo Novel Workspace, nút viết chương chạy tuần tự `chapter_writer → editor → continuity_qc`. Nút **Tự chạy ... đến chương 20** dùng các task nhỏ nối tiếp nhau, nên từng chương vẫn có lease, budget reservation và provider audit riêng. Chuỗi tự dừng nếu QC không đạt, hết ngân sách hoặc provider lỗi. Chỉ khi QC trả về `passed=true` thì chương đã biên tập mới được lưu; nếu không, draft vẫn nằm trong checkpoint task với trạng thái `needs_revision`.

## Lấy key còn thiếu

- Gemini: vào [Google AI Studio API Keys](https://aistudio.google.com/app/apikey), tạo key trong project của bạn, rồi paste vào `GEMINI_API_KEY` trong `.env`. Nên dùng auth key/restricted key dành riêng cho Gemini API.
- OpenAI: đăng nhập [OpenAI Platform API Keys](https://platform.openai.com/api-keys), tạo project key mới, lưu ngay khi key được hiển thị và paste vào `OPENAI_API_KEY` trong `.env`. Gói ChatGPT và OpenAI API là hai sản phẩm/billing riêng; dùng ChatGPT trên web không tự cấp API key hoặc API credit.

Không paste key vào chat, GitHub, `.env.example` hoặc ảnh chụp màn hình. Nếu một key từng bị lộ, revoke key đó và tạo key mới.

## 2. Novel Workspace native không cần đăng nhập

AI Company đã có workspace native riêng cho Story Bible, nhân vật, 20 outline, chapter draft, continuity/open loops và foreshadow. Sau khi real blueprint hoàn tất, bấm **Tạo Novel Workspace local** trên dashboard. Phần này chạy trong SQLite/API local, không yêu cầu username/password và không phụ thuộc MuMuAINovel. Xem [Novel Workspace](NATIVE_NOVEL_WORKSPACE.md).

## 3. Tùy chọn: cài MuMuAINovel như workspace riêng

MuMuAINovel là ứng dụng viết tiểu thuyết, không phải model provider. Giữ nó thành service riêng để tránh trộn mã GPLv3 và database của hai dự án.

1. Cài Docker Desktop.
2. Clone repository chính thức `https://github.com/xiamuceer-j/MuMuAINovel.git` vào một thư mục ngoài AI Company.
3. Sao chép `backend/.env.example` thành `.env` trong thư mục MuMuAINovel.
4. Đổi `APP_PORT=8800`, đặt mật khẩu PostgreSQL mạnh, bật local auth và đổi username/password mặc định. Vì chạy HTTP local, đặt `SESSION_COOKIE_SECURE=false`.
5. Điền ít nhất một AI provider vào `.env` của MuMuAINovel, rồi chạy `docker compose up -d` theo README upstream.
6. Mở `http://127.0.0.1:8800` và xác nhận đăng nhập được.

Lưu ý: các cuộc gọi model do MuMuAINovel tự thực hiện **không nằm trong budget ledger của AI Company**. Đặt spend limit riêng ở provider hoặc chỉ dùng MuMu để biên tập/viết tiếp sau khi AI Company đã tạo blueprint.

## 4. Tùy chọn: nối AI Company với MuMuAINovel

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
