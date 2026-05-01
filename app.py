import streamlit as st
import pandas as pd
from PIL import Image
from pathlib import Path

st.set_page_config(page_title="ÇSGB Organizasyon Şeması", layout="wide")

BASE_DIR = Path(__file__).parent

def find_file(extension, preferred_keywords=None):
    preferred_keywords = preferred_keywords or []
    files = list(BASE_DIR.glob(f"*{extension}"))

    if not files:
        return None

    for f in files:
        name = f.name.lower()
        if any(k.lower() in name for k in preferred_keywords):
            return f

    return files[0]

EXCEL_FILE = find_file(".xlsx", ["Çalışma", "ÇSGB", "csgb"])
LOGO_FILE = find_file(".png", ["logo", "csgb"])

@st.cache_data
def load_excel(path):
    xls = pd.ExcelFile(path, engine="openpyxl")

    best_df = None
    best_score = -1

    for sheet in xls.sheet_names:
        temp = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        temp.columns = [str(c).strip() for c in temp.columns]

        score = 0
        joined_cols = " ".join(temp.columns).lower()

        for key in ["uid", "kod", "pozisyon", "birim", "yetkinlik"]:
            if key in joined_cols:
                score += 1

        if score > best_score:
            best_score = score
            best_df = temp

    best_df.columns = [str(c).strip() for c in best_df.columns]
    return best_df

if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı. Repo içine .xlsx dosyasını yükleyin.")
    st.stop()

df = load_excel(EXCEL_FILE)

def normalize(text):
    return str(text).strip().lower().replace("ı", "i").replace("İ", "i")

def find_col(possible_names):
    normalized_columns = {normalize(c): c for c in df.columns}

    for name in possible_names:
        n = normalize(name)
        if n in normalized_columns:
            return normalized_columns[n]

    for c in df.columns:
        cn = normalize(c)
        for name in possible_names:
            if normalize(name) in cn:
                return c

    return None

uid_col = find_col([
    "UID",
    "Kod",
    "KOD",
    "Kodu",
    "Pozisyon Kodu",
    "Birim Kodu",
    "Pozisyon UID",
    "Birim UID",
    "Unique ID",
    "ID"
])

unit_col = find_col([
    "Ana Birim",
    "Kurum",
    "Birim",
    "Birim Adı",
    "Ana Birim / Kurum",
    "Bağlı Birim",
    "Üst Birim"
])

position_col = find_col([
    "Pozisyon / Birim Adı",
    "Pozisyon",
    "Pozisyon Adı",
    "Birim Adı",
    "Ad",
    "Unvan",
    "Görev"
])

if uid_col is None:
    possible_uid_cols = []
    for c in df.columns:
        sample_values = df[c].dropna().astype(str).head(20).tolist()
        if any("ÇSGB-" in v or "CSGB-" in v for v in sample_values):
            possible_uid_cols.append(c)

    if possible_uid_cols:
        uid_col = possible_uid_cols[0]

if uid_col is None:
    st.error("UID/Kod kolonu otomatik bulunamadı.")
    st.write("Excel kolonları:")
    st.write(list(df.columns))
    st.stop()

if unit_col is None:
    unit_col = position_col if position_col else df.columns[0]

if position_col is None:
    position_col = unit_col

competency_cols = []

for i in range(1, 6):
    name_col = find_col([
        f"Yetkinlik {i} Adı",
        f"Yetkinlik {i}",
        f"Yetkinlik{i} Adı",
        f"Yetkinlik{i}"
    ])

    code_col = find_col([
        f"Yetkinlik {i} Kodu",
        f"Yetkinlik{i} Kodu",
        f"Yetkinlik {i} Kod",
        f"Yetkinlik{i} Kod"
    ])

    if name_col or code_col:
        competency_cols.append((name_col, code_col))

st.markdown("""
<style>
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
.org-button button {
    min-height:68px;
    border:2px solid #ddd !important;
    box-shadow:0 3px 8px rgba(0,0,0,0.15);
    background:#f8f8f8 !important;
    color:#111 !important;
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
    if LOGO_FILE:
        st.image(Image.open(LOGO_FILE), use_container_width=True)

st.markdown("""
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Organizasyon ve Yetkinlik Haritası</div>
</div>
""", unsafe_allow_html=True)

org_groups = {
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
    "ÇSGB-BAK": [
        "Basın ve Halkla İlişkiler Müşavirliği",
        "Destek Hizmetleri Dairesi Başkanlığı",
        "İç Denetim Birimi Başkanlığı",
        "Özel Kalem Müdürlüğü",
        "Personel Dairesi Başkanlığı",
        "Rehberlik ve Teftiş Başkanlığı",
    ],
}

cols = st.columns(5)

for idx, (top_uid, units) in enumerate(org_groups.items()):
    with cols[idx]:
        st.markdown(f"<div class='org-red'>{top_uid}</div>", unsafe_allow_html=True)

        for unit in units:
            st.markdown("<div class='org-button'>", unsafe_allow_html=True)
            if st.button(unit, key=f"unit_{top_uid}_{unit}", use_container_width=True):
                st.session_state["selected_unit"] = unit
                st.session_state["selected_uid"] = None
            st.markdown("</div>", unsafe_allow_html=True)

if "selected_unit" in st.session_state:
    selected_unit = st.session_state["selected_unit"]

    st.divider()
    st.subheader(selected_unit)

    unit_df = df[
        df[unit_col].astype(str).str.contains(selected_unit, case=False, na=False) |
        df[position_col].astype(str).str.contains(selected_unit, case=False, na=False)
    ]

    if unit_df.empty:
        st.warning("Bu birim Excel içinde birebir bulunamadı.")
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

    selected_row = df[df[uid_col].astype(str) == str(selected_uid)]

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

st.caption(f"Kullanılan Excel dosyası: {EXCEL_FILE.name}")
