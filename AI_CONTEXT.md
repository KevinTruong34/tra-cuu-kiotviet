# AI_CONTEXT.md — Watch Store Management App

## 1. Tổng quan & Stack Công nghệ

**Mục tiêu dự án:** App nội bộ quản lý cửa hàng đồng hồ (3 chi nhánh) — dần thay thế KiotViet. Quy mô nhỏ: vài nhân viên, 1 developer (owner + AI assist).

**Stack:**
- **Frontend/Backend:** Streamlit (Python), deploy trên Streamlit Community Cloud
- **Database:** Supabase (PostgreSQL) qua supabase-py REST client
- **Auth:** bcrypt hash password, session token UUID lưu URL query params (`?token=xxx&branch=yyy`), expire 3 ngày
- **Dependencies:** `streamlit, pandas, plotly, supabase, bcrypt, openpyxl`

**3 Chi nhánh:** `100 Lê Quý Đôn`, `Coop Vũng Tàu`, `GO BÀ RỊA` (hardcode trong `ALL_BRANCHES`, có `CN_SHORT` map tên ngắn).

**3 Role:** `admin` (toàn quyền), `ke_toan` (xem nhiều CN), `nhan_vien` (chỉ CN của mình).

## 2. Cấu trúc Thư mục
app.py              # Single-file ~3000 dòng, chứa toàn bộ logic
requirements.txt    # Dependencies (đã làm sạch các lib cookie đã thất bại)
CLAUDE.md           # Behavioral guidelines: think-before-code, simplicity, surgical changes
## 3. Trạng thái Hiện tại

**Bảng Supabase đang dùng:**
- `nhan_vien` — user + bcrypt password + role
- `nhan_vien_chi_nhanh` — junction table user ↔ CN
- `chi_nhanh` — danh sách CN (nhưng app vẫn đọc từ `ALL_BRANCHES` hardcode)
- `sessions` — token + expire
- `hang_hoa` — master sản phẩm (upload 1 lần từ KiotViet)
- `the_kho` — snapshot tồn (upload định kỳ từ KiotViet)
- `hoa_don` — hóa đơn bán (upload từ KiotViet, có 4 cột phương thức TT)
- `phieu_chuyen_kho` — vừa chứa phiếu KiotViet (prefix `TRF...`) vừa phiếu App (prefix `CH000001`...). Có column `nguoi_nhan` (mới thêm). UNIQUE INDEX trên `(ma_phieu, ma_hang)`.

**Module đã chạy mượt:**
- Đăng nhập + chọn CN (URL-based session)
- Hóa đơn: search theo SĐT/mã/ngày, hiện 6 HĐ gần nhất khi chưa tìm, admin có filter CN, hiện phương thức thanh toán
- Hàng hóa: bảng + detail card, highlight CN hiện tại
- Chuyển hàng: tạo/sửa/xác nhận/nhận/hủy phiếu App, mã serial `CH000001...` (retry nếu race), validate tồn trước submit, form người nhận + checkbox xác nhận, giỏ hàng scroll khi >3 items
- Quản trị (admin only): Upload 4 loại file KiotViet, Xóa dữ liệu, Quản lý nhân viên, banner nhắc kết sổ khi phiếu App cũ >30 ngày

**Logic delta tồn kho quan trọng:**
- Phiếu App (`loai_phieu = "Chuyển hàng (App)"`) sinh delta động lên snapshot `the_kho`:
  - Phiếu tạm/Đã hủy: delta=0
  - Đang chuyển: −SL tại nguồn
  - Đã nhận: −SL nguồn, +SL đích
- Nút "Kết sổ" trong Quản trị chuyển `loai_phieu` → `"Chuyển hàng (App - đã đồng bộ)"` → ngừng tính delta (sau khi upload the_kho mới từ KiotViet).
- Logic `_apply_delta` biết tự tạo dòng mới trong DataFrame khi (mã, CN đích) chưa có trong the_kho.

**Logging:** `log_action(action, detail, level)` ghi stdout với prefix `[user@CN]`. Actions: LOGIN_OK/FAIL, LOGOUT, PHIEU_CREATE/UPDATE/CONFIRM/RECEIVE/CANCEL/ARCHIVE/RESTORE, STOCK_VALIDATION_FAIL, UPLOAD_*, DATA_DELETE.

## 4. Quy ước Code

**Behavioral (CLAUDE.md) — bắt buộc mọi phiên:**
1. Think before coding, surface assumptions
2. Simplicity first — minimum code, không over-engineer
3. Surgical changes — chỉ sửa cái user yêu cầu, không refactor tự ý
4. Goal-driven với verify steps

**Tech conventions:**
- **Secret management:** Supabase URL + key qua `st.secrets` (không hardcode)
- **Error handling:** Database errors wrap trong `try/except`, hiển thị user-friendly qua `st.error()`, log detail qua `_logger`
- **Cache:** `@st.cache_data(ttl=N)` cho data loading; clear bằng `st.cache_data.clear()` sau mutation
- **Comment tiếng Việt** cho business logic, tiếng Anh cho technical
- **Session state:** dùng cho state ngắn hạn trong session; **URL params** cho state persist qua F5 (token, branch)
- **Không dùng `st.dialog`** (compatibility issues) — thay bằng inline form với `session_state` flag

**Vietnamese UX:** toàn bộ UI + error messages tiếng Việt. User không technical.

## 5. Vấn đề Đang kẹt

**KHÔNG có blocker hiện tại.** Phiên làm việc kết thúc với **mọi tính năng chạy mượt** sau khi fix critical bug về delta tồn kho (CN đích không nhận hàng khi mã hàng chưa từng có ở đó).

**Technical debt cần dọn sau (không gấp):**
- `DEBT-01`: 4 phiếu format cũ chưa migrate (CH260417...), regex SQL không đủ rộng. Low priority — test data, sẽ xóa khi go-live.
- `DEBT-02`: Upload chuyển hàng gọi `df['Mã chuyển hàng'].nunique()` TRƯỚC khi check column → KeyError khó hiểu nếu sai file. Chỉ cần swap thứ tự.
- `DEBT-03`: `hien_thi_dashboard()` orphan sau khi xóa tab Doanh số. Giữ để tái dùng khi làm module Báo cáo.

**Roadmap dài hạn đã thống nhất (thay thế KiotViet từng bước):**
1. **Module Kiểm kê** (ưu tiên cao) — quét mã vạch 2D USB (keyboard emulator), pattern `on_change` + auto-focus JS
2. **Module Nhập hàng + NCC**
3. **Module Bán hàng (POS)** — TÁCH RA APP STREAMLIT RIÊNG để cache/tốc độ không đụng nhau, nhưng dùng chung Supabase DB
4. **Sổ quỹ, Cân bằng kho, Báo cáo**

**User preferences quan trọng:**
- Giao tiếp trực tiếp, pushback khi cần
- Mobile-first (Edge trên điện thoại)
- Ghét over-engineer; khi sửa lỗi đẻ ra vấn đề mới → dừng lại, note lại để giải quyết sau
