import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime, timedelta
import numpy as np
import bcrypt
import uuid

# ==========================================
# PHIEN BAN: 11.0.0 — Multi-user + Chi nhánh
# ==========================================

st.set_page_config(page_title="Hệ thống Watch Store", layout="wide")

st.markdown("""
    <style>
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    #stDecoration {display:none !important;}
    .stAppDeployButton {display:none !important;}
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    .block-container {padding-top: 1rem !important; padding-bottom: 0rem !important;}
    [data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    [data-testid="stMetricLabel"] {font-size: 0.9rem !important; color: gray;}
    [data-testid="stElementToolbar"] {display: none !important;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# SUPABASE INIT
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Chưa cấu hình SUPABASE_URL và SUPABASE_KEY trong Streamlit Secrets!")
    st.stop()

ALL_BRANCHES = ["100 Lê Quý Đôn", "Coop Vũng Tàu", "GO BÀ RỊA"]


# ==========================================
# AUTH HELPERS
# ==========================================

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_session_token(nhan_vien_id: int) -> str:
    token = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
    supabase.table("sessions").insert({
        "token": token,
        "nhan_vien_id": nhan_vien_id,
        "expires_at": expires_at
    }).execute()
    return token

def delete_session(token: str):
    supabase.table("sessions").delete().eq("token", token).execute()

def load_nhan_vien_by_id(nv_id: int):
    res = supabase.table("nhan_vien").select("*").eq("id", nv_id).eq("active", True).execute()
    if not res.data:
        return None
    user = res.data[0]
    user.pop("mat_khau", None)  # không giữ hash trong session
    # Lấy danh sách chi nhánh
    cn_res = supabase.table("nhan_vien_chi_nhanh") \
        .select("chi_nhanh_id, chi_nhanh(ten)") \
        .eq("nhan_vien_id", nv_id).execute()
    user["chi_nhanh_list"] = [item["chi_nhanh"]["ten"] for item in cn_res.data] if cn_res.data else []
    return user

def restore_session_from_token(token: str):
    """Validate token trong DB và khôi phục user session."""
    try:
        res = supabase.table("sessions") \
            .select("nhan_vien_id, expires_at") \
            .eq("token", token).execute()
        if not res.data:
            return None
        session = res.data[0]
        expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if expires.replace(tzinfo=None) < datetime.utcnow():
            delete_session(token)
            return None
        return load_nhan_vien_by_id(session["nhan_vien_id"])
    except Exception:
        return None

def do_login(username: str, password: str):
    """Trả về (user_dict, error_str)."""
    try:
        res = supabase.table("nhan_vien") \
            .select("*").eq("username", username).eq("active", True).execute()
        if not res.data:
            return None, "Tài khoản không tồn tại hoặc đã bị khóa."
        user = res.data[0]
        if not verify_password(password, user["mat_khau"]):
            return None, "Mật khẩu không chính xác."
        user.pop("mat_khau", None)
        cn_res = supabase.table("nhan_vien_chi_nhanh") \
            .select("chi_nhanh_id, chi_nhanh(ten)") \
            .eq("nhan_vien_id", user["id"]).execute()
        user["chi_nhanh_list"] = [item["chi_nhanh"]["ten"] for item in cn_res.data] if cn_res.data else []
        return user, None
    except Exception as e:
        return None, f"Lỗi hệ thống: {e}"

def do_logout():
    token = st.query_params.get("token")
    if token:
        delete_session(token)
    st.session_state.clear()
    st.query_params.clear()

# ==========================================
# HELPERS TRUY XUẤT USER HIỆN TẠI
# ==========================================

def get_user():
    return st.session_state.get("user")

def is_admin():
    u = get_user()
    return u and u.get("role") == "admin"

def is_ke_toan_or_admin():
    u = get_user()
    return u and u.get("role") in ("admin", "ke_toan")

def get_branches():
    """Danh sách chi nhánh user được phép xem."""
    u = get_user()
    if not u:
        return []
    if u.get("role") == "admin":
        return ALL_BRANCHES
    return u.get("chi_nhanh_list", [])


# ==========================================
# FIRST RUN SETUP (nếu chưa có nhân viên nào)
# ==========================================

def is_first_run() -> bool:
    try:
        res = supabase.table("nhan_vien").select("id", count="exact").execute()
        return (res.count or 0) == 0
    except Exception:
        return False

def show_first_run():
    st.title("🛠️ Khởi tạo hệ thống lần đầu")
    st.info("Chưa có tài khoản nào. Hãy tạo tài khoản **Admin** của bạn để bắt đầu.")
    with st.form("form_setup"):
        username = st.text_input("Username (ID đăng nhập):")
        ho_ten = st.text_input("Họ tên:")
        pwd = st.text_input("Mật khẩu:", type="password")
        pwd2 = st.text_input("Xác nhận mật khẩu:", type="password")
        submitted = st.form_submit_button("🚀 Tạo tài khoản Admin", type="primary")
        if submitted:
            if not all([username, ho_ten, pwd, pwd2]):
                st.error("Vui lòng điền đầy đủ.")
            elif pwd != pwd2:
                st.error("Mật khẩu xác nhận không khớp.")
            elif len(pwd) < 6:
                st.error("Mật khẩu tối thiểu 6 ký tự.")
            else:
                try:
                    hashed = hash_password(pwd)
                    supabase.table("nhan_vien").insert({
                        "username": username,
                        "ho_ten": ho_ten,
                        "mat_khau": hashed,
                        "role": "admin",
                        "active": True
                    }).execute()
                    st.success(f"✅ Tạo tài khoản Admin **{ho_ten}** thành công! Hãy đăng nhập.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")


# ==========================================
# LOGIN PAGE
# ==========================================

def show_login():
    st.title("🔐 Đăng nhập hệ thống")
    with st.form("login_form"):
        username = st.text_input("Tài khoản:")
        password = st.text_input("Mật khẩu:", type="password")
        submitted = st.form_submit_button("Đăng nhập", type="primary", use_container_width=True)
        if submitted:
            if not username or not password:
                st.error("Vui lòng nhập đầy đủ tài khoản và mật khẩu.")
            else:
                with st.spinner("Đang xác thực..."):
                    user, err = do_login(username, password)
                if err:
                    st.error(err)
                else:
                    token = create_session_token(user["id"])
                    st.session_state["user"] = user
                    st.query_params["token"] = token
                    st.rerun()


# ==========================================
# SESSION RESTORE (chạy mỗi lần load trang)
# ==========================================

if "user" not in st.session_state:
    token = st.query_params.get("token")
    if token:
        user = restore_session_from_token(token)
        if user:
            st.session_state["user"] = user
        else:
            st.query_params.clear()

# ==========================================
# ROUTING: FIRST RUN → LOGIN → APP
# ==========================================

if "user" not in st.session_state:
    if is_first_run():
        show_first_run()
    else:
        show_login()
    st.stop()


# ==========================================
# DATA LOADING (filtered by branch)
# ==========================================

@st.cache_data(ttl=300)
def load_hoa_don(branches_key: tuple = None):
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        q = supabase.table("hoa_don").select("*")
        if branches_key:
            q = q.in_("Chi nhánh", list(branches_key))
        res = q.range(offset, offset + batch - 1).execute()
        rows = res.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    tong = len(df)
    df = df.drop_duplicates()
    st.session_state["so_dong_trung"] = tong - len(df)

    for col in ["Tổng tiền hàng", "Khách cần trả", "Khách đã trả", "Đơn giá", "Thành tiền"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "Thời gian" in df.columns:
        df["_ngay"] = pd.to_datetime(df["Thời gian"], format="%d/%m/%Y %H:%M", errors="coerce")
        if df["_ngay"].isna().all():
            df["_ngay"] = pd.to_datetime(df["Thời gian"], dayfirst=True, errors="coerce")
        df["_date"] = df["_ngay"].dt.date
    return df

@st.cache_data(ttl=300)
def load_the_kho(branches_key: tuple = None):
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        q = supabase.table("the_kho").select("*")
        if branches_key:
            q = q.in_("Chi nhánh", list(branches_key))
        res = q.range(offset, offset + batch - 1).execute()
        rows = res.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    for col in ["Tồn đầu kì", "Giá trị đầu kì", "Nhập NCC", "Giá trị nhập NCC",
                "Xuất bán", "Giá trị xuất bán", "Tồn cuối kì", "Giá trị cuối kì"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ==========================================
# MODULE 0: TỔNG QUAN
# ==========================================

def module_tong_quan():
    user = get_user()
    branches = get_branches()
    st.markdown(f"### 👋 Xin chào, **{user.get('ho_ten', '')}**!")
    tag_cn = "  ".join([f"`{b}`" for b in branches])
    role_label = {"admin": "👑 Admin", "ke_toan": "📊 Kế toán", "nhan_vien": "👤 Nhân viên"}.get(user.get("role"), "")
    st.caption(f"{role_label}   |   Chi nhánh: {tag_cn}")
    st.markdown("---")
    if is_ke_toan_or_admin():
        hien_thi_dashboard()
    else:
        st.info("🚧 Trang tổng quan nhân viên đang phát triển — sẽ hiển thị doanh số cá nhân trong ngày.")


# ==========================================
# DASHBOARD DOANH SỐ
# ==========================================

def hien_thi_dashboard():
    branches = get_branches()
    try:
        raw = load_hoa_don(branches_key=tuple(branches))
        if raw.empty or "_date" not in raw.columns:
            st.info("💡 Chưa có dữ liệu hóa đơn.")
            return

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        first_of_month = today.replace(day=1)
        first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)
        last_of_last_month = first_of_month - timedelta(days=1)

        col_filter, _ = st.columns([2, 3])
        with col_filter:
            ky_chon = st.selectbox("Kỳ xem:",
                ["Hôm nay", "Hôm qua", "7 ngày qua", "Tháng này", "Tháng trước"],
                index=3, label_visibility="collapsed")

        if ky_chon == "Hôm nay":
            date_from, date_to = today, today
            compare_from, compare_to = yesterday, yesterday
            label_ss = "so với hôm qua"
        elif ky_chon == "Hôm qua":
            date_from, date_to = yesterday, yesterday
            day_before = yesterday - timedelta(days=1)
            compare_from, compare_to = day_before, day_before
            label_ss = "so với hôm kia"
        elif ky_chon == "7 ngày qua":
            date_from = today - timedelta(days=6)
            date_to = today
            compare_from = today - timedelta(days=13)
            compare_to = today - timedelta(days=7)
            label_ss = "so với 7 ngày trước đó"
        elif ky_chon == "Tháng này":
            date_from, date_to = first_of_month, today
            compare_from = first_of_last_month
            try:
                compare_to = first_of_last_month.replace(day=today.day)
            except ValueError:
                compare_to = last_of_last_month
            label_ss = "so với cùng kỳ tháng trước"
        else:
            date_from, date_to = first_of_last_month, last_of_last_month
            m2_first = (first_of_last_month - timedelta(days=1)).replace(day=1)
            m2_last = first_of_last_month - timedelta(days=1)
            compare_from, compare_to = m2_first, m2_last
            label_ss = "so với tháng trước nữa"

        ht = raw[raw["Trạng thái"] == "Hoàn thành"].copy()
        df_ky  = ht[(ht["_date"] >= date_from)    & (ht["_date"] <= date_to)]
        df_ss  = ht[(ht["_date"] >= compare_from)  & (ht["_date"] <= compare_to)]
        df_today = ht[ht["_date"] == today]
        df_yest  = ht[ht["_date"] == yesterday]

        def tinh(df_in):
            if df_in.empty:
                return 0, 0
            u = df_in.drop_duplicates(subset=["Mã hóa đơn"], keep="first")
            return u["Khách đã trả"].sum(), u["Mã hóa đơn"].nunique()

        def pct(moi, cu):
            return ((moi - cu) / cu * 100) if cu else None

        dt_today, hd_today = tinh(df_today)
        dt_yest,  _        = tinh(df_yest)
        dt_ky,    hd_ky    = tinh(df_ky)
        dt_ss,    _        = tinh(df_ss)

        p_yest    = pct(dt_today, dt_yest)
        p_compare = pct(dt_ky, dt_ss)

        st.markdown("#### Kết quả bán hàng hôm nay")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("💰 Doanh thu hôm nay", f"{dt_today:,.0f}")
            st.caption(f"{hd_today} hóa đơn")
        with m2:
            st.metric("🔄 Trả hàng", "0")
        with m3:
            if p_yest is not None:
                st.metric("So hôm qua", f"{'↑' if p_yest>=0 else '↓'} {abs(p_yest):.1f}%")
            else:
                st.metric("So hôm qua", "—")
        with m4:
            if p_compare is not None:
                st.metric(label_ss.capitalize(), f"{'↑' if p_compare>=0 else '↓'} {abs(p_compare):.1f}%")
            else:
                st.metric(label_ss.capitalize(), "—")

        st.markdown(f"**Doanh thu thuần kỳ này: {dt_ky:,.0f} đ** ({hd_ky} hóa đơn)")

        if not df_ky.empty:
            base = df_ky.drop_duplicates(subset=["Mã hóa đơn"], keep="first")
            chart = base.groupby(["_date", "Chi nhánh"])["Khách đã trả"].sum().reset_index()
            chart.columns = ["Ngày", "Chi nhánh", "Doanh thu"]
            pivot = chart.pivot_table(index="Ngày", columns="Chi nhánh", values="Doanh thu", fill_value=0).sort_index()

            color_map = {
                "100 Lê Quý Đôn": "#2E86DE",
                "Coop Vũng Tàu":   "#27AE60",
                "GO BÀ RỊA":       "#F39C12",
            }
            fallback = ["#2E86DE", "#27AE60", "#F39C12", "#E74C3C", "#9B59B6"]
            fig = go.Figure()
            for i, cn in enumerate(pivot.columns):
                fig.add_trace(go.Bar(
                    x=[d.strftime("%d") for d in pivot.index],
                    y=pivot[cn],
                    name=cn,
                    marker_color=color_map.get(cn, fallback[i % len(fallback)]),
                    hovertemplate=f"{cn}<br>Ngày %{{x}}<br>%{{y:,.0f}} đ<extra></extra>",
                ))
            fig.update_layout(
                barmode="stack", height=400,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
                yaxis=dict(tickformat=",.0f", gridcolor="#eee"),
                xaxis=dict(title=None, dtick=1),
                plot_bgcolor="white", font=dict(size=12), dragmode=False,
            )
            max_val = pivot.sum(axis=1).max() if not pivot.empty else 0
            if max_val >= 1_000_000:
                step = max(6_000_000, int(max_val / 8) // 1_000_000 * 1_000_000)
                tick_vals = list(range(0, int(max_val + step), step))
                tick_text = [f"{int(v/1_000_000)} tr" for v in tick_vals]
                fig.update_layout(yaxis=dict(tickvals=tick_vals, ticktext=tick_text, gridcolor="#eee"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Không có dữ liệu trong kỳ này.")

    except Exception as e:
        st.error(f"Lỗi dashboard: {e}")


# ==========================================
# MODULE 1: HÓA ĐƠN
# ==========================================

def module_hoa_don():
    def show_invoice(inv_df, code):
        row = inv_df.iloc[0]
        status = row.get("Trạng thái", "N/A")
        bg = "#28a745" if status == "Hoàn thành" else "#dc3545"
        header = f"🧾 **{code}** — {row.get('Thời gian','')} | **{row.get('Tên khách hàng','Khách lẻ')}** ({row.get('Điện thoại','N/A')})"
        with st.expander(header, expanded=True):
            st.markdown(f"""<div style="display:flex;justify-content:flex-end;margin-top:-40px;">
                <span style="background:{bg};color:white;padding:4px 15px;border-radius:20px;font-weight:bold;font-size:.85rem;">{status}</span>
            </div>""", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("Tổng tiền hàng", f"{row.get('Tổng tiền hàng',0):,.0f} đ")
            c2.metric("Thực tế trả",    f"{row.get('Khách đã trả',0):,.0f} đ")
            cols = ["Mã hàng", "Tên hàng", "Số lượng", "Đơn giá", "Thành tiền", "Ghi chú hàng hóa"]
            dv = inv_df[[c for c in cols if c in inv_df.columns]].copy()
            for c in ["Đơn giá", "Thành tiền"]:
                if c in dv.columns:
                    dv[c] = dv[c].apply(lambda x: f"{x:,.0f} đ")
            with st.expander("📋 Chi tiết hàng hóa", expanded=False):
                st.dataframe(dv, use_container_width=True, hide_index=True)

    def show_list(res):
        active   = res[res["Trạng thái"] != "Đã hủy"]
        canceled = res[res["Trạng thái"] == "Đã hủy"]
        for code in active["Mã hóa đơn"].unique():
            show_invoice(active[active["Mã hóa đơn"] == code], code)
        if not canceled.empty:
            n = canceled["Mã hóa đơn"].nunique()
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"🗑️ Hóa đơn Đã hủy ({n})", expanded=False):
                for code in canceled["Mã hóa đơn"].unique():
                    show_invoice(canceled[canceled["Mã hóa đơn"] == code], code)

    try:
        branches = get_branches()
        raw = load_hoa_don(branches_key=tuple(branches))
        if raw.empty:
            st.info("💡 Chưa có dữ liệu hóa đơn.")
            return

        list_cn = [cn for cn in raw["Chi nhánh"].dropna().unique() if cn in branches]
        sel_cn  = st.multiselect("Chi nhánh:", options=list_cn, default=list_cn)

        if st.session_state.get("so_dong_trung", 0) > 0:
            st.warning(f"⚠️ Phát hiện {st.session_state['so_dong_trung']} dòng trùng lặp đã được lọc.")

        data = raw[raw["Chi nhánh"].isin(sel_cn)].copy()
        data["SĐT_Search"] = data["Điện thoại"].fillna("").str.replace(r"\D+", "", regex=True)

        t1, t2, t3 = st.tabs(["📞 Số điện thoại", "🧾 Mã Hóa Đơn", "📅 Ngày tháng"])

        with t1:
            phone = st.text_input("Nhập số điện thoại:", key="in_phone")
            if phone:
                res = data[data["SĐT_Search"].str.contains(phone.replace(" ", ""), na=False)]
                if not res.empty:
                    st.info(f"Khách hàng: **{res.iloc[0].get('Tên khách hàng','Khách lẻ')}**")
                    show_list(res)
                else:
                    st.warning("Không tìm thấy số điện thoại.")

        with t2:
            inv = st.text_input("Nhập mã (Ví dụ: 1007 hoặc HD011007):", key="in_inv")
            if inv:
                res = data[data["Mã hóa đơn"].str.upper().str.endswith(inv.strip().upper(), na=False)]
                if not res.empty:
                    show_list(res)
                else:
                    st.warning("Không tìm thấy mã hóa đơn.")

        with t3:
            date_str = st.text_input("Nhập ngày/tháng (Ví dụ: 14/04/2026):", key="in_date")
            if date_str:
                res = data[data["Thời gian"].astype(str).str.contains(date_str.strip(), na=False)]
                if not res.empty:
                    st.success(f"Tìm thấy {res['Mã hóa đơn'].nunique()} hóa đơn.")
                    show_list(res)
                else:
                    st.warning("Không có dữ liệu trong ngày này.")

    except Exception as e:
        st.error(f"Lỗi tải Hóa đơn: {e}")


# ==========================================
# MODULE 2: THẺ KHO
# ==========================================

def module_the_kho():
    try:
        branches = get_branches()
        data = load_the_kho(branches_key=tuple(branches))
        if data.empty:
            st.info("💡 Chưa có dữ liệu thẻ kho.")
            return
        ma = st.text_input("🔍 Nhập Mã hàng hóa (Ví dụ: CASIO-01):").strip().upper()
        if ma:
            res = data[data["Mã hàng"].str.upper().str.contains(ma, na=False)]
            if not res.empty:
                st.success(f"Tìm thấy **{len(res)}** dòng — **{res.iloc[0].get('Tên hàng', ma)}**")
                cols = ["Chi nhánh", "Mã hàng", "Tên hàng", "Tồn đầu kì", "Nhập NCC",
                        "Xuất bán", "Tồn cuối kì", "Giá trị cuối kì"]
                cols = [c for c in cols if c in res.columns]
                dv = res[cols].copy()
                for c in ["Giá trị cuối kì", "Giá trị đầu kì"]:
                    if c in dv.columns:
                        dv[c] = dv[c].apply(lambda x: f"{x:,.0f} đ")
                st.dataframe(dv, use_container_width=True, hide_index=True)
            else:
                st.warning("Không tìm thấy mã hàng này.")
    except Exception as e:
        st.error(f"Lỗi tải Thẻ kho: {e}")


# ==========================================
# MODULE QUẢN LÝ NHÂN VIÊN
# ==========================================

def module_nhan_vien():
    st.markdown("### 👥 Quản lý nhân viên")

    # Load chi nhánh
    try:
        cn_res = supabase.table("chi_nhanh").select("*").eq("active", True).execute()
        cn_map = {cn["ten"]: cn["id"] for cn in cn_res.data} if cn_res.data else {}
    except Exception as e:
        st.error(f"Lỗi tải chi nhánh: {e}")
        return

    tab_add, tab_list = st.tabs(["➕ Thêm nhân viên", "📋 Danh sách"])

    with tab_add:
        with st.form("form_them_nv", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_user = st.text_input("Username:")
                new_name = st.text_input("Họ tên:")
                new_role = st.selectbox("Role:", ["nhan_vien", "ke_toan", "admin"])
            with c2:
                new_pwd  = st.text_input("Mật khẩu:", type="password")
                new_pwd2 = st.text_input("Xác nhận MK:", type="password")
                new_cns  = st.multiselect("Chi nhánh phụ trách:", list(cn_map.keys()))

            if st.form_submit_button("➕ Tạo tài khoản", type="primary"):
                if not all([new_user, new_name, new_pwd, new_pwd2]):
                    st.error("Điền đầy đủ thông tin.")
                elif new_pwd != new_pwd2:
                    st.error("Mật khẩu xác nhận không khớp.")
                elif len(new_pwd) < 6:
                    st.error("Mật khẩu tối thiểu 6 ký tự.")
                elif not new_cns and new_role != "admin":
                    st.error("Chọn ít nhất một chi nhánh.")
                else:
                    try:
                        res = supabase.table("nhan_vien").insert({
                            "username": new_user,
                            "ho_ten":   new_name,
                            "mat_khau": hash_password(new_pwd),
                            "role":     new_role,
                            "active":   True,
                        }).execute()
                        nv_id = res.data[0]["id"]
                        for cn in new_cns:
                            supabase.table("nhan_vien_chi_nhanh").insert({
                                "nhan_vien_id": nv_id,
                                "chi_nhanh_id": cn_map[cn]
                            }).execute()
                        st.success(f"✅ Tạo tài khoản **{new_name}** thành công!")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

    with tab_list:
        try:
            nv_res = supabase.table("nhan_vien").select("*").order("id").execute()
            nv_list = nv_res.data or []
            current_user = get_user()

            for nv in nv_list:
                cn_res2 = supabase.table("nhan_vien_chi_nhanh") \
                    .select("chi_nhanh(ten)").eq("nhan_vien_id", nv["id"]).execute()
                cn_names = [x["chi_nhanh"]["ten"] for x in cn_res2.data] if cn_res2.data else []

                icon_active = "🟢" if nv["active"] else "🔴"
                icon_role   = {"admin": "👑", "ke_toan": "📊", "nhan_vien": "👤"}.get(nv["role"], "👤")
                is_self     = (nv["id"] == current_user.get("id"))

                with st.expander(
                    f"{icon_active} {icon_role} **{nv['ho_ten']}** — `{nv['username']}`"
                    + (" *(bạn)*" if is_self else "")
                ):
                    col_info, col_pwd, col_act = st.columns([2, 2, 1])
                    with col_info:
                        st.caption(f"Role: **{nv['role']}**")
                        st.caption(f"Chi nhánh: {', '.join(cn_names) if cn_names else '—'}")
                        # Đổi role
                        new_role = st.selectbox(
                            "Đổi role:", ["nhan_vien", "ke_toan", "admin"],
                            index=["nhan_vien","ke_toan","admin"].index(nv["role"]),
                            key=f"role_{nv['id']}"
                        )
                        if st.button("💾 Lưu role", key=f"sr_{nv['id']}"):
                            supabase.table("nhan_vien").update({"role": new_role}).eq("id", nv["id"]).execute()
                            st.success("Đã cập nhật role!")
                            st.rerun()
                    with col_pwd:
                        np_ = st.text_input("Mật khẩu mới:", type="password", key=f"np_{nv['id']}")
                        if st.button("🔑 Đổi MK", key=f"sp_{nv['id']}"):
                            if np_ and len(np_) >= 6:
                                supabase.table("nhan_vien").update(
                                    {"mat_khau": hash_password(np_)}
                                ).eq("id", nv["id"]).execute()
                                st.success("Đã đổi mật khẩu!")
                            else:
                                st.warning("Mật khẩu tối thiểu 6 ký tự.")
                    with col_act:
                        if not is_self:  # Không tự khóa mình
                            btn_lbl = "🔒 Khóa" if nv["active"] else "🔓 Mở khóa"
                            if st.button(btn_lbl, key=f"tog_{nv['id']}"):
                                supabase.table("nhan_vien") \
                                    .update({"active": not nv["active"]}) \
                                    .eq("id", nv["id"]).execute()
                                st.rerun()
                        else:
                            st.caption("*(tài khoản của bạn)*")
        except Exception as e:
            st.error(f"Lỗi tải danh sách: {e}")


# ==========================================
# MODULE 3: QUẢN TRỊ
# ==========================================

def module_quan_tri():
    if not is_admin():
        st.error("⛔ Bạn không có quyền truy cập trang này.")
        return

    tab_ds, tab_up, tab_del, tab_nv = st.tabs([
        "📊 Doanh số", "📤 Upload", "🗑️ Xóa dữ liệu", "👥 Nhân viên"
    ])

    with tab_ds:
        hien_thi_dashboard()

    with tab_up:
        sub_kho, sub_hd = st.tabs(["📦 Thẻ kho", "🧾 Hóa đơn"])

        with sub_kho:
            st.markdown("**Hướng dẫn:** Tải file **Xuất nhập tồn chi tiết** từ KiotViet (`.xlsx`).")
            uploaded = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_kho")
            if uploaded:
                try:
                    df = pd.read_excel(uploaded)
                    st.success(f"Đọc được **{len(df)}** dòng, **{len(df.columns)}** cột")
                    missing = [c for c in ["Mã hàng","Tên hàng","Chi nhánh","Tồn cuối kì"] if c not in df.columns]
                    if missing:
                        st.error(f"Thiếu cột: {', '.join(missing)}")
                    else:
                        st.info(f"Chi nhánh: {', '.join(df['Chi nhánh'].unique())} — {len(df)} dòng")
                        with st.expander("👁️ Xem trước"):
                            st.dataframe(df.head(), use_container_width=True, hide_index=True)
                        if st.button("🚀 Upload Thẻ kho", key="btn_up_kho", type="primary"):
                            with st.spinner("Đang xử lý..."):
                                text_cols = ["Nhóm hàng","Mã hàng","Mã vạch","Tên hàng","Thương hiệu","Chi nhánh"]
                                for col in text_cols:
                                    if col in df.columns:
                                        df[col] = df[col].astype(str).str.replace(",","",regex=False) \
                                            .str.replace("\n"," ",regex=False).str.strip()
                                        df.loc[df[col]=="nan", col] = None
                                for col in [c for c in df.columns if c not in text_cols]:
                                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
                                records = df.where(pd.notnull(df), None).to_dict(orient="records")
                                for r in records:
                                    for k,v in r.items():
                                        if isinstance(v, np.integer): r[k] = int(v)
                                        elif isinstance(v, np.floating): r[k] = float(v)
                                total, success = len(records), 0
                                prog = st.progress(0, text="Đang upload...")
                                for i in range(0, total, 500):
                                    try:
                                        supabase.table("the_kho").insert(records[i:i+500]).execute()
                                        success += len(records[i:i+500])
                                        prog.progress(min(success/total, 1.0), text=f"{success}/{total} dòng...")
                                    except Exception as e:
                                        st.error(f"Lỗi batch {i}: {e}")
                                prog.empty()
                                if success == total:
                                    st.success(f"✅ Upload {success} dòng thành công!")
                                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Lỗi đọc file: {e}")

        with sub_hd:
            st.markdown("**Hướng dẫn:** Tải file **Danh sách hóa đơn** từ KiotViet (`.xlsx`).")
            uploaded = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_hd")
            if uploaded:
                try:
                    df = pd.read_excel(uploaded)
                    st.success(f"Đọc được **{len(df)}** dòng, **{len(df.columns)}** cột")
                    missing = [c for c in ["Mã hóa đơn","Thời gian","Chi nhánh"] if c not in df.columns]
                    if missing:
                        st.error(f"Thiếu cột: {', '.join(missing)}")
                    else:
                        st.info(f"Chi nhánh: {', '.join(df['Chi nhánh'].unique())} — {df['Mã hóa đơn'].nunique()} hóa đơn")
                        with st.expander("👁️ Xem trước"):
                            st.dataframe(df.head(), use_container_width=True, hide_index=True)
                        if st.button("🚀 Upload Hóa đơn", key="btn_up_hd", type="primary"):
                            with st.spinner("Đang xử lý..."):
                                for col in df.columns:
                                    if df[col].dtype == "object":
                                        df[col] = df[col].astype(str).str.replace("\n"," ",regex=False).str.strip()
                                        df.loc[df[col]=="nan", col] = None
                                for col in ["Tổng tiền hàng","Khách cần trả","Khách đã trả","Đơn giá","Thành tiền"]:
                                    if col in df.columns:
                                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
                                records = df.where(pd.notnull(df), None).to_dict(orient="records")
                                for r in records:
                                    for k,v in r.items():
                                        if isinstance(v, np.integer): r[k] = int(v)
                                        elif isinstance(v, np.floating): r[k] = float(v)
                                total, success = len(records), 0
                                prog = st.progress(0, text="Đang upload...")
                                for i in range(0, total, 500):
                                    try:
                                        supabase.table("hoa_don").insert(records[i:i+500]).execute()
                                        success += len(records[i:i+500])
                                        prog.progress(min(success/total, 1.0), text=f"{success}/{total} dòng...")
                                    except Exception as e:
                                        st.error(f"Lỗi batch {i}: {e}")
                                prog.empty()
                                if success == total:
                                    st.success(f"✅ Upload {success} dòng thành công!")
                                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Lỗi đọc file: {e}")

    with tab_del:
        st.caption("Xóa dữ liệu cũ trước khi upload lại hoặc dọn dẹp hàng tháng.")
        c1, c2 = st.columns(2)
        with c1:
            bang = st.selectbox("Chọn bảng:", ["the_kho","hoa_don"], key="sel_del_table")
        with c2:
            try:
                tmp = load_the_kho() if bang == "the_kho" else load_hoa_don()
                ds_cn = ["-- Tất cả --"] + sorted(tmp["Chi nhánh"].dropna().unique().tolist()) if not tmp.empty else ["-- Tất cả --"]
            except Exception:
                ds_cn = ["-- Tất cả --"]
            cn_xoa = st.selectbox("Chi nhánh:", ds_cn, key="sel_del_branch")
        try:
            q = supabase.table(bang).select("id", count="exact")
            if cn_xoa != "-- Tất cả --":
                q = q.eq("Chi nhánh", cn_xoa)
            cnt = q.execute().count or 0
        except Exception:
            cnt = "?"
        pham_vi = f"chi nhánh **{cn_xoa}**" if cn_xoa != "-- Tất cả --" else "**TOÀN BỘ**"
        st.warning(f"Sẽ xóa **{cnt}** dòng từ `{bang}` — {pham_vi}")
        confirm = st.text_input("Gõ **XOA** để xác nhận:", key="confirm_del")
        if st.button("🗑️ Thực hiện xóa", key="btn_del"):
            if confirm != "XOA":
                st.error("Gõ đúng XOA để xác nhận.")
            else:
                with st.spinner("Đang xóa..."):
                    try:
                        q = supabase.table(bang).delete()
                        if cn_xoa != "-- Tất cả --":
                            q = q.eq("Chi nhánh", cn_xoa)
                        else:
                            q = q.neq("id", -999999)
                        q.execute()
                        st.success("✅ Xóa thành công!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

    with tab_nv:
        module_nhan_vien()


# ==========================================
# NAVIGATION CHÍNH
# ==========================================

user = get_user()

col_nav, col_reload, col_logout = st.columns([4, 1, 1])
with col_nav:
    menu = ["📊 Tổng quan", "🧾 Hóa đơn", "📦 Thẻ kho"]
    if is_admin():
        menu.append("⚙️ Quản trị")
    chuc_nang = st.radio("Phân hệ:", menu, horizontal=True, label_visibility="collapsed")

with col_reload:
    if st.button("🔄 Reload", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_logout:
    if st.button("🚪 Đăng xuất", use_container_width=True):
        do_logout()
        st.rerun()

st.markdown("<hr style='margin-top:0;margin-bottom:20px;'>", unsafe_allow_html=True)

if chuc_nang == "📊 Tổng quan":
    module_tong_quan()
elif chuc_nang == "🧾 Hóa đơn":
    module_hoa_don()
elif chuc_nang == "📦 Thẻ kho":
    module_the_kho()
elif chuc_nang == "⚙️ Quản trị":
    module_quan_tri()
