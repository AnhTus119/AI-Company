# Thiết lập GPT-5.6-Terra và MuMuAINovel

Runtime hiện khóa duy nhất OpenAI `gpt-5.6-terra` qua Responses API. Gemini và fallback đa provider không còn được dùng. ChatGPT trên web và OpenAI API là hai sản phẩm/billing riêng; tài khoản ChatGPT không tự cấp API credit.

## 1. Lấy OpenAI API key

1. Mở https://platform.openai.com/api-keys và đăng nhập OpenAI Platform.
2. Tạo Project API key, lưu key ngay khi nó xuất hiện.
3. Kiểm tra Billing/Limits của project. Không paste key vào chat, GitHub, `.env.example` hoặc ảnh chụp.
4. Chỉ paste key vào `OPENAI_API_KEY=` trong file `.env` cục bộ.

## 2. Cấu hình `.env` thủ công

Sao chép các giá trị không bí mật từ `.env.example` vào `.env` và giữ key chỉ ở `.env`:

```dotenv
AI_COMPANY_REAL_AI_ENABLED=true
AI_COMPANY_LITE_CONCURRENCY=2
AI_COMPANY_STORY_ARCHITECT_PROVIDER=openai
AI_COMPANY_STORY_ARCHITECT_FALLBACKS=

OPENAI_API_KEY=key-cua-ban
OPENAI_MODEL=gpt-5.6-terra
OPENAI_BASE_URL=https://api.openai.com/v1

AI_COMPANY_POLICY_VERSION=story-agents-policy-v2-terra-only
AI_COMPANY_ASSIGNMENT_VERSION=story-agents-models-v2-terra-only
AI_COMPANY_BUDGET_VERSION=story-agents-budget-v2-terra-only
AI_COMPANY_DAILY_BUDGET_MINOR=500
AI_COMPANY_BUDGET_CURRENCY=USD

AI_COMPANY_OPENAI_RATE_CARD_VERSION=gpt-5.6-terra-standard-2026-10-10
AI_COMPANY_OPENAI_INPUT_MINOR_PER_MILLION=200
AI_COMPANY_OPENAI_OUTPUT_MINOR_PER_MILLION=1200
AI_COMPANY_OPENAI_MAX_OUTPUT_TOKENS=6000
AI_COMPANY_OPENAI_TIMEOUT_SECONDS=60
AI_COMPANY_OPENAI_SERVICE_TIER=default

AI_COMPANY_CHAPTER_PIPELINE_MODE=fast
AI_COMPANY_STORY_ARCHITECT_REASONING_EFFORT=low
AI_COMPANY_CHAPTER_WRITER_REASONING_EFFORT=none
AI_COMPANY_EDITOR_REASONING_EFFORT=none
AI_COMPANY_CONTINUITY_QC_REASONING_EFFORT=low
```

`fast` dùng một provider call cho mỗi chương nhưng vẫn yêu cầu schema và `passed=true`; `quality` dùng ba call độc lập writer/editor/QC. `AI_COMPANY_LITE_CONCURRENCY=2` xử lý tối đa hai story cùng lúc. Nếu máy thiếu RAM hoặc gặp SQLite contention, giảm về `1`; không tăng quá `4`.

`AI_COMPANY_OPENAI_SERVICE_TIER=fast` chỉ được bật sau khi bạn thay rate card bằng bảng giá Fast đã kiểm tra và tên version chứa `fast`. Hệ thống cố ý từ chối Fast với bảng giá standard để không âm thầm đánh giá thiếu chi phí.

## 3. Duyệt cấu hình và chạy

Mỗi khi đổi model, giá, policy hoặc route, dùng ba version hoàn toàn mới. Sau đó:

```powershell
python launch_local.py --check
Test-AI-Providers.cmd
Setup-AI-Agents.cmd
Start-AI-Company.cmd
```

Lệnh test provider chỉ kiểm tra key/model visibility, không gửi story. Setup ghi policy, assignment và budget đã duyệt. Dashboard cho chọn `manual` hoặc `auto`; auto chỉ có hiệu lực khi package thật vượt đủ gate.

## 4. Video thật hiện chưa được tích hợp

`gpt-5.6-terra` nhận text/image và trả text; nó không tạo video. Hệ thống hiện chỉ có `hook.mp4` mock để kiểm tra pipeline, không được tính production-ready. Muốn hook video thật phải chọn thêm một video provider/model riêng, rồi triển khai adapter, job polling/download, cost ledger, continuity QC và license/provenance. Điều này không thể đồng thời thỏa điều kiện “chỉ dùng một model GPT-5.6-Terra”.

## 5. MuMuAINovel là tùy chọn, không phải model provider

Core Novel Workspace lưu Story Bible, nhân vật, outline, chapter, continuity/open loops và foreshadow trong SQLite local, không cần đăng nhập.

MuMuAINovel chỉ là workspace riêng tùy chọn. AI Company không sao chép code GPLv3 upstream và không phụ thuộc vào nó. Nếu dùng, chạy service ở localhost, đặt `MUMUAINOVEL_BASE_URL`, username/password trong `.env`, rồi dùng:

```powershell
python -m ai_company.application.mumu_cli status
python -m ai_company.application.mumu_cli export --story-id STORY_ID --output ".\mumu-project.json"
python -m ai_company.application.mumu_cli push --story-id STORY_ID --output ".\mumu-project.json"
```

Các call model do MuMu tự chạy không nằm trong budget ledger của AI Company; nên dùng MuMu chủ yếu để xem/biên tập project đã xuất.
