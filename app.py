import streamlit as st
import pandas as pd

# 1. Cấu hình giao diện
st.set_page_config(page_title="Tra cứu Hóa đơn KiotViet", layout="wide")

# --- THÔNG TIN CẤU HÌNH ---
PASSWORD_SYSTEM = "9999"  # Bạn có thể đổi mật khẩu tại đây
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT27nMRVzpVgaCVNmvREvonJM_fRJ2uGxm4I8LT2PuBxIaFtvuqIO54tOixVCmmpEcLThzEkG92iNsb/pub?output=csv"

# 2. Cơ chế bảo mật
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Đăng nhập hệ thống tra cứu")
    user_pwd = st.text_input("Nhập mật khẩu truy cập:", type="password")
    if st.button("Xác nhận"):
        if user_pwd == PASSWORD_SYSTEM:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Mật khẩu không chính xác!")
    st.stop()

# --- GIAO DIỆN CHÍNH ---
st.title("🔍 Tra cứu Lịch sử Khách hàng")

if st.button("🔄 Cập nhật dữ liệu"):
    st.cache_data.clear()
    st.success("Đã đồng bộ dữ liệu mới nhất!")

# Hàm xử lý tiền tệ từ định dạng KiotViet
def parse_money(val):
    if pd.isna(val): return 0
    val = str(val).strip().replace('.', '').replace(',', '.')
    try: return float(val)
    except: return 0

@st.cache_data(ttl=300)
def load_data(url):
    return pd.read_csv(url, dtype=str)

try:
    data = load_data(SHEET_URL)
    data = data.dropna(subset=['Điện thoại'])
    data['Điện thoại'] = data['Điện thoại'].str.replace(r'\D+', '', regex=True)
    
    # Định dạng các cột tiền thành số để tính toán
    for col in ['Tổng tiền hàng', 'Khách cần trả', 'Khách đã trả', 'Đơn giá', 'Thành tiền']:
        if col in data.columns:
            data[col] = data[col].apply(parse_money)

    search_query = st.text_input("Nhập số điện thoại khách hàng:")
    if search_query:
        clean_query = search_query.replace(" ", "")
        result = data[data['Điện thoại'].str.contains(clean_query, na=False)]
        
        if not result.empty:
            st.info(f"Khách hàng: **{result.iloc[0].get('Tên khách hàng', 'Ẩn danh')}**")
            
            # Gom nhóm theo mã hóa đơn
            unique_invoices = result['Mã hóa đơn'].unique()
            for inv_code in unique_invoices:
                inv_data = result[result['Mã hóa đơn'] == inv_code]
                row = inv_data.iloc[0]
                
                # Xử lý màu sắc trạng thái
                status = row.get('Trạng thái', 'N/A')
                bg_color = "#28a745" if status == "Hoàn thành" else "#dc3545"
                
                header = f"🧾 {inv_code} — {row.get('Thời gian', '')}"
                with st.expander(header, expanded=True):
                    # Hiển thị Badge Trạng thái
                    st.markdown(f"""
                        <div style="display: flex; justify-content: flex-end; margin-top: -40px;">
                            <span style="background-color: {bg_color}; color: white; padding: 4px 15px; border-radius: 20px; font-weight: bold;">
                                {status}
                            </span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Chỉ số tài chính
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Tổng tiền hàng", f"{row.get('Tổng tiền hàng', 0):,.0f} đ")
                    c2.metric("Tổng hóa đơn", f"{row.get('Khách cần trả', 0):,.0f} đ")
                    c3.metric("Thực tế trả", f"{row.get('Khách đã trả', 0):,.0f} đ")
                    
                    # Bảng sản phẩm chi tiết
                    cols = ['Mã hàng', 'Tên hàng', 'Số lượng', 'Đơn giá', 'Thành tiền', 'Ghi chú hàng hóa']
                    df_view = inv_data[[c for c in cols if c in inv_data.columns]].copy()
                    
                    for c in ['Đơn giá', 'Thành tiền']:
                        if c in df_view.columns:
                            df_view[c] = df_view[c].apply(lambda x: f"{x:,.0f} đ")
                            
                    st.dataframe(df_view, use_container_width=True, hide_index=True)
        else:
            st.warning("Không tìm thấy dữ liệu cho số điện thoại này.")
except Exception as e:
    st.error(f"Lỗi: {e}")
