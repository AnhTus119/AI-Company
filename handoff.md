# AI Company — handoff cho chat mới

Cập nhật 2026-10-09. Đây là trạng thái **mã và quyết định hiện có**, không phải tuyên bố sản phẩm hoàn tất. Đọc `docs/FINAL_PRODUCT_REQUIREMENTS.md`, `PROJECT_CONTEXT.md` và `docs/PHASE_6_IMPLEMENTATION_STATUS.md` khi tiếp tục; nếu tài liệu cũ mâu thuẫn với quyết định mới bên dưới, ưu tiên quyết định mới và xác minh mã thực tế. Không bịa kết quả kiểm thử hay triển khai.

## Quyết định mới nhất của chủ dự án

- **Hủy hướng web public Vercel/Render.** Mỗi người dùng tải repository về máy Windows của họ, nhấp đúp `Start-AI-Company.cmd`, dùng web ở `http://127.0.0.1:8000/`. Không cần VS Code. Không có màn hình đăng nhập, username hay password. Không expose API ra LAN/Internet.
- Vẫn cần Python 3.12+ trên PATH; launcher tự cài dependency thiếu khi có Internet. Chưa có EXE/installer tự chứa Python. Xem `docs/LOCAL_INSTALL.md` và README. Không tuyên bố “tải repo là chạy được” cho đến khi toàn bộ source được đẩy lên GitHub và thử trên máy mới.
- Chạy bản đầu trên laptop Windows 4 GB RAM của chủ dự án; bộ PC i3-14100F/8 GB trong ảnh là cấu hình kiểm thử đại diện do chủ dự án đưa ra, không phải thống kê thị trường. Ưu tiên Lite. Standard/máy mạnh hơn là mục tiêu sau, cần migration/benchmark trước khi tuyên bố hỗ trợ hoàn chỉnh.
- Mọi model/provider được nhắc đến vẫn là **prototype**. ChatGPT Free chỉ dùng thủ công để so sánh, không phải API tự động; Gemini Pro không tự cấp Gemini API; Muse.ai là công cụ tham khảo chưa xác minh API inference; MuMuAINovel cần review license/kiến trúc trước khi dùng. Chưa có assignment production, key hay AI thật trong luồng web. Chỉ dùng dữ liệu không nhạy cảm khi thử cloud.

## Mục tiêu và phase

- PRD: hệ thống sản xuất drama tiếng Anh dạng local-first, từ ý tưởng/reference/brief tới story gốc 20 chương, hook video 13–17 giây và gói 5 file (`hook.mp4`, `hook.srt`, `story.txt`, `caption.txt`, `comment.txt`). KPI thiết kế 60 gói production-ready/ngày theo giờ Việt Nam; **chưa chứng minh đạt KPI**. Mock không tính production-ready. Con người vẫn duyệt và đăng bài.
- Phase 1–5 đã được chủ dự án duyệt theo tài liệu. Phase 6 đang triển khai; Phase 7–13 chưa hoàn thành. Tài liệu thiết kế ở `docs/PHASE_3_TECHNOLOGY_SELECTION.md`, `docs/PHASE_4_DETAILED_ARCHITECTURE.md`, `docs/PHASE_5_REPOSITORY_DATABASE_DESIGN.md`; model matrix ở `docs/MODEL_ASSIGNMENT_MATRIX.md` chưa chốt production.

## Mã hiện có

- `Start-AI-Company.cmd` gọi `launch_local.py`: cùng Python cho API và worker, cài dependency thiếu, chỉ bind `127.0.0.1`, mở browser, dừng child process khi thoát. FastAPI phục vụ HTML tại `/`; **không còn `/login` hoặc route auth**. Startup chặn môi trường Render/Vercel. HTML cho phép tạo bản nháp `user_idea`, xếp hàng mock blueprint → mock 20 chương → mock package, xem trạng thái và mở/tải 5 file. Worker chạy riêng cùng launcher; đóng tab browser không dừng worker.
- Dữ liệu Lite mặc định dưới `%LOCALAPPDATA%\AIContentCompany` (SQLite WAL + artifacts); không nằm trong ZIP/repo. Code có task bền vững, idempotency, lease/checkpoint, recovery hold, retry gói mock, checksum file, snapshot database Lite thủ công. Backup hiện chỉ gồm database, chưa đầy đủ artifacts/cấu hình.
- Lite schema v2 bổ sung policy/model-assignment snapshot và provider/cost ledger. Provider call phải gắn với task attempt, policy đã duyệt và assignment đã kích hoạt; completion chỉ ghi một lần, không lưu lỗi thô/credential. Migration PostgreSQL tương ứng là `0002_governance_ledgers`.
- Lite schema v3 bổ sung budget policy theo ngày, reservation trước provider call và settlement sau usage thật. Gemini REST adapter + `real_blueprint` task bị tắt mặc định; `docs/GEMINI_PROTOTYPE_SETUP.md` và `Setup-Gemini.cmd` là đường bật có phê duyệt. Luồng thật hiện dừng ở Story Bible/20-chapter plan/Hook Contract, chưa viết chapter body.
- MP4 mock là tệp kỹ thuật hợp lệ 15 giây 720×1280 với caption/âm giả lập; text/chapter/blueprint cũng giả lập. Không có real AI/content/media provider hoạt động, không có automatic publishing, không có dashboard duyệt/khôi phục đầy đủ. Standard PostgreSQL/RabbitMQ là hướng thiết kế, chưa xác minh end-to-end hoặc chuyển dữ liệu.
- Trước lần đổi hướng này, bài HTTP API+worker process riêng từng đạt trên laptop 4 GB với đủ RAM. Sau khi gỡ auth/public, lượt chạy lại ngày 2026-10-09 bị skip vì RAM khả dụng dưới ngưỡng 768 MB trong tiến trình test; cần chạy lại khi đủ RAM và xác nhận nhấp đúp thật trên máy chủ dự án. **Không suy ra web đang chạy từ unit tests**.

## Repository và việc cần làm tiếp

- Repository được người dùng cung cấp: `https://github.com/AnhTus119/AI-Company.git`. Lần kiểm tra trước, nhánh `main` trên GitHub chỉ có README; source local chưa được push và local chưa có Git remote, mọi file dự án đang untracked. **Không có URL web public.** Trước khi người khác Download ZIP được bản chạy, cần kiểm tra `.gitignore`/secret rồi đưa mã lên repo, xác minh file thực sự xuất hiện trên GitHub. Không tự tuyên bố đã push.
- Ưu tiên: (1) người dùng nhấp đúp launcher, kiểm tra trang và một luồng mock trên máy thật; (2) push source lên GitHub khi sẵn sàng, thử trên Windows sạch không VS Code; (3) tiếp tục lát cắt AI thật có giới hạn theo Cloud Boundary/assignment/budget/audit; (4) hoàn thiện backup/restore, giao diện review/recovery, QC và Standard/migration sau.
- Không hỏi API key cho luồng mock. Khi thử Gemini API thật, người dùng tự tạo key và đặt vào secret local, không gửi key vào chat hoặc commit. Không chốt model production dựa trên demo.

## Kiểm chứng và an toàn

- Sau provider/budget increment: `python -m pytest -q --basetemp=.pytest-run` đạt **52 passed, 1 skipped** ngày 2026-10-09. `python launch_local.py --check` và provider-setup smoke test không gọi mạng đều đạt. Test HTTP process riêng là opt-in (`AI_COMPANY_RUN_HTTP_INTEGRATION=1`); lần chạy lại bị skip vì RAM khả dụng dưới ngưỡng 768 MB, không phải pass. Khởi động qua launcher và Gemini call đầu tiên trên máy thật vẫn cần người dùng xác nhận.
- Vì không có login, bất kỳ tiến trình/người nào trên cùng máy có thể gọi localhost API. Không dùng dữ liệu nhạy cảm, không mở port 8000 ra ngoài. Việc bỏ auth chỉ phù hợp hướng local theo yêu cầu hiện tại; không tái dùng bản này để public nếu chưa thiết kế bảo mật mới.
