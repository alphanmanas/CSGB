import streamlit as st
import pandas as pd
from PIL import Image

st.set_page_config(page_title="ÇSGB Organizasyon Şeması", layout="wide")

EXCEL_PATH = "Çalışma ve Sosyal Güvenlik Bakanlığı (ÇSGB) Kodlama & Yetkinlik Matrisi v01.xlsx"
LOGO_PATH = "csgb_logo.png"

@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = load_data()

def find_col(possible):
    for c in possible:
        if c in df.columns:
            return c
    return None

uid_col = find_col(["UID", "Kod", "Pozisyon Kodu", "Birim Kodu"])
unit_col = find_col(["Ana Birim", "Kurum", "Birim", "Birim Adı"])
position_col = find_col(["Pozisyon / Birim Adı", "Pozisyon", "Pozisyon Adı", "Birim Adı"])

if uid_col is None:
    st.error("Excel içinde UID/Kod kolonu bulunamadı.")
    st.stop()

if unit_col is None:
    unit_col = position_col

if position_col is None:
    position_col = unit_col

competency_cols = []
for i in range(1, 6):
    name_candidates = [
        f"Yetkinlik {i} Adı",
        f"Yetkinlik {i}",
    ]
    code_candidates = [
        f"Yetkinlik {i} Kodu",
    ]

    name_col = find_col(name_candidates)
    code_col = find_col(code_candidates)

    if name_col or code_col:
        competency_cols.append((name_col, code_col))

st.markdown("""
<style>
.logo-area {
    text-align:center;
    margin-top:10px;
}
.title-box {
    border:2px solid #ddd;
    box-shadow:0 2px 8px rgba(0,0,0,0.15);
    text-align:center;
    padding:12px;
    margin:10px 0 25px 0;
    background:white;
}
.title-red {
    color:#e30613;
    font-size:26px;
    font-weight:800;
}
.org-red {
    background:#e30613;
    color:white;
    text-align:center;
    padding:18px 8px;
    font-weight:800;
    border-radius:2px;
    margin-bottom:18px;
    box-shadow:0 3px 8px rgba(0,0,0,0.25);
}
.org-card {
    background:#f8f8f8;
    border:2px solid #ddd;
    box-shadow:0 3px 8px rgba(0,0,0,0.15);
    padding:15px 8px;
    min-height:65px;
    text-align:center;
    margin-bottom:14px;
    font-size:14px;
}
.uid-card {
    background:#d8f2fb;
    border:1px solid #8fc8dc;
    padding:10px;
    margin-top:6px;
    font-weight:700;
    text-align:center;
}
.detail-card {
    background:white;
    border:1px solid #ddd;
    border-radius:8px;
    padding:14px;
    margin-bottom:10px;
    box-shadow:0 2px 5px rgba(0,0,0,0.08);
}
</style>
""", unsafe_allow_html=True)

logo_col = st.columns([4, 2, 4])[1]
with logo_col:
    try:
        st.image(Image.open(LOGO_PATH), use_container_width=True)
    except:
        st.warning("Logo bulunamadı: csgb_logo.png")

st.markdown("""
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Organizasyon ve Yetkinlik Haritası</div>
</div>
""", unsafe_allow_html=True)

org_groups = {
    "ÇSGB-BAK": [
        "Basın ve Halkla İlişkiler Müşavirliği",
        "Destek Hizmetleri Dairesi Başkanlığı",
        "İç Denetim Birimi Başkanlığı",
        "Özel Kalem Müdürlüğü",
        "Personel Dairesi Başkanlığı",
        "Rehberlik ve Teftiş Başkanlığı",
    ],
    "ÇSGB-BY1": [
        "Dış İlişkiler ve Avrupa Birliği Genel Müdürlüğü",
        "Sosyal Güvenlik Kurumu",
        "Strateji Geliştirme Başkanlığı",
    ],
    "ÇSGB-BY2": [
        "Bilgi Teknolojileri Genel Müdürlüğü",
        "Hukuk Hizmetleri Genel Müdürlüğü",
        "Çalışma ve Sosyal Güvenlik Eğitim ve Araştırma Merkezi",
        "Ereğli Kömür Havzası Amele Birliği Biriktirme ve Yardımlaşma Sandığı",
    ],
    "ÇSGB-BY3": [
        "Çalışma Genel Müdürlüğü",
        "Uluslararası İşgücü Genel Müdürlüğü",
        "Mesleki Yeterlilik Kurumu",
    ],
    "ÇSGB-BY4": [
        "İş Sağlığı ve Güvenliği Genel Müdürlüğü",
        "Türkiye İş Kurumu Genel Müdürlüğü",
    ],
}

cols = st.columns(5)

for idx, (top_uid, units) in enumerate(org_groups.items()):
    with cols[idx]:
        st.markdown(f"<div class='org-red'>{top_uid}</div>", unsafe_allow_html=True)

        for unit in units:
            if st.button(unit, key=f"unit_{top_uid}_{unit}", use_container_width=True):
                st.session_state["selected_unit"] = unit
                st.session_state["selected_uid"] = None

if "selected_unit" in st.session_state:
    selected_unit = st.session_state["selected_unit"]

    st.divider()
    st.subheader(selected_unit)

    unit_df = df[df[unit_col].astype(str).str.contains(selected_unit, case=False, na=False)]

    if unit_df.empty:
        unit_df = df[df[position_col].astype(str).str.contains(selected_unit, case=False, na=False)]

    if unit_df.empty:
        st.warning("Bu birim Excel içinde bulunamadı. Excel’deki birim adı ile şemadaki ad birebir farklı olabilir.")
    else:
        for i, row in unit_df.iterrows():
            position_name = row.get(position_col, "")
            uid = row.get(uid_col, "")

            st.markdown(
                f"""
                <div class="detail-card">
                    <b>{position_name}</b>
                    <div class="uid-card">{uid}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("Yetkinlikleri Göster", key=f"show_{i}", use_container_width=True):
                st.session_state["selected_uid"] = uid

if "selected_uid" in st.session_state and st.session_state["selected_uid"]:
    selected_uid = st.session_state["selected_uid"]
    selected_row = df[df[uid_col] == selected_uid]

    if not selected_row.empty:
        row = selected_row.iloc[0]

        st.divider()
        st.subheader("Yetkinlikler")

        for name_col, code_col in competency_cols:
            comp_name = row.get(name_col, "") if name_col else ""
            comp_code = row.get(code_col, "") if code_col else ""

            if pd.notna(comp_name) and str(comp_name).strip():
                st.markdown(
                    f"""
                    <div class="detail-card">
                        <b>{comp_name}</b>
                        <div class="uid-card">{comp_code}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
