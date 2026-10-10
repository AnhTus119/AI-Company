# AI Content Company

Hệ thống sản xuất nội dung drama tiếng Anh trên máy Windows, hiện ở **Phase 6 — MVP implementation**. Lát cắt thật hiện tạo được Story Bible và 20 chương; hook video/media thật và đóng gói production vẫn là phần còn thiếu.

## Mở bản thử trên Windows

Trên Windows, cài Python 3.12 trở lên (chọn **Add Python to PATH**), tải đủ mã nguồn, rồi nhấp đúp [Start-AI-Company.cmd](Start-AI-Company.cmd). Giữ cửa sổ đó mở; trình duyệt sẽ mở `http://127.0.0.1:8000/`. Không cần VS Code, tài khoản, mật khẩu hay API key cho đường thử mock. Lần đầu launcher có thể tự cài thư viện qua Internet; các lần sau chỉ cần nhấp đúp file. Nếu trình duyệt không tự mở, nhập địa chỉ localhost trên. Xem [hướng dẫn cài đặt chi tiết](docs/LOCAL_INSTALL.md).

Hướng Vercel/Render đã **hủy**. Đây là web **chạy trên từng máy**, chỉ lắng nghe `127.0.0.1`, không phải website public. Người khác muốn dùng cần tải mã nguồn về máy Windows của họ. Mã local chưa được đẩy đầy đủ lên [repository GitHub](https://github.com/AnhTus119/AI-Company.git), nên chưa thể chỉ tải repository hiện có rồi chạy.

## Đã có

- Quy tắc vòng đời story, 20 chương tuần tự, các gate bắt buộc và điều kiện ghi nhận `production_ready`.
- Kiểm soát nhận việc theo mục tiêu ngày, hàng chờ duyệt, khả năng xử lý an toàn và ngân sách.
- Quy tắc Cloud Boundary và assignment model đã duyệt. Runtime hiện khóa duy nhất OpenAI `gpt-5.6-terra`; cấu hình model/provider khác bị từ chối.
- Bản ghi policy/model-assignment bất biến cùng sổ provider/cost gắn với task attempt; mọi provider thật bị chặn cho đến khi route và ngân sách được duyệt.
- Các vai `story_architect`, `chapter_writer`, `editor` và `continuity_qc` dùng OpenAI Responses API. Mỗi lần gọi giữ ngân sách riêng và ghi provider/model. Chế độ `fast` gộp writer → editor → QC vào một structured response (20 call/truyện thay vì 60); chế độ `quality` giữ ba call độc lập. Chỉ chương vượt QC mới được lưu. Hai worker Lite mặc định có thể xử lý hai story song song, trong giới hạn RAM/budget.
- Campaign có `approval_mode=manual|auto`. `manual` là mặc định; `auto` chỉ tự duyệt sau khi story đã vượt toàn bộ production gate và artifact thật đã được xác minh.
- Novel Workspace native lưu Story Bible, nhân vật, 20 outline, chapter drafts, continuity/open loops và foreshadow ngay trong SQLite local; không có đăng nhập/đăng ký và dùng optimistic version để chống ghi đè. Xem [Novel Workspace](docs/NATIVE_NOVEL_WORKSPACE.md).
- Cầu nối MuMuAINovel được giữ như integration tùy chọn để export/push project v1.1.0. Core không phụ thuộc vào MuMu; code GPLv3 của upstream không được sao chép vào repo này. Xem [hướng dẫn agent và MuMuAINovel](docs/AI_AGENTS_AND_MUMU_SETUP.md).
- Hai profile dùng chung logic: `lite` dùng SQLite cục bộ trên máy 4 GB; `standard` dành cho PostgreSQL/RabbitMQ khi máy có đủ tài nguyên.
- Các bảng đầu tiên cùng migration PostgreSQL, repository và API tạo campaign/story nháp, xem story, duyệt story đã sẵn sàng.
- Task bền vững với idempotency key, lease, checkpoint và trạng thái chờ xác nhận sau gián đoạn; đã có lõi worker Lite thăm dò database, nhưng chưa nối thành tiến trình vận hành với các handler sản xuất story.
- Đường thử offline đã nối API command handler → blueprint giả lập → 20 chương giả lập tuần tự qua các task và checkpoint bền vững. Đây là dữ liệu kiểm tra quy trình, không phải nội dung sản xuất và không thể tăng Production KPI.
- Có lệnh chụp bản sao database Lite nhất quán, kiểm tra tính toàn vẹn và từ chối ghi đè file cũ. Đây chưa phải bản backup đầy đủ của media và cấu hình.
- Đã nối đường thử offline qua task xuất gói: bốn file chữ giả lập và `hook.mp4` hợp lệ (15 giây, 720×1280, phụ đề gắn vào hình, âm báo giả lập), lưu đúng năm file trong `MOCK_OUTPUT`. Có kiểm tra media/checksum và thử chạy lại không ghi đè. Đây chỉ là gói kỹ thuật mock, chưa phải story/media dùng để xuất bản.
- Test domain, database, task, cấu hình profile, governance ledger và API command handlers. SQLite WAL, nâng schema và claim tranh chấp đã được kiểm thử; PostgreSQL/RabbitMQ thật chưa được xác minh.

## Chạy test hiện tại

Với Python có các dependency trong `pyproject.toml`:

```powershell
python -m pytest -q --basetemp=.pytest-run
```

## Chạy thử trên máy 4 GB (profile `lite`)

1. Dùng launcher phía trên. Nếu muốn cài thủ công để phát triển/test, cài dependency bằng đúng Python sẽ chạy app: `python -m pip install -e ".[dev,media]"`. Phần `media` dùng Pillow và imageio-ffmpeg để tạo video mock cục bộ.
2. Để `AI_COMPANY_PROFILE=lite` hoặc không đặt biến này. Database mặc định nằm dưới thư mục dữ liệu ứng dụng cục bộ (`LOCALAPPDATA` trên Windows), ngoài thư mục OneDrive của repository.
3. Launcher sẽ mở cả API và worker. Nếu chạy API thủ công, dùng `python -m uvicorn ai_company.api.main:create_app --factory --host 127.0.0.1 --port 8000` để chắc chắn không gọi nhầm Python. Schema Lite ban đầu được tạo khi mở API lần đầu.

Profile `standard` sẽ dùng PostgreSQL/RabbitMQ khi các adapter và kiểm thử tích hợp hoàn tất. Việc đổi profile sau này cần quy trình chuyển dữ liệu đã kiểm chứng; chỉ đổi biến môi trường sẽ không tự chuyển lịch sử story.

API hiện chỉ nhận story nháp kiểu `user_idea`. Launcher tự chạy worker thử nghiệm; người phát triển có thể chạy riêng bằng `python -m ai_company.worker.mock_cli --loop`. Nó tự hoãn nếu RAM trống quá thấp. Gọi các route lần lượt: `POST /stories/{id}/mock-blueprint`, sau khi xong gọi `POST /stories/{id}/mock-chapters`, rồi `POST /stories/{id}/mock-package`; mỗi bước dùng `GET` tương ứng để xem trạng thái task. Bước xuất video đòi ít nhất 768 MB RAM khả dụng và mặc định lưu dưới thư mục dữ liệu ứng dụng (`artifacts/MOCK_OUTPUT`); có thể đổi gốc lưu bằng `ARTIFACT_ROOT`. Các chế độ reference, autonomous, dashboard đầy đủ và media thật vẫn đang được triển khai. Chưa có route nào cho phép bỏ qua gate để đánh dấu `production_ready`.

Giao diện vận hành Lite ở `http://127.0.0.1:8000/` khi launcher đang chạy. Tại đây có thể chọn duyệt thủ công/tự động, tạo bản nháp từ ý tưởng, tạo dàn ý AI thật, materialize Novel Workspace và chạy từng chương hoặc tự chạy đến chương 20. Nhánh mock vẫn hỗ trợ dàn ý → 20 chương → gói 5 tệp để kiểm tra kỹ thuật. Launcher chạy worker riêng; đóng trình duyệt không dừng worker.

Nếu task xuất gói mock báo `technical_failure`, người vận hành có thể gọi `POST /stories/{id}/mock-package/{task_id}/retry` rồi chạy worker lại. Lệnh này chỉ hoạt động khi còn lượt thử trong giới hạn đã lưu (hiện tối đa hai lượt cho gói mock); nó không tự thử lại, không ghi đè gói đã xuất và không áp dụng cho task/model thật.

Bài kiểm thử HTTP qua API và worker ở các tiến trình riêng nằm trong `tests/test_http_process_integration.py`. Toàn bộ đường thử blueprint → chương → video → gói 5 file đã qua trên máy 4 GB ngày 2026-10-09. Test chỉ chạy khi đặt `AI_COMPANY_RUN_HTTP_INTEGRATION=1` và còn ít nhất 768 MB RAM khả dụng; ở mức thấp hơn nó tự bỏ qua. Môi trường sandbox có thể chặn kết nối loopback, nên bài kiểm thử HTTP cần quyền chạy cục bộ phù hợp.

Để lưu một bản sao database Lite sau khi đã tạo, chạy `python -m ai_company.application.backup_cli "D:\backup\state-2026-10-09.sqlite3"` với thư mục đích có sẵn và tên file mới. Thay đường dẫn ví dụ bằng vị trí của bạn; bản sao có thể chứa ý tưởng/story nên cần lưu ở nơi bạn tin cậy.

Thông tin yêu cầu sản phẩm ở [PRD](docs/FINAL_PRODUCT_REQUIREMENTS.md); cấu hình theo máy ở [Resource Profiles](docs/RESOURCE_PROFILES.md); tiến độ ở [Phase 6 status](docs/PHASE_6_IMPLEMENTATION_STATUS.md); kiểm soát an toàn khi code ở [Phase 6 checklist](docs/PHASE_6_SAFE_CODE_CHECKLIST.md).
