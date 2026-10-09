# Cài AI Company Lite trên Windows

**Quyết định hiện tại:** chạy web trên chính máy người dùng qua `http://127.0.0.1:8000/`; không dùng Vercel/Render, không có đăng nhập. Đây vẫn là bản thử mock, chưa sản xuất nội dung bằng AI thật.

## Cần chuẩn bị một lần

1. Máy Windows 10/11, RAM tối thiểu 4 GB cho bản thử; nên còn ít nhất 1 GB RAM khả dụng trước khi dựng video mock. Trên máy nhiều RAM hơn, ứng dụng sẽ có thêm khoảng trống vận hành, nhưng chưa có benchmark/auto-tuning hoàn chỉnh.
2. Cài Python 3.12 trở lên từ nguồn chính thức. Khi cài, chọn **Add Python to PATH**. Không cần VS Code.
3. Tải *đầy đủ mã nguồn* từ GitHub bằng **Code → Download ZIP**, giải nén vào thư mục dễ tìm. Hiện repository GitHub của dự án chưa có đủ mã nguồn, nên bước này chỉ dùng được sau khi chủ dự án đẩy các file local lên. Không tải riêng mỗi README.
4. Lần đầu cần Internet để launcher cài các thư viện Python còn thiếu. Về sau không cần nhập lệnh, trừ khi cần sửa lỗi/cập nhật.

## Mỗi lần sử dụng

Nhấp đúp `Start-AI-Company.cmd` trong thư mục đã giải nén. Giữ cửa sổ đen mở. Trình duyệt sẽ tự mở; nếu không, vào `http://127.0.0.1:8000/`. Không có màn hình đăng nhập; không cần API key cho luồng mock. Để dừng, quay lại cửa sổ và nhấn `Ctrl+C` (hoặc đóng cửa sổ).

Nếu báo thiếu Python, cài Python 3.12+ và bật PATH rồi mở lại. Nếu báo cài thư viện thất bại, giữ nguyên cửa sổ và chụp lỗi ở phía trên; kiểm tra Internet và dung lượng đĩa. Nếu port 8000 bị chiếm bởi phiên bản cũ, đóng cửa sổ ứng dụng cũ trước khi mở lại. Không cần chạy riêng `uvicorn` hoặc worker.

## Dữ liệu và giới hạn

Mặc định cơ sở dữ liệu và tệp xuất nằm trong `%LOCALAPPDATA%\AIContentCompany` trên *từng máy*, không đồng bộ qua GitHub/ZIP. Thay source bằng bản mới không tự chuyển hay sao lưu dữ liệu. Có lệnh sao lưu riêng database Lite trong README; nó chưa gồm toàn bộ media. Hãy dùng dữ liệu không nhạy cảm trong bản thử.

Ứng dụng chỉ lắng nghe `127.0.0.1`; người khác cần tải và chạy bản riêng trên máy của họ. Không mở port ra Internet/LAN: bản này cố ý không có đăng nhập. Hướng public hosting trước đây đã bị hủy. Để người dùng có thể chạy hoàn toàn không cần cài Python, cần một bản đóng gói EXE/installer riêng; hiện chưa có.
