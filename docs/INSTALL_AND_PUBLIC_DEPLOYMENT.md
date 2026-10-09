# Cài đặt và hướng public domain

**Trạng thái 2026-10-09:** Bản Lite/mock đã chạy cục bộ trên Windows 4 GB. Hướng public domain đã được chọn, nhưng **chưa được triển khai công khai**. Đăng nhập localhost có đúng hai tài khoản `Tou` và `Chibun`; mật khẩu demo chung do chủ dự án chọn nằm trong `.env` cục bộ bị Git bỏ qua, và file xác thực lưu hash ngoài repository. Mật khẩu thử nghiệm ngắn không phù hợp Internet. Dữ liệu/file hiện cũng nằm trên máy chạy.

API prototype hiện chỉ chấp nhận hostname `localhost`/`127.0.0.1` và cố ý không khởi động khi phát hiện môi trường Render/Vercel. Đây là chốt chặn triển khai nhầm. Chủ dự án yêu cầu public với mật khẩu demo rất ngắn và chấp nhận rủi ro bị người lạ đăng nhập; yêu cầu đó **chưa được triển khai**. Trước khi có URL public, tối thiểu vẫn phải chọn hạ tầng/lưu trữ dữ liệu, cấu hình HTTPS cookie và kiểm thử luồng đăng nhập; không thể lấy URL thật chỉ bằng cách đổi một dòng cấu hình.

## Dùng ngay trên máy của bạn (Windows)

1. Mở thư mục `AI Company`, nhấp đúp `Start-AI-Company.cmd`. Trên máy hiện tại file `.env` đã chứa mật khẩu demo; máy mới cần tự tạo `.env` từ `.env.example` và đặt `AI_COMPANY_DEMO_PASSWORD` trước khi mở launcher.
2. Giữ cửa sổ vừa mở. Trình duyệt mở `http://127.0.0.1:8000/` (nếu không tự mở, bấm đường dẫn này), rồi đăng nhập bằng một trong hai tài khoản.
3. Nhập ý tưởng **không nhạy cảm** và bấm các bước mock. Bản này không dùng model thật, không cần API key.
4. Muốn dừng: vào cửa sổ launcher và nhấn `Ctrl+C`. Lần sau chỉ cần nhấp đúp file đó.

Launcher dùng cùng một Python cho web và worker, tránh lỗi `pip` chạy Python 3.14 nhưng lệnh `uvicorn.exe` trên PATH lại thuộc Python 3.11. Nếu thiếu thư viện, nó thử cài bằng chính Python đang chạy. Nếu máy chưa có Python 3.12+, cần cài Python trước. Có thể kiểm tra mà không mở web bằng `python launch_local.py --check`.

Nếu thích dùng một lệnh thay vì nhấp đúp: chạy `python launch_local.py` từ thư mục dự án. Không dùng lệnh `uvicorn` đứng riêng vì PATH có thể trỏ nhầm Python.

## macOS / Linux (chưa kiểm thử trên máy thật)

Từ thư mục dự án, cài Python 3.12+ rồi chạy `python3 launch_local.py`. Launcher sẽ thử cài thư viện còn thiếu. Nếu hệ điều hành không cho `pip` cài trực tiếp vào Python hệ thống, tạo môi trường riêng một lần: `python3 -m venv .venv`, kích hoạt bằng `source .venv/bin/activate`, chạy `python -m pip install -e ".[media]"`; các lần sau trong môi trường đó chạy `python launch_local.py`. Các hệ này vẫn cần bài kiểm thử và bộ cài trước khi hứa hỗ trợ chính thức.

## Từ bản local tới web public

Hướng triển khai đã chọn là **Vercel cho frontend**, **Render cho API và worker**, cơ sở dữ liệu PostgreSQL bền vững, và kho file bền vững cho video/gói xuất. Đây là hướng kiến trúc, chưa phải nút Deploy hoạt động. Render có web service/worker; Vercel Python chạy dưới dạng Functions nên không phù hợp để giữ worker SQLite-polling liên tục của bản hiện tại. [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [Render service types](https://render.com/docs/service-types).

**Thực tế repository hiện tại:** Trang điều hành HTML đang được FastAPI phục vụ trực tiếp, chưa có frontend riêng để Vercel build. Repository GitHub do chủ dự án cung cấp hiện chỉ chứa `README.md`; source local chưa được đẩy lên. Không nên tạo Vercel project với repo đó rồi kỳ vọng có web hoạt động. Bước đầu hợp lý là xác nhận local, đưa source không chứa secret lên GitHub, chọn lưu trữ, triển khai API/web hiện có trên Render và kiểm thử; sau đó mới tách frontend cho Vercel theo kiến trúc đã chọn.

**Ràng buộc Free/always-on được xác minh ngày 2026-10-09:** Render Free tự ngủ sau 15 phút không có yêu cầu HTTP/WebSocket; không có cấu hình Free bảo đảm server không bao giờ ngủ. Có thể khởi động lại khi có truy cập nhưng lần đầu có thể chờ khoảng một phút; Render còn có thể restart dịch vụ Free. Vercel Hobby Cron chỉ chạy tối đa một lần/ngày, không phải cơ chế giữ Render thức. Vì vậy yêu cầu "mọi thứ Free" cùng "server Render không bao giờ ngủ" hiện không thể cam kết. [Render Free](https://render.com/docs/free), [Vercel Hobby Cron](https://vercel.com/docs/cron-jobs/manage-cron-jobs).

Các điều kiện bắt buộc trước khi public:

1. Củng cố đăng nhập, cookie HTTPS, chống CSRF, giới hạn tần suất bền vững và kiểm thử trước khi Internet có thể truy cập API. Chỉ giữ hai tài khoản đã chốt. Mật khẩu hiện tại yếu; user yêu cầu giữ nguyên, nên nếu triển khai theo yêu cầu phải ghi nhận rủi ro và không mô tả hệ thống là an toàn.
2. Chuyển SQLite local sang PostgreSQL bằng migration có kiểm chứng và backup/restore. Render Free web mất file/SQLite khi restart hoặc sleep; Free Postgres hết hạn sau 30 ngày, không có backup. Không chọn nó làm nơi lưu dữ liệu quan trọng. [Render Free limitations](https://render.com/docs/free).
3. Tách worker và kho media khỏi web frontend; lưu video/gói xuất vào object storage hoặc đĩa bền vững phù hợp. Render mặc định dùng filesystem tạm. [Render deploy/storage](https://render.com/docs/deploys).
4. Thêm giới hạn ngân sách, Cloud Boundary và phê duyệt model trước khi gọi AI thật; chạy thử private/staging trước public.
5. Kết nối repository GitHub với Vercel/Render, cấu hình tên miền riêng (nếu muốn) và HTTPS; chỉ nhập secret vào trang Environment của nhà cung cấp, không đưa vào GitHub hay trình duyệt. [Render environment secrets](https://render.com/docs/configure-environment-variables), [Vercel environment variables](https://vercel.com/docs/environment-variables).

Vercel/Render cung cấp subdomain để thử; tên miền riêng là tùy chọn và sẽ cần bạn quản lý DNS. Chi phí, giới hạn và tính sẵn có phải kiểm tra lại ở thời điểm triển khai. Hiện **không cần** mua domain hay cung cấp API key để chạy local; máy mới chỉ cần đặt mật khẩu demo trong `.env` riêng.

## Thông tin/khóa sẽ cần theo từng giai đoạn

| Giai đoạn | Cần từ bạn | Ghi chú |
|---|---|---|
| Local hiện tại | Mật khẩu demo trong `.env` riêng; không có API key | Chạy offline/mock; ý tưởng thử nên không nhạy cảm. Mật khẩu thử nghiệm chỉ dùng với localhost. |
| Public hạ tầng | Tài khoản GitHub, Vercel, Render; lựa chọn domain nếu muốn | Database URL, session secret, object-storage credentials là secret triển khai, chỉ tạo khi kiến trúc public đã sẵn sàng. |
| Gemini API thật (tùy chọn) | `GEMINI_API_KEY` từ Google AI Studio, sau khi bạn duyệt adapter/dữ liệu được gửi | Gemini API có Free Tier cho một số model/giới hạn; gói Gemini Pro cho người dùng không tự đồng nghĩa với quyền API. [Google API keys](https://ai.google.dev/gemini-api/docs/api-key), [billing](https://ai.google.dev/gemini-api/docs/billing). |
| OpenAI API thật (tùy chọn) | `OPENAI_API_KEY` và ngân sách API riêng, chỉ sau khi bạn duyệt | Không yêu cầu để chạy mock. API key phải ở server, không trong frontend. ChatGPT Free/Plus không tự biến thành API key. Một luồng Sign in with ChatGPT cho người dùng đủ điều kiện là tích hợp riêng, không có sẵn trong dự án. [OpenAI API authentication](https://developers.openai.com/api/reference/overview), [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart). |
| Muse.ai / MuMuAINovel | Chưa yêu cầu khóa | Chỉ thu thập khi có adapter cụ thể và xác minh API/quyền sử dụng. MuMuAINovel là ứng dụng có thể dùng khóa của các provider nền như OpenAI/Gemini; không mặc định cần một “MuMu API key” cho hệ thống này. [MuMuAINovel README](https://github.com/xiamuceer-j/MuMuAINovel/blob/main/README.md). |

**Không gửi API key, mật khẩu, cookie đăng nhập hoặc chuỗi kết nối database vào chat.** Khi tới bước kết nối thật, nhập chúng trực tiếp vào phần cấu hình bí mật trên máy hoặc dịch vụ triển khai. Mỗi provider vẫn là lựa chọn prototype, chưa chốt cố định.
