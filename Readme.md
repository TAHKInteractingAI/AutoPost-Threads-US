# THREADS AUTO POST TOOL (BOT ĐĂNG BÀI TỰ ĐỘNG LÊN THREADS)

Tool tự động hóa việc đăng bài tuyển dụng lên nền tảng Threads. Hoạt động hoàn toàn tự động thông qua cấu hình trên Google Sheet, lưu Cookie và chạy ngầm định kỳ trên GitHub Actions.

## Tính Năng Nổi Bật

- **Quản lý tập trung trên Google Sheet:** Đọc nội dung, link ảnh, thời gian đăng trực tiếp từ Google Sheet.
- **Đăng Bài Kép (Post + Reply):** Hỗ trợ tách nội dung làm bài đăng chính (Job Content) và bình luận phụ (Thread Content) để vượt giới hạn 500 ký tự của Threads.
- **Quản Lý Phiên (Cookie):** Tự động lưu và sử dụng file `storage_state.json` (Cookie) siêu nhẹ để giữ trạng thái đăng nhập, tránh bị Meta nghi ngờ spam.
- **Anti-Spam Cơ Bản:** Gõ phím với tốc độ ngẫu nhiên như người thật, tự động tắt popup quảng cáo/thông báo, khoảng nghỉ ngẫu nhiên giữa các bài đăng.
- **Hỗ Trợ Đám Mây (Cloud Ready):** Tối ưu 100% để chạy ngầm (Headless) trên GitHub Actions với múi giờ Việt Nam.

---

## Tạo Google Sheet đúng cấu trúc

1. Vào [sheets.google.com](https://sheets.google.com) → tạo bảng tính mới
2. Đặt tên tab (sheet con) là: **`AutoPost-Threads`**
3. Điền tiêu đề cột ở **hàng đầu tiên** đúng như sau:

| A       | B         | C        | D     | E              | F      | G       | H               |
| ------- | --------- | -------- | ----- | -------------- | ------ | ------- | --------------- |
| content | image_url | hashtags | topic | scheduled_time | status | post_id | completion_time |

> ⚠️ **Quan trọng:** Phải gõ đúng tên cột, không dấu cách thừa, không viết hoa sai

4. Điền thử 1 bài vào hàng 2

| Cột            | Ví dụ                             | Ghi chú                          |
| -------------- | --------------------------------- | -------------------------------- |
| content        | Bài tuyển dụng của công ty tôi 🔥 | Nội dung bài đăng                |
| image_url      | https://...                       | Link ảnh (để trống nếu không có) |
| hashtags       | #TuyenDung                        | Hashtag                          |
| topic          | Tuyển Dụng HCM                    | **Bắt buộc** — chủ đề Threads    |
| scheduled_time | 03/04/2026 08:00                  | Định dạng dd/mm/yyyy HH:MM       |
| status         | pending                           | Để nguyên chữ này                |

5. Copy **ID của Sheet** từ URL trình duyệt:
   ```
   https://docs.google.com/spreadsheets/d/  👉[COPY_PHẦN_NÀY]👈  /edit
   ```
   Lưu lại, cần dùng sau.

---

## Tạo Google Service Account

1. Vào [console.cloud.google.com](https://console.cloud.google.com)
2. Nhấn **"Select a project"** → **"New Project"** → đặt tên bất kỳ → **"Create"**
3. Vào menu ☰ → **"APIs & Services"** → **"Library"**
4. Tìm **"Google Sheets API"** → nhấn vào → **"Enable"**
5. Tìm **"Google Drive API"** → nhấn vào → **"Enable"**
6. Vào **"APIs & Services"** → **"Credentials"** → **"+ Create Credentials"** → **"Service Account"**
7. Điền tên bất kỳ (vd: `threads-bot`) → **"Create and Continue"** → **"Done"**
8. Nhấn vào service account vừa tạo → tab **"Keys"** → **"Add Key"** → **"Create new key"** → chọn **JSON** → **"Create"**
9. File `credentials.json` tự động tải về máy → **giữ file này, không xóa**

### Chia sẻ Sheet với Service Account

1. Mở file `credentials.json` vừa tải → tìm dòng `"client_email"`:
   ```json
   "client_email": "threads-bot@your-project.iam.gserviceaccount.com"
   ```
2. Copy địa chỉ email đó
3. Mở Google Sheet → nhấn nút **"Share"** (góc trên phải)
4. Dán email vào → chọn quyền **"Editor"** → **"Send"**

---

## LẤY SESSION THREADS

## Cài extension Cookie-Editor trên Chrome

1. Mở Chrome → vào: [chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
2. Nhấn **"Add to Chrome"** → **"Add extension"**

## Xuất cookies từ Threads

1. Vào [threads.com](https://www.threads.com) → **đăng nhập** vào tài khoản của bạn
2. Sau khi đăng nhập xong, nhấn vào icon **Cookie-Editor** trên thanh extension
3. Nhấn nút **"Export"** (góc dưới) → **"Export as JSON"**
4. Mở **Notepad** (Windows) hoặc **TextEdit** (Mac)
5. Nhấn **Ctrl+V** để dán → **Save As** → đặt tên `cookies.json`

## Chuyển cookies thành session file

1. Đặt cookies.json cùng thư mục với script, chạy:

```bash
python get_threads_session.py
```

2. Chuyển file `cookies.json` thành `threads_session.json`
3. Thấy `✅ Tạo session thành công!` -> Tải file xuống.

---

## Lấy base 64

1. Chạy file `encode_secrets.py`

```bash
python encode_secrets.py
```

2. Copy output, sau đó vào:
   **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

3. Thêm 4 secrets:
   | Secret name | Giá trị |
   |---|---|
   | `CREDENTIALS_JSON_B64` | _(output từ encode_secrets.py)_ |
   | `THREADS_SESSION_B64` | _(output từ encode_secrets.py)_ |
   | `SHEET_ID` | `SheetID` |
   | `SHEET_NAME` | `Sheet1` |

---

## Lấy GitHub Personal Access Token

Vào **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**

- **Note:** `cronjob-trigger`
- **Expiration:** No expiration (hoặc 1 năm)
- **Scope:** ✅ `workflow`
  Copy token → lưu lại (chỉ hiện 1 lần).

---

## Thiết lập cronjob.com

Đăng ký tài khoản free tại [cronjob.com](https://cronjob.com), tạo job mới:

**URL:**

```
https://api.github.com/repos/YOUR_USERNAME/threads-bot/actions/workflows/autopost.yml/dispatches
```

**Method:** `POST`

**Headers:**

```
Authorization: Bearer YOUR_GITHUB_TOKEN
Accept: application/vnd.github+json
Content-Type: application/json
```

**Body:**

```json
{ "ref": "main" }
```

**Schedule:** Custom cron:

```
57 19 * * 1,3,5
```

_(19:57 — thứ 2, 4, 6)_

---

## 🔁 Cập nhật session khi hết hạn

Session Threads thường hết hạn sau vài tháng. Khi bot báo lỗi `SESSION_EXPIRED`:

1. Chạy lại login trên máy local để lấy `threads_session.json` mới
2. Chạy lại `python encode_secrets.py`
3. Cập nhật secret `THREADS_SESSION_B64` trên GitHub

---
