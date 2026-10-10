# Novel Workspace cục bộ — không đăng nhập

AI Company có workspace tiểu thuyết native chạy ngay trong API local `127.0.0.1`. Phần này được triển khai độc lập; không sao chép source code GPLv3 của MuMuAINovel và không yêu cầu tài khoản, đăng ký, cookie hay mật khẩu.

## Phạm vi hiện tại

Sau khi real blueprint hoàn tất, bấm **Tạo Novel Workspace local** trên dashboard. Workspace lưu bền vững trong SQLite và gồm:

- Story Bible và Hook Contract;
- nhân vật cùng trạng thái hiện tại;
- đúng 20 chapter outlines;
- chapter draft, summary, trạng thái review và word count;
- continuity notes, timeline notes và open loops;
- foreshadow đã cài cùng chapter dự kiến payoff;
- provenance của provider/model đã tạo blueprint.

Mỗi workspace có `row_version`. Khi ghi chapter hoặc foreshadow, client phải gửi version vừa đọc. Nếu một thao tác khác đã cập nhật trước, hệ thống từ chối ghi và yêu cầu reload, tránh mất dữ liệu.

## API local

```text
POST /stories/{story_id}/novel-workspace
GET  /stories/{story_id}/novel-workspace
PUT  /stories/{story_id}/novel-workspace/chapters/{chapter_number}
POST /stories/{story_id}/novel-workspace/foreshadows
```

Ví dụ lưu chapter:

```json
{
  "expected_version": 1,
  "title": "The Letter",
  "content": "Chapter text...",
  "summary": "Mara discovers the letter.",
  "status": "reviewed",
  "continuity_notes": ["Mara now distrusts Eli."],
  "new_open_loops": ["Why was the seal broken?"],
  "close_open_loops": []
}
```

## Quan hệ với MuMuAINovel

MuMuAINovel vẫn là một integration tùy chọn nếu cần giao diện và hệ sinh thái riêng của họ. Khi dùng upstream nguyên bản, API import yêu cầu session đăng nhập local. AI Company core không còn phụ thuộc vào integration đó; bridge export/push được giữ riêng và không chạy mặc định.

Các bước tiếp theo cho workspace native là nối chapter-writer/editor/QC agents, bổ sung màn hình biên tập chapter và thao tác resolve foreshadow. Các bước này vẫn phải qua model assignment, Cloud Boundary, budget và audit hiện có.
