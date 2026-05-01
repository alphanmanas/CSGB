import streamlit as st
import pandas as pd
from PIL import Image

st.set_page_config(page_title="ÇSGB Organizasyon & Yetkinlik Haritası", layout="wide")

EXCEL_PATH = "Çalışma ve Sosyal Güvenlik Bakanlığı (ÇSGB) Kodlama & Yetkinlik Matrisi v01.xlsx"
LOGO_PATH = "csgb_logo.png"

@st.cache_data
def load_data():
    xls = pd.ExcelFile(EXCEL_PATH)
    sheet_name = xls.sheet_names[0]
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = load_data()

st.markdown(
    """
    <style>
    .main-title {
        text-align:center;
        color:#d71920;
        font-size:30px;
        font-weight:700;
        margin-top:5px;
    }
    .uid-box {
        background-color:#e9f7fb;
        border:1px solid #b7dce8;
        padding:12px;
        border-radius:8px;
        font-size:16px;
        font-weight:600;
        text-align:center;
        margin-bottom:8px;
    }
    .unit-card {
        border:1px solid #ddd;
        border-radius:10px;
        padding:14px;
        margin:8px 0;
        box-shadow:0 2px 6px rgba(0,0,0,0.08);
        background:#fff;
    }
    </style>
    """,
    unsafe_allow_html=True
)

col_logo = st.columns([4, 2, 4])[1]

with col_logo:
    try:
        logo = Image.open(LOGO_PATH)
        st.image(logo, use_container_width=True)
    except:
        st.warning("Logo dosyası bulunamadı. LOGO_PATH değerini kontrol edin.")

st.markdown("<div class='main-title'>T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>", unsafe_allow_html=True)
st.divider()

required_possible_cols = {
    "uid": ["UID", "Kod", "Pozisyon Kodu", "Birim Kodu"],
    "unit": ["Ana Birim", "Kurum", "Birim", "Birim Adı"],
    "position": ["Pozisyon", "Pozisyon / Birim Adı", "Birim Adı", "Pozisyon Adı"],
}

def find_col(possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None

uid_col = find_col(required_possible_cols["uid"])
unit_col = find_col(required_possible_cols["unit"])
position_col = find_col(required_possible_cols["position"])

if uid_col is None:
    st.error("UID / Kod kolonu bulunamadı.")
    st.stop()

if unit_col is None:
    unit_col = position_col if position_col else df.columns[0]

if position_col is None:
    position_col = unit_col

competency_cols = []
for i in range(1, 6):
    name_col = None
    code_col = None

    for c in df.columns:
        c_clean = str(c).strip().lower()
        if f"yetkinlik {i}" in c_clean and "adı" in c_clean:
            name_col = c
        if f"yetkinlik {i}" in c_clean and "kodu" in c_clean:
            code_col = c

    if name_col or code_col:
        competency_cols.append((name_col, code_col))

if not competency_cols:
    for i in range(1, 6):
        possible_name = f"Yetkinlik {i}"
        possible_code = f"Yetkinlik {i} Kodu"
        if possible_name in df.columns or possible_code in df.columns:
            competency_cols.append((possible_name, possible_code))

st.subheader("Organizasyon Şeması")

units = (
    df[[unit_col]]
    .dropna()
    .drop_duplicates()
    .sort_values(by=unit_col)
    [unit_col]
    .tolist()
)

cols = st.columns(5)

selected_unit = None

for idx, unit in enumerate(units):
    with cols[idx % 5]:
        if st.button(str(unit), use_container_width=True, key=f"unit_{idx}"):
            selected_unit = unit
            st.session_state["selected_unit"] = unit
            st.session_state["selected_position_uid"] = None

if "selected_unit" in st.session_state:
    selected_unit = st.session_state["selected_unit"]

st.divider()

if selected_unit:
    st.subheader(f"Seçilen Ana Birim / Kurum: {selected_unit}")

    unit_df = df[df[unit_col] == selected_unit].copy()

    st.markdown("### Pozisyon / Birim Listesi")

    for idx, row in unit_df.iterrows():
        position_name = row.get(position_col, "")
        uid = row.get(uid_col, "")

        with st.container():
            st.markdown(
                f"""
                <div class="unit-card">
                    <div><b>{position_name}</b></div>
                    <div class="uid-box">{uid}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("Yetkinlikleri Göster", key=f"pos_{idx}", use_container_width=True):
                st.session_state["selected_position_uid"] = uid

if "selected_position_uid" in st.session_state and st.session_state["selected_position_uid"]:
    selected_uid = st.session_state["selected_position_uid"]
    selected_row = df[df[uid_col] == selected_uid].iloc[0]

    st.divider()
    st.subheader("Yetkinlikler")

    for name_col, code_col in competency_cols:
        comp_name = selected_row.get(name_col, "") if name_col in df.columns else ""
        comp_code = selected_row.get(code_col, "") if code_col in df.columns else ""

        if pd.notna(comp_name) or pd.notna(comp_code):
            st.markdown(
                f"""
                <div class="unit-card">
                    <div><b>{comp_name}</b></div>
                    <div class="uid-box">{comp_code}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
