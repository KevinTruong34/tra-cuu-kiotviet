import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime, timedelta
import numpy as np
import bcrypt
import uuid

# ==========================================
# PHIEN BAN: 13.3 — Master hang hoa + UX + mobile fix
# ==========================================

st.set_page_config(page_title="Watch Store", layout="wide")

st.markdown("""
<style>
/* ══════════════════════════════════════════
   PHIEN BAN: 14.0 — New UI Theme
   ══════════════════════════════════════════ */

/* ── Ẩn chrome Streamlit ── */
header, footer, #stDecoration, .stAppDeployButton,
[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stElementToolbar"], [data-testid="stDecoration"]
{ display: none !important; }

/* ── Base ── */
html, body { overflow-x: hidden !important; max-width: 100vw !important; }
*, *::before, *::after { box-sizing: border-box; }
.stApp { background: #f5f6f8 !important; }

/* ── Layout ── */
.block-container {
    padding: 0.6rem 0.8rem 1.5rem 0.8rem !important;
    max-width: 900px !important;
}

/* ── Metric ── */
[data-testid="stMetricValue"] { font-size: 1.25rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-size: 0.78rem !important; color: #888; }

/* ── Search input ── */
[data-testid="stTextInput"] input {
    font-size: 0.95rem !important;
    padding: 0.55rem 0.75rem !important;
    border-radius: 8px !important;
    border: 1px solid #e0e0e0 !important;
    background: #fff !important;
}

/* ── Buttons: primary = red like KiotViet ── */
[data-testid="stBaseButton-primary"] {
    background: #e63946 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background: #c1121f !important;
}
[data-testid="stBaseButton-secondary"] {
    border-radius: 8px !important;
    border: 1px solid #ddd !important;
    background: #fff !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-testid="stTab"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    color: #e63946 !important;
    border-bottom-color: #e63946 !important;
}

/* ── Radio nav ── */
[data-testid="stRadio"] > label:first-child { display: none; }
[data-testid="stRadio"] label { font-size: 0.88rem !important; }
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.88rem !important;
}

/* ── Dataframe: contain scroll trên mobile ── */
[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden !important; }
[data-testid="stDataFrame"] > div { overscroll-behavior: contain !important; }
iframe { touch-action: pan-y; }

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid #e8e8e8 !important;
    border-radius: 8px !important;
    background: #fff !important;
}

/* ── Divider ── */
hr { border-color: #ebebeb !important; margin: 8px 0 !important; }

/* ── Caption ── */
[data-testid="stCaptionContainer"] { color: #888 !important; font-size: 0.78rem !important; }

/* ── Info/Warning/Success ── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Mobile ── */
@media (max-width: 640px) {
    .block-container { padding: 0.4rem 0.5rem 1rem 0.5rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.05rem !important; }
}

/* ── Card utility (dùng trong markdown) ── */
.ws-card {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px 0;
}
.ws-tag {
    display: inline-block;
    background: #fff0f1;
    color: #e63946;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
}
.ws-badge-green { color: #1a7f37; font-weight: 700; font-size: 1.1rem; }
.ws-badge-red   { color: #cf4c2c; font-weight: 700; font-size: 1.1rem; }
.ws-badge-gray  { color: #aaa;    font-weight: 700; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# SUPABASE
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Chưa cấu hình SUPABASE_URL và SUPABASE_KEY trong Streamlit Secrets!")
    st.stop()

ALL_BRANCHES = ["100 Lê Quý Đôn", "Coop Vũng Tàu", "GO BÀ RỊA"]
CN_SHORT = {
    "100 Lê Quý Đôn": "Lê Quý Đôn",
    "Coop Vũng Tàu":  "Coop VT",
    "GO BÀ RỊA":      "GO Bà Rịa",
}


# ==========================================
# AUTH
# ==========================================

def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def create_session_token(nv_id):
    token = str(uuid.uuid4())
    supabase.table("sessions").insert({
        "token": token,
        "nhan_vien_id": nv_id,
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }).execute()
    return token

def delete_session(token):
    supabase.table("sessions").delete().eq("token", token).execute()

def load_user_by_id(nv_id):
    res = supabase.table("nhan_vien").select("*").eq("id", nv_id).eq("active", True).execute()
    if not res.data:
        return None
    u = res.data[0]; u.pop("mat_khau", None)
    cn = supabase.table("nhan_vien_chi_nhanh") \
        .select("chi_nhanh(ten)").eq("nhan_vien_id", nv_id).execute()
    u["chi_nhanh_list"] = [x["chi_nhanh"]["ten"] for x in cn.data] if cn.data else []
    return u

def restore_session(token):
    try:
        res = supabase.table("sessions").select("nhan_vien_id,expires_at").eq("token", token).execute()
        if not res.data: return None
        s = res.data[0]
        if datetime.fromisoformat(s["expires_at"].replace("Z","+00:00")).replace(tzinfo=None) < datetime.utcnow():
            delete_session(token); return None
        return load_user_by_id(s["nhan_vien_id"])
    except Exception:
        return None

def do_login(username, password):
    try:
        res = supabase.table("nhan_vien").select("*").eq("username", username).eq("active", True).execute()
        if not res.data: return None, "Tài khoản không tồn tại hoặc đã bị khóa."
        u = res.data[0]
        if not verify_password(password, u["mat_khau"]): return None, "Mật khẩu không chính xác."
        u.pop("mat_khau", None)
        cn = supabase.table("nhan_vien_chi_nhanh") \
            .select("chi_nhanh(ten)").eq("nhan_vien_id", u["id"]).execute()
        u["chi_nhanh_list"] = [x["chi_nhanh"]["ten"] for x in cn.data] if cn.data else []
        return u, None
    except Exception as e:
        return None, f"Lỗi hệ thống: {e}"

def do_logout():
    token = st.query_params.get("token")
    if token: delete_session(token)
    st.session_state.clear(); st.query_params.clear()


# ==========================================
# SESSION HELPERS
# ==========================================

def get_user(): return st.session_state.get("user")
def is_admin(): u = get_user(); return u and u.get("role") == "admin"
def is_ke_toan_or_admin(): u = get_user(); return u and u.get("role") in ("admin","ke_toan")
def get_active_branch(): return st.session_state.get("active_chi_nhanh","")

def get_accessible_branches():
    u = get_user()
    if not u: return []
    return ALL_BRANCHES if u.get("role") == "admin" else u.get("chi_nhanh_list", [])

def get_selectable_branches():
    return get_accessible_branches()


# ==========================================
# FIRST RUN
# ==========================================

def is_first_run():
    try:
        return (supabase.table("nhan_vien").select("id",count="exact").execute().count or 0) == 0
    except: return False

def show_first_run():
    st.title("Khởi tạo hệ thống")
    st.info("Chưa có tài khoản nào. Tạo tài khoản Admin để bắt đầu.")
    with st.form("setup"):
        u = st.text_input("Username:"); n = st.text_input("Họ tên:")
        p = st.text_input("Mật khẩu:", type="password")
        p2 = st.text_input("Xác nhận:", type="password")
        if st.form_submit_button("Tạo tài khoản Admin", type="primary"):
            if not all([u,n,p,p2]): st.error("Điền đầy đủ.")
            elif p != p2: st.error("Mật khẩu không khớp.")
            elif len(p) < 6: st.error("Tối thiểu 6 ký tự.")
            else:
                try:
                    supabase.table("nhan_vien").insert({
                        "username":u,"ho_ten":n,"mat_khau":hash_password(p),"role":"admin","active":True
                    }).execute()
                    st.success("Tạo thành công! Hãy đăng nhập."); st.rerun()
                except Exception as e: st.error(f"Lỗi: {e}")

# ==========================================
# LOGIN
# ==========================================

def show_login():
    st.title("Đăng nhập")
    with st.form("login"):
        u = st.text_input("Tài khoản:")
        p = st.text_input("Mật khẩu:", type="password")
        if st.form_submit_button("Đăng nhập", type="primary", use_container_width=True):
            if not u or not p: st.error("Nhập đầy đủ.")
            else:
                with st.spinner("Đang xác thực..."):
                    user, err = do_login(u, p)
                if err: st.error(err)
                else:
                    token = create_session_token(user["id"])
                    st.session_state["user"] = user
                    st.query_params["token"] = token
                    st.rerun()


# ==========================================
# BRANCH SELECTION
# ==========================================

def show_branch_selection():
    user     = get_user()
    branches = get_selectable_branches()

    if len(branches) == 1:
        st.session_state["active_chi_nhanh"] = branches[0]
        st.rerun(); return

    # Căn giữa màn hình
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(f"""
            <div style="text-align:center;padding:32px 0 24px 0;">
                <div style="font-size:1.5rem;font-weight:700;color:#1a1a2e;margin-bottom:4px;">
                    Xin chào, {user.get('ho_ten','')}
                </div>
                <div style="font-size:0.9rem;color:#888;">
                    Chọn chi nhánh để bắt đầu ca làm việc
                </div>
            </div>
        """, unsafe_allow_html=True)

        for i, branch in enumerate(branches):
            if st.button(
                branch,
                key=f"sel_{i}",
                use_container_width=True,
                type="primary" if i == 0 else "secondary",
            ):
                st.session_state["active_chi_nhanh"] = branch
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Đăng xuất", use_container_width=True):
            do_logout(); st.rerun()


# ==========================================
# SESSION RESTORE
# ==========================================

if "user" not in st.session_state:
    token = st.query_params.get("token")
    if token:
        user = restore_session(token)
        if user: st.session_state["user"] = user
        else: st.query_params.clear()

if "user" not in st.session_state:
    show_first_run() if is_first_run() else show_login()
    st.stop()

if "active_chi_nhanh" not in st.session_state:
    show_branch_selection(); st.stop()


# ==========================================
# DATA LOADING
# ==========================================

@st.cache_data(ttl=300)
def load_hoa_don(branches_key: tuple):
    rows, batch, offset = [], 1000, 0
    while True:
        res = supabase.table("hoa_don").select("*") \
            .in_("Chi nhánh", list(branches_key)) \
            .range(offset, offset+batch-1).execute()
        if not res.data: break
        rows.extend(res.data)
        if len(res.data) < batch: break
        offset += batch
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    tong = len(df); df = df.drop_duplicates()
    st.session_state["so_dong_trung"] = tong - len(df)
    for col in ["Tổng tiền hàng","Khách cần trả","Khách đã trả","Đơn giá","Thành tiền"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "Thời gian" in df.columns:
        df["_ngay"] = pd.to_datetime(df["Thời gian"], format="%d/%m/%Y %H:%M", errors="coerce")
        if df["_ngay"].isna().all():
            df["_ngay"] = pd.to_datetime(df["Thời gian"], dayfirst=True, errors="coerce")
        df["_date"] = df["_ngay"].dt.date
    return df

@st.cache_data(ttl=300)
def load_the_kho(branches_key: tuple):
    rows, batch, offset = [], 1000, 0
    while True:
        res = supabase.table("the_kho").select("*") \
            .in_("Chi nhánh", list(branches_key)) \
            .range(offset, offset+batch-1).execute()
        if not res.data: break
        rows.extend(res.data)
        if len(res.data) < batch: break
        offset += batch
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ["Tồn đầu kì","Giá trị đầu kì","Nhập NCC","Giá trị nhập NCC",
                "Xuất bán","Giá trị xuất bán","Tồn cuối kì","Giá trị cuối kì"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=600)
def load_hang_hoa() -> pd.DataFrame:
    """Master data sản phẩm — cache 10 phút (ít thay đổi hơn tồn kho)."""
    rows, batch, offset = [], 1000, 0
    while True:
        res = supabase.table("hang_hoa").select("*") \
            .range(offset, offset + batch - 1).execute()
        if not res.data: break
        rows.extend(res.data)
        if len(res.data) < batch: break
        offset += batch
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "gia_ban" in df.columns:
        df["gia_ban"] = pd.to_numeric(df["gia_ban"], errors="coerce").fillna(0)
    return df

@st.cache_data(ttl=300)
def load_phieu_chuyen_kho(branches_key: tuple = None):
    """Load phiếu chuyển kho — filter theo chi nhánh (từ HOẶC tới)."""
    all_rows, batch, offset = [], 1000, 0
    while True:
        q = supabase.table("phieu_chuyen_kho").select("*") \
            .order("ngay_chuyen", desc=True)
        res = q.range(offset, offset + batch - 1).execute()
        if not res.data: break
        all_rows.extend(res.data)
        if len(res.data) < batch: break
        offset += batch
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    # Filter: chỉ giữ phiếu có liên quan đến ít nhất 1 trong các CN được chọn
    if branches_key:
        bk = list(branches_key)
        mask = df["tu_chi_nhanh"].isin(bk) | df["toi_chi_nhanh"].isin(bk)
        df = df[mask].reset_index(drop=True)
    for col in ["so_luong_chuyen","so_luong_nhan","tong_sl_chuyen","tong_sl_nhan",
                "tong_mat_hang","gia_chuyen","thanh_tien_chuyen","thanh_tien_nhan","tong_gia_tri"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "ngay_chuyen" in df.columns:
        df["_ngay"] = pd.to_datetime(df["ngay_chuyen"], errors="coerce")
        df["_date"] = df["_ngay"].dt.date
    return df
    user   = get_user()
    active = get_active_branch()
    role_label = {"admin":"Admin","ke_toan":"Kế toán","nhan_vien":"Nhân viên"}.get(user.get("role"),"")
    st.markdown(f"**{user.get('ho_ten','')}** · {role_label} · {active}")
    st.markdown("---")
    if is_ke_toan_or_admin():
        hien_thi_dashboard()
    else:
        st.info("Trang tổng quan nhân viên đang phát triển.")


# ==========================================
# DASHBOARD
# ==========================================

def hien_thi_dashboard(show_filter: bool = True):
    accessible = get_accessible_branches()
    if show_filter and is_ke_toan_or_admin() and len(accessible) > 1:
        report_branches = st.multiselect(
            "Chi nhánh báo cáo:", accessible, default=accessible, key="db_cn")
        if not report_branches:
            st.warning("Chọn ít nhất một chi nhánh."); return
    else:
        report_branches = accessible if is_ke_toan_or_admin() else [get_active_branch()]

    try:
        raw = load_hoa_don(branches_key=tuple(report_branches))
        if raw.empty or "_date" not in raw.columns:
            st.info("Chưa có dữ liệu hóa đơn."); return

        today       = datetime.now().date()
        yesterday   = today - timedelta(1)
        first_month = today.replace(day=1)
        first_last  = (first_month - timedelta(1)).replace(day=1)
        last_last   = first_month - timedelta(1)

        ky = st.selectbox("Kỳ xem:",
            ["Hôm nay","Hôm qua","7 ngày qua","Tháng này","Tháng trước"],
            index=3, label_visibility="collapsed")

        if ky=="Hôm nay":      df,dt,cf,ct,lb = today,today,yesterday,yesterday,"so với hôm qua"
        elif ky=="Hôm qua":    df,dt,cf,ct,lb = yesterday,yesterday,yesterday-timedelta(1),yesterday-timedelta(1),"so với hôm kia"
        elif ky=="7 ngày qua": df,dt,cf,ct,lb = today-timedelta(6),today,today-timedelta(13),today-timedelta(7),"so với 7 ngày trước"
        elif ky=="Tháng này":
            df,dt,cf = first_month,today,first_last
            try:    ct = first_last.replace(day=today.day)
            except: ct = last_last
            lb = "so với cùng kỳ tháng trước"
        else:
            df,dt = first_last,last_last
            m2f = (first_last-timedelta(1)).replace(day=1)
            cf,ct,lb = m2f,first_last-timedelta(1),"so với tháng trước nữa"

        ht   = raw[raw["Trạng thái"]=="Hoàn thành"].copy()
        d_ky = ht[(ht["_date"]>=df)&(ht["_date"]<=dt)]
        d_ss = ht[(ht["_date"]>=cf)&(ht["_date"]<=ct)]
        d_td = ht[ht["_date"]==today]
        d_ye = ht[ht["_date"]==yesterday]

        def tinh(d):
            if d.empty: return 0,0
            u = d.drop_duplicates(subset=["Mã hóa đơn"],keep="first")
            return u["Khách đã trả"].sum(), u["Mã hóa đơn"].nunique()

        def pct(a,b): return ((a-b)/b*100) if b else None

        dt_td,hd_td = tinh(d_td); dt_ye,_ = tinh(d_ye)
        dt_ky,hd_ky = tinh(d_ky); dt_ss,_ = tinh(d_ss)
        p_ye = pct(dt_td,dt_ye); p_ss = pct(dt_ky,dt_ss)

        st.markdown("#### Hôm nay")
        m1,m2,m3,m4 = st.columns(4)
        with m1: st.metric("Doanh thu",f"{dt_td:,.0f}"); st.caption(f"{hd_td} hóa đơn")
        with m2: st.metric("Trả hàng","0")
        with m3: st.metric("So hôm qua", f"{'↑' if (p_ye or 0)>=0 else '↓'} {abs(p_ye):.1f}%" if p_ye is not None else "—")
        with m4: st.metric(lb.capitalize(), f"{'↑' if (p_ss or 0)>=0 else '↓'} {abs(p_ss):.1f}%" if p_ss is not None else "—")

        st.caption(f"Doanh thu thuần kỳ này: **{dt_ky:,.0f} đ** ({hd_ky} hóa đơn)")

        if not d_ky.empty:
            base  = d_ky.drop_duplicates(subset=["Mã hóa đơn"],keep="first")
            chart = base.groupby(["_date","Chi nhánh"])["Khách đã trả"].sum().reset_index()
            chart.columns = ["Ngày","Chi nhánh","Doanh thu"]
            pivot = chart.pivot_table(index="Ngày",columns="Chi nhánh",values="Doanh thu",fill_value=0).sort_index()
            cmap  = {"100 Lê Quý Đôn":"#2E86DE","Coop Vũng Tàu":"#27AE60","GO BÀ RỊA":"#F39C12"}
            fig   = go.Figure()
            for i,cn in enumerate(pivot.columns):
                fig.add_trace(go.Bar(
                    x=[d.strftime("%d") for d in pivot.index], y=pivot[cn], name=CN_SHORT.get(cn,cn),
                    marker_color=cmap.get(cn,["#2E86DE","#27AE60","#F39C12"][i%3]),
                    hovertemplate=f"{cn}<br>Ngày %{{x}}<br>%{{y:,.0f}} đ<extra></extra>",
                ))
            fig.update_layout(
                barmode="stack", height=320,
                margin=dict(l=0,r=0,t=8,b=0),
                legend=dict(orientation="h",yanchor="bottom",y=-0.3,xanchor="center",x=0.5),
                yaxis=dict(tickformat=",.0f",gridcolor="#eee"),
                xaxis=dict(title=None,dtick=1),
                plot_bgcolor="white", font=dict(size=11), dragmode=False,
            )
            mx = pivot.sum(axis=1).max() if not pivot.empty else 0
            if mx >= 1_000_000:
                step = max(6_000_000, int(mx/8)//1_000_000*1_000_000)
                tvs  = list(range(0,int(mx+step),step))
                fig.update_layout(yaxis=dict(tickvals=tvs,ticktext=[f"{int(v/1_000_000)}tr" for v in tvs],gridcolor="#eee"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
        else:
            st.info("Không có dữ liệu trong kỳ này.")
    except Exception as e:
        st.error(f"Lỗi dashboard: {e}")


# ==========================================
# MODULE: HÓA ĐƠN
# ==========================================

def module_hoa_don():
    def render_invoice(inv_df, code):
        row    = inv_df.iloc[0]
        status = row.get("Trạng thái","N/A")
        color  = "#1a7f37" if status=="Hoàn thành" else "#cf4c2c"
        with st.expander(
            f"{code}  ·  {row.get('Thời gian','')}  ·  {row.get('Tên khách hàng','Khách lẻ')}",
            expanded=True
        ):
            st.markdown(
                f'<span style="background:{color};color:#fff;padding:3px 12px;'
                f'border-radius:20px;font-size:.8rem;font-weight:600;">{status}</span>',
                unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            c1,c2 = st.columns(2)
            c1.metric("Tổng tiền hàng", f"{row.get('Tổng tiền hàng',0):,.0f} đ")
            c2.metric("Khách đã trả",   f"{row.get('Khách đã trả',0):,.0f} đ")

            cols = ["Mã hàng","Tên hàng","Số lượng","Đơn giá","Thành tiền","Ghi chú hàng hóa"]
            dv = inv_df[[c for c in cols if c in inv_df.columns]].copy()
            for c in ["Đơn giá","Thành tiền"]:
                if c in dv.columns: dv[c] = dv[c].apply(lambda x: f"{x:,.0f}")
            with st.expander("Chi tiết hàng hóa", expanded=False):
                st.dataframe(dv, use_container_width=True, hide_index=True)

    def render_list(res):
        ok  = res[res["Trạng thái"] != "Đã hủy"]
        huy = res[res["Trạng thái"] == "Đã hủy"]
        for code in ok["Mã hóa đơn"].unique():
            render_invoice(ok[ok["Mã hóa đơn"]==code], code)
        if not huy.empty:
            with st.expander(f"Hóa đơn đã hủy ({huy['Mã hóa đơn'].nunique()})", expanded=False):
                for code in huy["Mã hóa đơn"].unique():
                    render_invoice(huy[huy["Mã hóa đơn"]==code], code)

    try:
        active = get_active_branch()
        raw = load_hoa_don(branches_key=(active,))
        if raw.empty:
            st.info("Chưa có dữ liệu hóa đơn tại chi nhánh này."); return

        if st.session_state.get("so_dong_trung",0) > 0:
            st.caption(f"⚠ {st.session_state['so_dong_trung']} dòng trùng đã lọc.")

        data = raw.copy()
        data["SĐT_Search"] = data["Điện thoại"].fillna("").str.replace(r"\D+","",regex=True)

        t1,t2,t3 = st.tabs(["Số điện thoại","Mã hóa đơn","Ngày tháng"])
        with t1:
            phone = st.text_input("Số điện thoại:", key="in_phone", placeholder="Nhập số điện thoại...")
            if phone:
                res = data[data["SĐT_Search"].str.contains(phone.replace(" ",""),na=False)]
                if not res.empty:
                    st.caption(f"Khách hàng: **{res.iloc[0].get('Tên khách hàng','Khách lẻ')}**")
                    render_list(res)
                else: st.warning("Không tìm thấy số điện thoại.")
        with t2:
            inv = st.text_input("Mã hóa đơn:", key="in_inv", placeholder="VD: 1007 hoặc HD011007")
            if inv:
                res = data[data["Mã hóa đơn"].str.upper().str.endswith(inv.strip().upper(),na=False)]
                if not res.empty: render_list(res)
                else: st.warning("Không tìm thấy mã hóa đơn.")
        with t3:
            ds = st.text_input("Ngày:", key="in_date", placeholder="VD: 14/04/2026")
            if ds:
                res = data[data["Thời gian"].astype(str).str.contains(ds.strip(),na=False)]
                if not res.empty:
                    st.caption(f"Tìm thấy {res['Mã hóa đơn'].nunique()} hóa đơn")
                    render_list(res)
                else: st.warning("Không có dữ liệu trong ngày này.")
    except Exception as e:
        st.error(f"Lỗi: {e}")


# ==========================================
# MODULE: HÀNG HÓA (v13.3)
# ==========================================

def _normalize(text: str) -> str:
    """Fuzzy search: bỏ space/dash/dot → 'F 94' khớp 'F94'."""
    import re
    return re.sub(r"[\s\-_./]", "", str(text)).upper()


def module_hang_hoa():
    """
    v14.0 — UI theo mockup:
    - Detail card trên, bảng dưới
    - st.dataframe on_select (click row → detail)
    - 10 hàng hiển thị, scroll nội bộ
    - Tồn kho: highlight chi nhánh hiện tại
    - Bỏ suggestion buttons
    """
    try:
        active     = get_active_branch()
        accessible = get_accessible_branches()

        # ── Chi nhánh filter ──
        if is_ke_toan_or_admin() and len(accessible) > 1:
            view_branches = st.multiselect(
                "Chi nhánh:", accessible, default=[active],
                key="hh_cn", label_visibility="collapsed")
            if not view_branches: st.warning("Chọn ít nhất một chi nhánh."); return
        else:
            view_branches = [active]

        # ── Load data ──
        master   = load_hang_hoa()
        the_kho  = load_the_kho(branches_key=tuple(view_branches))
        has_master = not master.empty

        if not has_master and the_kho.empty:
            st.info("Chưa có dữ liệu. Vào ⚙️ Quản trị → Upload để tải lên."); return

        # ── Build df ──
        if has_master and not the_kho.empty:
            kho_agg = the_kho.groupby("Mã hàng", as_index=False).agg(
                Ton_cuoi=("Tồn cuối kì","sum"))
            df = master.merge(kho_agg, left_on="ma_hang", right_on="Mã hàng", how="left")
            df["Ton_cuoi"] = df["Ton_cuoi"].fillna(0).astype(int)
        elif has_master:
            df = master.copy(); df["Ton_cuoi"] = 0
        else:
            df = the_kho.groupby(["Mã hàng","Tên hàng"], as_index=False).agg(
                Ton_cuoi=("Tồn cuối kì","sum"))
            df["ma_hang"]=""; df["ma_vach"]=""; df["ten_hang"]=df["Tên hàng"]
            df["nhom_hang"]=""; df["thuong_hieu"]=""; df["gia_ban"]=0; df["bao_hanh"]=""
            df["ma_hang"] = df["Mã hàng"]; df["ma_vach"] = df["Mã hàng"]

        # Parse nhóm cha/con
        nhom_col = df["nhom_hang"].fillna("") if "nhom_hang" in df.columns \
                   else pd.Series([""] * len(df))
        split = nhom_col.str.split(">>", n=1, expand=True)
        df["_cha"] = split[0].str.strip()
        df["_con"] = (split[1].str.strip() if 1 in split.columns else "").fillna("")

        # Normalize
        df["_norm_ma"]   = df["ma_hang"].apply(_normalize)
        df["_norm_vach"] = df.get("ma_vach", df["ma_hang"]).apply(
            lambda x: _normalize(x) if pd.notna(x) else "")
        df["_norm_ten"]  = df["ten_hang"].apply(_normalize)

        # ══════════════════════════════════════════
        # SEARCH + FILTER (1 hàng)
        # ══════════════════════════════════════════
        cha_list = sorted([c for c in df["_cha"].dropna().unique() if c])

        col_s, col_f = st.columns([5, 1])
        with col_s:
            keyword = st.text_input("", key="hh_search",
                placeholder="🔍  Tìm mã hàng, mã vạch hoặc tên...")
        with col_f:
            # Popover lọc nhóm hàng
            with st.popover("⊞ Lọc", use_container_width=True):
                cha_chon = st.selectbox("Nhóm hàng:", ["Tất cả"] + cha_list,
                    key="hh_cha", label_visibility="collapsed")
                if cha_chon != "Tất cả":
                    con_list = sorted([c for c in
                        df[df["_cha"]==cha_chon]["_con"].dropna().unique() if c])
                    con_chon = st.selectbox("Nhóm con:", ["Tất cả"] + con_list,
                        key="hh_con", label_visibility="collapsed")
                else:
                    con_chon = "Tất cả"
        # Đọc lại giá trị filter (đã được lưu vào session từ popover)
        cha_chon = st.session_state.get("hh_cha", "Tất cả")
        con_chon = st.session_state.get("hh_con", "Tất cả")

        # ── Apply filter ──
        filtered = df.copy()
        kw = _normalize(keyword) if keyword.strip() else ""
        if kw:
            filtered = filtered[
                filtered["_norm_ma"].str.contains(kw, na=False) |
                filtered["_norm_vach"].str.contains(kw, na=False) |
                filtered["_norm_ten"].str.contains(kw, na=False)]
        if cha_chon != "Tất cả":
            filtered = filtered[filtered["_cha"] == cha_chon]
        if con_chon != "Tất cả":
            filtered = filtered[filtered["_con"] == con_chon]

        filtered = filtered.sort_values("Ton_cuoi", ascending=False).reset_index(drop=True)

        if filtered.empty:
            st.warning("Không tìm thấy hàng hóa phù hợp."); return

        # Auto-select khi filter còn đúng 1 kết quả
        if len(filtered) == 1:
            st.session_state["hh_ma_chon"] = filtered.iloc[0]["ma_hang"]

        # Validate ma_chon
        ma_chon = st.session_state.get("hh_ma_chon")
        if ma_chon and ma_chon not in filtered["ma_hang"].values:
            ma_chon = None; st.session_state.pop("hh_ma_chon", None)

        # ══════════════════════════════════════════
        # DETAIL CARD (trên bảng, khi đã chọn)
        # ══════════════════════════════════════════
        if ma_chon:
            row_m = filtered[filtered["ma_hang"] == ma_chon].iloc[0]
            ma_display = str(row_m["ma_hang"])
            vach       = str(row_m.get("ma_vach","") or "")
            nhom_full  = (f"{row_m['_cha']} › {row_m['_con']}"
                         if row_m.get("_con","") else row_m.get("_cha",""))
            gb = int(row_m.get("gia_ban", 0) or 0)

            extra_parts = []
            if pd.notna(row_m.get("thuong_hieu","")) and str(row_m.get("thuong_hieu","")).strip():
                extra_parts.append(f"Thương hiệu: {row_m['thuong_hieu']}")
            if pd.notna(row_m.get("bao_hanh","")) and str(row_m.get("bao_hanh","")).strip():
                extra_parts.append(f"Bảo hành: {row_m['bao_hanh']}")
            extra_str = " · ".join(extra_parts)

            vach_str   = f" · {vach}" if vach and vach != ma_display else ""
            nhom_html  = f"<div style='font-size:0.75rem;color:#aaa;margin-top:1px;'>{nhom_full}</div>" if nhom_full else ""
            extra_html = f"<div style='font-size:0.78rem;color:#666;margin-top:6px;'>{extra_str}</div>" if extra_str else ""
            gb_html    = f"<div style='margin-top:10px;font-size:0.75rem;color:#888;'>Giá bán</div>" \
                         f"<div style='font-size:1.1rem;font-weight:700;color:#1a1a2e;'>" \
                         f"{'—' if not gb else f'{gb:,} đ'}</div>"

            # Card trắng ôm hết thông tin + giá
            c_card, c_close = st.columns([8, 1])
            with c_card:
                st.markdown(
                    f"<div style='background:#fff;border:1px solid #e0e0e0;"
                    f"border-radius:12px;padding:14px 16px;'>"
                    f"<div style='font-weight:700;font-size:1.05rem;color:#1a1a2e;'>"
                    f"{row_m['ten_hang']}</div>"
                    f"{nhom_html}"
                    f"<div style='margin-top:10px;'>"
                    f"<span style='font-family:monospace;font-size:0.95rem;font-weight:700;"
                    f"background:#f4f6fa;padding:4px 10px;border-radius:6px;color:#1a1a2e;'>"
                    f"{ma_display}</span>"
                    f"<span style='font-size:0.82rem;color:#999;margin-left:8px;'>{vach_str}</span>"
                    f"</div>"
                    f"{extra_html}"
                    f"{gb_html}"
                    f"</div>",
                    unsafe_allow_html=True)
            with c_close:
                st.markdown("<div style='padding-top:10px;'>", unsafe_allow_html=True)
                if st.button("✕", key="btn_close", help="Đóng"):
                    st.session_state.pop("hh_ma_chon", None); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            # ── Tồn kho LUÔN đủ 3 chi nhánh, highlight CN hiện tại ──
            st.markdown(
                "<div style='font-size:0.82rem;font-weight:600;"
                "color:#555;margin:10px 0 6px;'>Tồn kho chi nhánh</div>",
                unsafe_allow_html=True)
            try:
                all_kho  = load_the_kho(branches_key=tuple(ALL_BRANCHES))
                # Build dict mặc định 0 cho tất cả chi nhánh
                branch_tons = {cn: 0 for cn in ALL_BRANCHES}
                if not all_kho.empty:
                    rows_kho = all_kho[all_kho["Mã hàng"] == ma_chon]
                    for _, kr in rows_kho.iterrows():
                        cn = kr.get("Chi nhánh","")
                        if cn in branch_tons:
                            branch_tons[cn] = int(kr.get("Tồn cuối kì", 0))

                # Luôn render đúng 3 cột
                cn_cols = st.columns(3)
                for idx, cn_name in enumerate(ALL_BRANCHES):
                    with cn_cols[idx]:
                        ton    = branch_tons[cn_name]
                        is_cur = (cn_name == active_cn)
                        clr    = "#1a7f37" if ton > 5 else ("#cf4c2c" if ton > 0 else "#aaa")
                        border = "2px solid #e63946" if is_cur else "1px solid #e8e8e8"
                        bg     = "#fff8f8" if is_cur else "#fff"
                        icon   = "📍 " if is_cur else ""
                        st.markdown(
                            f"<div style='text-align:center;padding:10px 4px;"
                            f"border:{border};border-radius:10px;background:{bg};'>"
                            f"<div style='font-size:0.68rem;color:#777;"
                            f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>"
                            f"{icon}{CN_SHORT.get(cn_name, cn_name)}</div>"
                            f"<div style='font-size:1.4rem;font-weight:700;color:{clr};'>"
                            f"{ton:,}</div></div>",
                            unsafe_allow_html=True)
            except Exception:
                pass

            st.markdown("<hr style='margin:12px 0 6px;'>", unsafe_allow_html=True)

        # ══════════════════════════════════════════
        # BẢNG HÀNG HÓA — st.dataframe on_select
        # 10 hàng cố định, scroll nội bộ
        # ══════════════════════════════════════════
        total = len(filtered)
        filter_label = (f"{cha_chon}" if cha_chon != "Tất cả" else "")
        st.caption(
            f"**{total}** sản phẩm"
            + (f" · {filter_label}" if filter_label else "")
            + f" · {', '.join(view_branches)}"
            + (" — lọc thêm để thu hẹp" if total > 100 else "")
        )

        # Bảng hiển thị: Tên hàng | Mã hàng | Mã vạch | Tồn kho
        disp_cols = {"ten_hang":"Tên hàng","ma_hang":"Mã hàng","Ton_cuoi":"Tồn kho"}
        if "ma_vach" in filtered.columns:
            disp_cols = {"ten_hang":"Tên hàng","ma_hang":"Mã hàng",
                         "ma_vach":"Mã vạch","Ton_cuoi":"Tồn kho"}
        avail = {k:v for k,v in disp_cols.items() if k in filtered.columns}
        disp  = filtered[list(avail.keys())].rename(columns=avail).copy()
        disp["Tồn kho"] = disp["Tồn kho"].astype(int)

        ROW_H  = 35
        HEADER = 42
        N_ROWS = 10
        tbl_h  = HEADER + N_ROWS * ROW_H   # 392px = 10 hàng cố định

        event = st.dataframe(
            disp,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="hh_table",
            column_config={
                "Tên hàng": st.column_config.TextColumn("Tên hàng", width="large"),
                "Mã hàng":  st.column_config.TextColumn("Mã hàng",  width="small"),
                "Mã vạch":  st.column_config.TextColumn("Mã vạch",  width="small"),
                "Tồn kho":  st.column_config.NumberColumn("Tồn", width="small", format="%d"),
            },
            height=tbl_h,
        )

        # Row selection → cập nhật ma_chon
        sel = event.selection.rows
        if sel and sel[0] < len(disp):
            new_ma = disp.iloc[sel[0]]["Mã hàng"]
            if new_ma != ma_chon:
                st.session_state["hh_ma_chon"] = new_ma
                st.rerun()

        if not ma_chon:
            st.caption("↑ Chọn một dòng để xem chi tiết sản phẩm")

    except Exception as e:
        st.error(f"Lỗi tải Hàng hóa: {e}")


# ==========================================
# MODULE: QUẢN LÝ NHÂN VIÊN
# ==========================================

def module_nhan_vien():
    st.markdown("### Quản lý nhân viên")
    try:
        cn_res = supabase.table("chi_nhanh").select("*").eq("active",True).execute()
        cn_map = {cn["ten"]: cn["id"] for cn in cn_res.data} if cn_res.data else {}
    except Exception as e:
        st.error(f"Lỗi tải chi nhánh: {e}"); return

    tab_add, tab_list = st.tabs(["Thêm nhân viên","Danh sách"])
    with tab_add:
        with st.form("them_nv", clear_on_submit=True):
            c1,c2 = st.columns(2)
            with c1:
                nu  = st.text_input("Username:")
                nn  = st.text_input("Họ tên:")
                nr  = st.selectbox("Role:", ["nhan_vien","ke_toan","admin"])
            with c2:
                np1 = st.text_input("Mật khẩu:", type="password")
                np2 = st.text_input("Xác nhận:", type="password")
                ncs = st.multiselect("Chi nhánh:", list(cn_map.keys()))
            if st.form_submit_button("Tạo tài khoản", type="primary"):
                if not all([nu,nn,np1,np2]): st.error("Điền đầy đủ.")
                elif np1!=np2: st.error("Mật khẩu không khớp.")
                elif len(np1)<6: st.error("Tối thiểu 6 ký tự.")
                elif not ncs and nr!="admin": st.error("Chọn ít nhất một chi nhánh.")
                else:
                    try:
                        res = supabase.table("nhan_vien").insert({
                            "username":nu,"ho_ten":nn,"mat_khau":hash_password(np1),"role":nr,"active":True
                        }).execute()
                        nv_id = res.data[0]["id"]
                        for cn in ncs:
                            supabase.table("nhan_vien_chi_nhanh").insert({
                                "nhan_vien_id":nv_id,"chi_nhanh_id":cn_map[cn]
                            }).execute()
                        st.success(f"Tạo tài khoản **{nn}** thành công!")
                    except Exception as e: st.error(f"Lỗi: {e}")

    with tab_list:
        try:
            nv_list = supabase.table("nhan_vien").select("*").order("id").execute().data or []
            cur = get_user()
            for nv in nv_list:
                cn2      = supabase.table("nhan_vien_chi_nhanh") \
                    .select("chi_nhanh(ten)").eq("nhan_vien_id",nv["id"]).execute()
                cn_names = [x["chi_nhanh"]["ten"] for x in cn2.data] if cn2.data else []
                status   = "Hoạt động" if nv["active"] else "Đã khóa"
                role_lbl = {"admin":"Admin","ke_toan":"Kế toán","nhan_vien":"Nhân viên"}.get(nv["role"],"")
                is_self  = (nv["id"]==cur.get("id"))
                with st.expander(
                    f"**{nv['ho_ten']}** · {role_lbl} · {status}"
                    + (" (bạn)" if is_self else "")
                ):
                    st.caption(f"Username: `{nv['username']}` · Chi nhánh: {', '.join(cn_names) if cn_names else '—'}")
                    ci,cp,ca = st.columns([2,2,1])
                    with ci:
                        nr2 = st.selectbox("Role:",["nhan_vien","ke_toan","admin"],
                            index=["nhan_vien","ke_toan","admin"].index(nv["role"]),
                            key=f"role_{nv['id']}")
                        if st.button("Lưu role", key=f"sr_{nv['id']}"):
                            supabase.table("nhan_vien").update({"role":nr2}).eq("id",nv["id"]).execute()
                            st.success("Đã cập nhật!"); st.rerun()
                    with cp:
                        np_ = st.text_input("Mật khẩu mới:", type="password", key=f"np_{nv['id']}")
                        if st.button("Đổi mật khẩu", key=f"sp_{nv['id']}"):
                            if np_ and len(np_)>=6:
                                supabase.table("nhan_vien").update(
                                    {"mat_khau":hash_password(np_)}).eq("id",nv["id"]).execute()
                                st.success("Đã đổi mật khẩu!")
                            else: st.warning("Tối thiểu 6 ký tự.")
                    with ca:
                        if not is_self:
                            if st.button("Khóa" if nv["active"] else "Mở khóa", key=f"tog_{nv['id']}"):
                                supabase.table("nhan_vien").update(
                                    {"active":not nv["active"]}).eq("id",nv["id"]).execute()
                                st.rerun()
                        else: st.caption("(bạn)")
        except Exception as e: st.error(f"Lỗi: {e}")


# ==========================================
# MODULE: CHUYỂN HÀNG (v13.2)
# ==========================================

def module_chuyen_hang():
    """
    View phiếu chuyển kho theo chuẩn KiotViet:
    - Grouped by ngày
    - Mỗi phiếu: từ → tới, mặt hàng, trạng thái
    - Filter theo kỳ + chi nhánh
    """
    try:
        active     = get_active_branch()
        accessible = get_accessible_branches()

        # ── Filter bar ──
        col_ky, col_cn = st.columns([2, 2])
        with col_ky:
            ky = st.selectbox("Kỳ:", ["Tháng này","Tháng trước","Tất cả"],
                key="ck_ky", label_visibility="collapsed")
        with col_cn:
            if is_ke_toan_or_admin() and len(accessible) > 1:
                cn_filter = st.selectbox("Chi nhánh:", ["Tất cả"] + accessible,
                    key="ck_cn", label_visibility="collapsed")
            else:
                cn_filter = active
                st.caption(f"📍 {active}")

        # Load data
        view_cns = tuple(accessible) if is_ke_toan_or_admin() else (active,)
        df = load_phieu_chuyen_kho(branches_key=view_cns)

        if df.empty:
            st.info("Chưa có dữ liệu chuyển hàng. Vào Quản trị → Upload để tải lên.")
            return

        # ── Apply filters ──
        today      = datetime.now().date()
        first_month = today.replace(day=1)
        first_last  = (first_month - timedelta(days=1)).replace(day=1)

        if ky == "Tháng này":
            df = df[df["_date"] >= first_month]
        elif ky == "Tháng trước":
            last_end = first_month - timedelta(days=1)
            df = df[(df["_date"] >= first_last) & (df["_date"] <= last_end)]

        if cn_filter != "Tất cả":
            df = df[(df["tu_chi_nhanh"] == cn_filter) | (df["toi_chi_nhanh"] == cn_filter)]

        if df.empty:
            st.info("Không có phiếu trong kỳ này.")
            return

        # ── Summary ──
        # Lấy 1 dòng đại diện mỗi phiếu để tính tổng
        phieu_df = df.drop_duplicates(subset=["ma_phieu"], keep="first")
        tong_giatri = phieu_df["tong_gia_tri"].sum()
        so_phieu    = len(phieu_df)

        c_sum1, c_sum2 = st.columns(2)
        with c_sum1:
            st.metric("Tổng giá trị chuyển",
                f"{tong_giatri/1_000_000:.1f} tr đ" if tong_giatri >= 1_000_000
                else f"{tong_giatri:,} đ")
        with c_sum2:
            st.metric("Số phiếu", str(so_phieu))

        st.markdown("---")

        # ── Group by date, render phiếu ──
        dates = sorted(df["_date"].dropna().unique(), reverse=True)

        for dt in dates:
            df_day = df[df["_date"] == dt]
            phieu_day = df_day["ma_phieu"].unique()

            # Date header
            today_dt = datetime.now().date()
            yest     = today_dt - timedelta(days=1)
            if dt == today_dt:   day_lbl = "HÔM NAY"
            elif dt == yest:     day_lbl = "HÔM QUA"
            else:
                try:
                    weekday = ["THỨ HAI","THỨ BA","THỨ TƯ","THỨ NĂM",
                               "THỨ SÁU","THỨ BẢY","CHỦ NHẬT"][dt.weekday()]
                    day_lbl = f"{weekday}, {dt.strftime('%d/%m/%Y')}"
                except Exception:
                    day_lbl = dt.strftime("%d/%m/%Y")

            st.markdown(
                f"<div style='font-size:0.72rem;font-weight:700;color:#aaa;"
                f"letter-spacing:1px;margin:12px 0 6px;'>{day_lbl}</div>",
                unsafe_allow_html=True)

            # Render từng phiếu trong ngày
            for ma_phieu in phieu_day:
                df_phieu = df_day[df_day["ma_phieu"] == ma_phieu]
                row_h    = df_phieu.iloc[0]  # header info từ dòng đầu

                tu_cn   = row_h.get("tu_chi_nhanh","")
                toi_cn  = row_h.get("toi_chi_nhanh","")
                loai    = row_h.get("loai_phieu","")
                tt      = row_h.get("trang_thai","")
                tsl     = int(row_h.get("tong_sl_chuyen", 0) or 0)
                tmat    = int(row_h.get("tong_mat_hang", 0) or 0)
                tgiatri = int(row_h.get("tong_gia_tri", 0) or 0)
                ngay_str = ""
                try:
                    ngay_str = pd.Timestamp(row_h["ngay_chuyen"]).strftime("%d/%m %H:%M")
                except Exception:
                    pass

                # Màu trạng thái
                tt_color = "#1a7f37" if tt == "Đã nhận" else "#aaa"
                tt_bg    = "#f0faf4" if tt == "Đã nhận" else "#f5f5f5"

                # Tóm tắt hàng hóa (tối đa 3 mặt hàng)
                hang_list = df_phieu[["ten_hang","so_luong_chuyen"]].dropna().head(3)
                hang_str  = ", ".join(
                    f"{r['ten_hang']} <b>x{int(r['so_luong_chuyen'])}</b>"
                    for _, r in hang_list.iterrows()
                )
                if len(df_phieu) > 3:
                    hang_str += f" <span style='color:#aaa;'>+{len(df_phieu)-3} khác</span>"

                # Card phiếu
                with st.expander(
                    f"{tmat} mặt hàng · SL: {tsl}   —   "
                    f"{tgiatri/1_000_000:.2f} tr đ",
                    expanded=False
                ):
                    # Header trong expander
                    col_info, col_status = st.columns([4, 1])
                    with col_info:
                        tu_color  = "#2E86DE"
                        toi_color = "#27AE60"
                        st.markdown(
                            f"<div style='font-size:0.88rem;'>"
                            f"Từ <span style='color:{tu_color};font-weight:600;'>{tu_cn}</span>"
                            f" → Đến <span style='color:{toi_color};font-weight:600;'>{toi_cn}</span>"
                            f"</div>"
                            f"<div style='font-size:0.78rem;color:#888;margin-top:3px;'>"
                            f"{ngay_str} · {ma_phieu}</div>",
                            unsafe_allow_html=True)
                    with col_status:
                        st.markdown(
                            f"<div style='text-align:right;margin-top:4px;'>"
                            f"<span style='background:{tt_bg};color:{tt_color};"
                            f"padding:3px 10px;border-radius:20px;font-size:0.75rem;"
                            f"font-weight:600;'>{tt}</span></div>",
                            unsafe_allow_html=True)

                    st.markdown(
                        f"<div style='font-size:0.82rem;color:#444;margin:8px 0 4px;'>"
                        f"{hang_str}</div>",
                        unsafe_allow_html=True)

                    # Bảng chi tiết hàng hóa
                    cols_detail = ["ten_hang","ma_hang","so_luong_chuyen","so_luong_nhan"]
                    cols_avail  = [c for c in cols_detail if c in df_phieu.columns]
                    dv = df_phieu[cols_avail].copy()
                    dv = dv.rename(columns={
                        "ten_hang":"Tên hàng","ma_hang":"Mã hàng",
                        "so_luong_chuyen":"SL chuyển","so_luong_nhan":"SL nhận"})
                    st.dataframe(dv, use_container_width=True, hide_index=True,
                                 height=min(200, 42 + len(dv)*35))

    except Exception as e:
        st.error(f"Lỗi tải Chuyển hàng: {e}")


# ==========================================
# MODULE: QUẢN TRỊ
# ==========================================

def module_quan_tri():
    if not is_admin():
        st.error("Bạn không có quyền truy cập."); return

    tab_ds, tab_up, tab_del, tab_nv = st.tabs(["Doanh số","Upload","Xóa dữ liệu","Nhân viên"])

    with tab_ds:
        hien_thi_dashboard(show_filter=False)

    with tab_up:
        s1, s2, s3, s4 = st.tabs(["Hàng hóa (master)","Thẻ kho","Hóa đơn","Chuyển kho"])

        with s1:
            st.caption("File **Danh sách sản phẩm** từ KiotViet (.xlsx) — upload một lần, cập nhật khi có sản phẩm mới.")
            up = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_hh")
            if up:
                try:
                    df = pd.read_excel(up)
                    st.success(f"Đọc được {len(df)} dòng")
                    # Map cột KiotViet → hang_hoa
                    col_map = {
                        "Mã hàng":          "ma_hang",
                        "Mã vạch":          "ma_vach",
                        "Tên hàng":         "ten_hang",
                        "Nhóm hàng(3 Cấp)": "nhom_hang",
                        "Thương hiệu":      "thuong_hieu",
                        "Giá bán":          "gia_ban",
                        "Bảo hành":         "bao_hanh",
                        "Đang kinh doanh":  "dang_kd",
                    }
                    miss = [c for c in ["Mã hàng","Tên hàng"] if c not in df.columns]
                    if miss:
                        st.error(f"Thiếu cột bắt buộc: {', '.join(miss)}")
                    else:
                        # Chỉ lấy cột có trong file
                        avail = {k:v for k,v in col_map.items() if k in df.columns}
                        df_out = df[list(avail.keys())].rename(columns=avail).copy()
                        # Parse nhóm cha/con
                        if "nhom_hang" in df_out.columns:
                            split = df_out["nhom_hang"].fillna("").str.split(">>", n=1, expand=True)
                            df_out["nhom_cha"] = split[0].str.strip()
                            df_out["nhom_con"] = split[1].str.strip() if 1 in split.columns else ""
                            df_out["nhom_con"] = df_out["nhom_con"].fillna("")
                        # Clean
                        df_out["ma_hang"]  = df_out["ma_hang"].astype(str).str.strip()
                        df_out["ten_hang"] = df_out["ten_hang"].astype(str).str.strip()
                        if "gia_ban" in df_out.columns:
                            df_out["gia_ban"] = pd.to_numeric(df_out["gia_ban"], errors="coerce").fillna(0).astype(int)
                        if "dang_kd" in df_out.columns:
                            df_out["dang_kd"] = df_out["dang_kd"].fillna(1).astype(bool)

                        # ── Clean NaN → None triệt để ──
                        def _clean(val):
                            if val is None: return None
                            try:
                                if pd.isna(val): return None
                            except Exception: pass
                            if isinstance(val, (np.integer,)):  return int(val)
                            if isinstance(val, (np.floating,)): return None if np.isnan(val) else float(val)
                            if isinstance(val, float) and (val != val): return None  # nan check
                            return val

                        records = [
                            {k: _clean(v) for k, v in row.items()}
                            for row in df_out.to_dict(orient="records")
                        ]

                        st.info(f"{len(records)} sản phẩm sẽ được upsert (thêm mới hoặc cập nhật)")
                        with st.expander("Xem trước"):
                            st.dataframe(df_out.head(), use_container_width=True, hide_index=True)

                        if st.button("Upload Hàng hóa", key="btn_up_hh", type="primary"):
                            with st.spinner("Đang upload..."):
                                total, ok = len(records), 0
                                prog = st.progress(0, text="Đang upload...")
                                for i in range(0, total, 500):
                                    try:
                                        supabase.table("hang_hoa").upsert(
                                            records[i:i+500],
                                            on_conflict="ma_hang"
                                        ).execute()
                                        ok += len(records[i:i+500])
                                        prog.progress(min(ok/total,1.0), text=f"{ok}/{total}...")
                                    except Exception as e:
                                        st.error(f"Batch {i}: {e}")
                                prog.empty()
                                if ok == total:
                                    st.success(f"✅ Upsert {ok} sản phẩm thành công!")
                                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
        with s2:
            st.caption("File **Xuất nhập tồn chi tiết** từ KiotViet (.xlsx)")
            up = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_kho")
            if up:
                try:
                    df   = pd.read_excel(up)
                    st.success(f"Đọc được {len(df)} dòng")
                    miss = [c for c in ["Mã hàng","Tên hàng","Chi nhánh","Tồn cuối kì"] if c not in df.columns]
                    if miss: st.error(f"Thiếu cột: {', '.join(miss)}")
                    else:
                        st.info(f"Chi nhánh: {', '.join(df['Chi nhánh'].unique())}")
                        with st.expander("Xem trước"):
                            st.dataframe(df.head(), use_container_width=True, hide_index=True)
                        if st.button("Upload thẻ kho", key="btn_up_kho", type="primary"):
                            with st.spinner("Đang xử lý..."):
                                tc = ["Nhóm hàng","Mã hàng","Mã vạch","Tên hàng","Thương hiệu","Chi nhánh"]
                                for col in tc:
                                    if col in df.columns:
                                        df[col] = df[col].astype(str).str.replace(","," ",regex=False) \
                                            .str.replace("\n"," ",regex=False).str.strip()
                                        df.loc[df[col]=="nan",col] = None
                                for col in [c for c in df.columns if c not in tc]:
                                    df[col] = pd.to_numeric(df[col],errors="coerce").fillna(0).astype(int)
                                records = df.where(pd.notnull(df),None).to_dict(orient="records")
                                for r in records:
                                    for k,v in r.items():
                                        if isinstance(v,np.integer): r[k]=int(v)
                                        elif isinstance(v,np.floating): r[k]=float(v)
                                total,ok = len(records),0
                                prog = st.progress(0,text="Đang upload...")
                                for i in range(0,total,500):
                                    try:
                                        supabase.table("the_kho").insert(records[i:i+500]).execute()
                                        ok+=len(records[i:i+500])
                                        prog.progress(min(ok/total,1.0),text=f"{ok}/{total}...")
                                    except Exception as e: st.error(f"Batch {i}: {e}")
                                prog.empty()
                                if ok==total:
                                    st.success(f"Upload {ok} dòng thành công!"); st.cache_data.clear()
                except Exception as e: st.error(f"Lỗi: {e}")

        with s3:
            st.caption("File **Danh sách hóa đơn** từ KiotViet (.xlsx)")
            up = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_hd")
            if up:
                try:
                    df   = pd.read_excel(up)
                    st.success(f"Đọc được {len(df)} dòng")
                    miss = [c for c in ["Mã hóa đơn","Thời gian","Chi nhánh"] if c not in df.columns]
                    if miss: st.error(f"Thiếu cột: {', '.join(miss)}")
                    else:
                        st.info(f"{df['Mã hóa đơn'].nunique()} hóa đơn · {', '.join(df['Chi nhánh'].unique())}")
                        with st.expander("Xem trước"):
                            st.dataframe(df.head(), use_container_width=True, hide_index=True)
                        if st.button("Upload hóa đơn", key="btn_up_hd", type="primary"):
                            with st.spinner("Đang xử lý..."):
                                for col in df.columns:
                                    if df[col].dtype=="object":
                                        df[col] = df[col].astype(str).str.replace("\n"," ",regex=False).str.strip()
                                        df.loc[df[col]=="nan",col] = None
                                for col in ["Tổng tiền hàng","Khách cần trả","Khách đã trả","Đơn giá","Thành tiền"]:
                                    if col in df.columns:
                                        df[col] = pd.to_numeric(df[col],errors="coerce").fillna(0).astype(int)
                                records = df.where(pd.notnull(df),None).to_dict(orient="records")
                                for r in records:
                                    for k,v in r.items():
                                        if isinstance(v,np.integer): r[k]=int(v)
                                        elif isinstance(v,np.floating): r[k]=float(v)
                                total,ok = len(records),0
                                prog = st.progress(0,text="Đang upload...")
                                for i in range(0,total,500):
                                    try:
                                        supabase.table("hoa_don").insert(records[i:i+500]).execute()
                                        ok+=len(records[i:i+500])
                                        prog.progress(min(ok/total,1.0),text=f"{ok}/{total}...")
                                    except Exception as e: st.error(f"Batch {i}: {e}")
                                prog.empty()
                                if ok==total:
                                    st.success(f"Upload {ok} dòng thành công!"); st.cache_data.clear()
                except Exception as e: st.error(f"Lỗi: {e}")

        with s4:
            st.caption("File **Danh sách chi tiết chuyển hàng** từ KiotViet (.xlsx)")
            up = st.file_uploader("Chọn file:", type=["xlsx","xls"], key="up_ck")
            if up:
                try:
                    df = pd.read_excel(up)
                    st.success(f"Đọc được {len(df)} dòng — {df['Mã chuyển hàng'].nunique()} phiếu")
                    miss = [c for c in ["Mã chuyển hàng","Từ chi nhánh","Tới chi nhánh"] if c not in df.columns]
                    if miss:
                        st.error(f"Thiếu cột: {', '.join(miss)}")
                    else:
                        st.info(f"Từ {df['Ngày chuyển'].min()} đến {df['Ngày chuyển'].max()}")
                        with st.expander("Xem trước"):
                            st.dataframe(df.head(), use_container_width=True, hide_index=True)

                        if st.button("Upload Chuyển kho", key="btn_up_ck", type="primary"):
                            with st.spinner("Đang xử lý..."):
                                col_map = {
                                    "Mã chuyển hàng":    "ma_phieu",
                                    "Loại phiếu":        "loai_phieu",
                                    "Từ chi nhánh":      "tu_chi_nhanh",
                                    "Tới chi nhánh":     "toi_chi_nhanh",
                                    "Ngày chuyển":       "ngay_chuyen",
                                    "Ngày nhận":         "ngay_nhan",
                                    "Người tạo":         "nguoi_tao",
                                    "Ghi chú chuyển":    "ghi_chu_chuyen",
                                    "Ghi chú nhận":      "ghi_chu_nhan",
                                    "Tổng SL chuyển":    "tong_sl_chuyen",
                                    "Tổng SL nhận":      "tong_sl_nhan",
                                    "Tổng giá trị chuyển":"tong_gia_tri",
                                    "Tổng số mặt hàng":  "tong_mat_hang",
                                    "Trạng thái":        "trang_thai",
                                    "Mã hàng":           "ma_hang",
                                    "Mã vạch":           "ma_vach",
                                    "Tên hàng":          "ten_hang",
                                    "Thương hiệu":       "thuong_hieu",
                                    "Số lượng chuyển":   "so_luong_chuyen",
                                    "Số lượng nhận":     "so_luong_nhan",
                                    "Giá chuyển/nhận":   "gia_chuyen",
                                    "Thành tiền chuyển": "thanh_tien_chuyen",
                                    "Thành tiền nhận":   "thanh_tien_nhan",
                                }
                                avail = {k:v for k,v in col_map.items() if k in df.columns}
                                df_out = df[list(avail.keys())].rename(columns=avail).copy()

                                # Clean text
                                for col in df_out.select_dtypes(include="object").columns:
                                    df_out[col] = df_out[col].astype(str).str.strip()
                                    df_out.loc[df_out[col]=="nan", col] = None

                                # Numeric
                                int_cols = ["tong_sl_chuyen","tong_sl_nhan","tong_mat_hang",
                                            "so_luong_chuyen","so_luong_nhan",
                                            "gia_chuyen","thanh_tien_chuyen","thanh_tien_nhan",
                                            "tong_gia_tri"]
                                for col in int_cols:
                                    if col in df_out.columns:
                                        df_out[col] = pd.to_numeric(df_out[col], errors="coerce").fillna(0).astype(int)

                                # Datetime → ISO string
                                for col in ["ngay_chuyen","ngay_nhan"]:
                                    if col in df_out.columns:
                                        df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
                                        df_out[col] = df_out[col].apply(
                                            lambda x: x.isoformat() if pd.notna(x) else None)

                                def _clean(v):
                                    if v is None: return None
                                    try:
                                        if pd.isna(v): return None
                                    except Exception: pass
                                    if isinstance(v, np.integer):  return int(v)
                                    if isinstance(v, np.floating):
                                        return None if np.isnan(v) else float(v)
                                    return v

                                records = [{k: _clean(v) for k,v in row.items()}
                                           for row in df_out.to_dict(orient="records")]

                                total, ok = len(records), 0
                                prog = st.progress(0, text="Đang upload...")
                                for i in range(0, total, 500):
                                    try:
                                        supabase.table("phieu_chuyen_kho").insert(
                                            records[i:i+500]).execute()
                                        ok += len(records[i:i+500])
                                        prog.progress(min(ok/total,1.0), text=f"{ok}/{total}...")
                                    except Exception as e:
                                        st.error(f"Batch {i}: {e}")
                                prog.empty()
                                if ok == total:
                                    st.success(f"✅ Upload {ok} dòng ({df['Mã chuyển hàng'].nunique()} phiếu)!")
                                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    with tab_del:
        st.caption("Xóa dữ liệu cũ trước khi upload lại.")
        c1,c2 = st.columns(2)
        with c1:
            bang = st.selectbox("Bảng:", ["the_kho","hoa_don"], key="del_table")
        with c2:
            try:
                tmp = load_the_kho(tuple(ALL_BRANCHES)) if bang=="the_kho" else load_hoa_don(tuple(ALL_BRANCHES))
                ds  = ["Tất cả"]+sorted(tmp["Chi nhánh"].dropna().unique().tolist()) if not tmp.empty else ["Tất cả"]
            except: ds = ["Tất cả"]
            cn_x = st.selectbox("Chi nhánh:", ds, key="del_cn")
        try:
            q   = supabase.table(bang).select("id",count="exact")
            if cn_x!="Tất cả": q=q.eq("Chi nhánh",cn_x)
            cnt = q.execute().count or 0
        except: cnt="?"
        pv = f"chi nhánh **{cn_x}**" if cn_x!="Tất cả" else "**toàn bộ**"
        st.warning(f"Sẽ xóa **{cnt}** dòng từ `{bang}` — {pv}")
        confirm = st.text_input("Gõ XOA để xác nhận:", key="confirm_del")
        if st.button("Xóa dữ liệu", key="btn_del", type="primary"):
            if confirm!="XOA": st.error("Gõ đúng XOA để xác nhận.")
            else:
                with st.spinner("Đang xóa..."):
                    try:
                        q = supabase.table(bang).delete()
                        q = q.eq("Chi nhánh",cn_x) if cn_x!="Tất cả" else q.neq("id",-999999)
                        q.execute(); st.success("Xóa thành công!"); st.cache_data.clear()
                    except Exception as e: st.error(f"Lỗi: {e}")

    with tab_nv:
        module_nhan_vien()


# ==========================================
# NAVIGATION
# ==========================================

user      = get_user()
active_cn = get_active_branch()
sel_cns   = get_selectable_branches()
cn_short  = CN_SHORT.get(active_cn, active_cn[:6])  # tên ngắn cho nút

# ══════════════════════════════════════════
# NAVIGATION  v14.0
# ══════════════════════════════════════════

user      = get_user()
active_cn = get_active_branch()
sel_cns   = get_selectable_branches()
cn_short  = CN_SHORT.get(active_cn, active_cn[:8])
ho_ten    = user.get("ho_ten","") if user else ""
initials  = "".join(w[0].upper() for w in ho_ten.split()[:2]) if ho_ten else "?"
role_lbl  = {"admin":"Admin","ke_toan":"Kế toán","nhan_vien":"Nhân viên"}.get(
    user.get("role",""), "")

# ── Hàng 1: menu nav (toàn chiều rộng) ──
menu = ["📊 Tổng quan", "🧾 Hóa đơn", "📦 Hàng hóa", "🔄 Chuyển hàng"]
if is_admin(): menu.append("⚙️ Quản trị")
page = st.radio("nav", menu, horizontal=True, label_visibility="collapsed")

# ── Hàng 2: reload + avatar (50% / 50%) ──
col_rel, col_avatar = st.columns([1, 1])

with col_rel:
    if st.button("↺  Tải lại", use_container_width=True, help="Tải lại dữ liệu"):
        st.cache_data.clear(); st.rerun()

with col_avatar:
    with st.popover(initials, use_container_width=True):
        st.markdown(
            f"<div style='text-align:center;padding:8px 0 4px;'>"
            f"<div style='font-size:1.1rem;font-weight:700;'>{ho_ten}</div>"
            f"<div style='font-size:0.8rem;color:#888;'>{role_lbl}</div>"
            f"<div style='font-size:0.78rem;color:#aaa;margin-top:2px;'>"
            f"📍 {active_cn}</div>"
            f"</div>",
            unsafe_allow_html=True)
        st.markdown("---")

        # Đổi chi nhánh ngay trong popover
        if len(sel_cns) > 1:
            st.caption("Đổi chi nhánh:")
            for cn in sel_cns:
                is_active = (cn == active_cn)
                lbl = f"✓ {cn}" if is_active else cn
                if st.button(lbl, key=f"sw_cn_{cn}", use_container_width=True,
                             type="primary" if is_active else "secondary",
                             disabled=is_active):
                    st.session_state["active_chi_nhanh"] = cn
                    st.rerun()
            st.markdown("---")

        if st.button("🚪 Đăng xuất", use_container_width=True, key="btn_logout_pop"):
            do_logout(); st.rerun()

# strip icon từ page value để routing
page_clean = page.split(" ", 1)[1] if " " in page else page
st.markdown("<hr style='margin:4px 0 10px 0;'>", unsafe_allow_html=True)

if page_clean == "Tổng quan":     module_tong_quan()
elif page_clean == "Hóa đơn":     module_hoa_don()
elif page_clean == "Hàng hóa":    module_hang_hoa()
elif page_clean == "Chuyển hàng": module_chuyen_hang()
elif page_clean == "Quản trị":    module_quan_tri()
