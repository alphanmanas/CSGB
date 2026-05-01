import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="ÇSGB", layout="wide")

BASE_DIR = Path(__file__).parent

def normalize_text(x):
    x = str(x).strip().lower()
    tr_map = str.maketrans("çğıöşüİ", "cgiosui")
    x = x.translate(tr_map)
    x = re.sub(r"\s+", " ", x)
    return x

def find_file(extension, keywords):
    files = list(BASE_DIR.glob(f"*{extension}"))
    if not files:
        return None
    for f in files:
        name = normalize_text(f.name)
        if any(normalize_text(k) in name for k in keywords):
            return f
    return files[0]

EXCEL_FILE = find_file(".xlsx", ["çalışma", "csgb", "çsgb", "yetkinlik"])

def score_header(columns):
    joined = " ".join([normalize_text(c) for c in columns])
    score = 0
    for k in ["uid", "kod", "birim", "kurum", "pozisyon", "yetkinlik", "agirlik", "seviye", "olcum"]:
        if k in joined:
            score += 1
    return score

@st.cache_data
def load_best_excel(path):
    xls = pd.ExcelFile(path, engine="openpyxl")
    best_df = None
    best_score = -1

    for sheet in xls.sheet_names:
        for header_row in range(0, 10):
            try:
                temp = pd.read_excel(path, sheet_name=sheet, header=header_row, engine="openpyxl")
                temp.columns = [str(c).strip() for c in temp.columns]
                temp = temp.dropna(how="all")

                if temp.empty:
                    continue

                score = score_header(temp.columns)
                sample_text = " ".join(temp.astype(str).head(20).fillna("").values.flatten().tolist())

                if "ÇSGB-" in sample_text or "CSGB-" in sample_text:
                    score += 5

                if score > best_score:
                    best_score = score
                    best_df = temp
            except Exception:
                pass

    if best_df is None:
        return None

    best_df.columns = [str(c).strip() for c in best_df.columns]
    best_df = best_df.dropna(how="all")
    return best_df

if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı.")
    st.stop()

df = load_best_excel(EXCEL_FILE)

if df is None:
    st.error("Excel okunamadı.")
    st.stop()

def find_col(possible_names):
    possible = [normalize_text(x) for x in possible_names]

    for col in df.columns:
        col_norm = normalize_text(col)
        if col_norm in possible:
            return col

    for col in df.columns:
        col_norm = normalize_text(col)
        for p in possible:
            if p in col_norm or col_norm in p:
                return col

    return None

uid_col = find_col([
    "UID", "Kod", "KOD", "Kodu", "Pozisyon Kodu", "Birim Kodu",
    "Pozisyon UID", "Birim UID", "ID"
])

if uid_col is None:
    for col in df.columns:
        sample_values = df[col].dropna().astype(str).head(100).tolist()
        if any("ÇSGB-" in v or "CSGB-" in v for v in sample_values):
            uid_col = col
            break

unit_col = find_col([
    "Ana Birim / Kurum", "Ana Birim", "Kurum", "Birim",
    "Birim Adı", "Bağlı Birim", "Üst Birim"
])

position_col = find_col([
    "Pozisyon / Birim Adı", "Pozisyon", "Pozisyon Adı",
    "Birim Adı", "Ad", "Unvan", "Görev"
])

if position_col is None:
    position_col = unit_col

if unit_col is None:
    unit_col = position_col

if uid_col is None or unit_col is None or position_col is None:
    st.error("Excel yapısı algılanamadı.")
    st.stop()

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
        f"Yetkinlik {i} Kod",
        f"Yetkinlik{i} Kodu",
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
    font-size:19px;
    font-weight:800;
    margin-bottom:18px;
    box-shadow:0 3px 8px rgba(0,0,0,0.25);
}
.stButton button {
    font-weight:700 !important;
}
.detail-card {
    background:white;
    border:1px solid #ddd;
    border-radius:8px;
    padding:14px;
    margin-bottom:10px;
    box-shadow:0 2px 5px rgba(0,0,0,0.08);
}
.uid-card {
    background:#d8f2fb;
    border:1px solid #8fc8dc;
    padding:10px;
    margin-top:6px;
    font-weight:700;
    text-align:center;
}
.competency-card {
    background:#ffffff;
    border:1px solid #ddd;
    border-radius:8px;
    padding:12px;
    margin:8px 0 8px 25px;
    box-shadow:0 2px 4px rgba(0,0,0,0.06);
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Yetkinlik Haritası Çalışması</div>
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

top_titles = [
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bağlı Birimler"
]

aliases = {
    "Türkiye İş Kurumu Genel Müdürlüğü": ["Türkiye İş Kurumu", "İŞKUR", "ISKUR", "İşkur"],
    "Sosyal Güvenlik Kurumu": ["Sosyal Güvenlik Kurumu", "SGK"],
    "İş Sağlığı ve Güvenliği Genel Müdürlüğü": ["İş Sağlığı", "İSGGM", "ISGGM"],
    "Bilgi Teknolojileri Genel Müdürlüğü": ["Bilgi Teknolojileri"],
    "Çalışma Genel Müdürlüğü": ["Çalışma Genel"],
    "Mesleki Yeterlilik Kurumu": ["Mesleki Yeterlilik", "MYK"],
    "Rehberlik ve Teftiş Başkanlığı": ["Rehberlik ve Teftiş", "RTB"],
    "Personel Dairesi Başkanlığı": ["Personel Dairesi"],
    "Destek Hizmetleri Dairesi Başkanlığı": ["Destek Hizmetleri"],
    "Strateji Geliştirme Başkanlığı": ["Strateji Geliştirme"],
    "Hukuk Hizmetleri Genel Müdürlüğü": ["Hukuk Hizmetleri"],
    "İç Denetim Birimi Başkanlığı": ["İç Denetim"],
    "Özel Kalem Müdürlüğü": ["Özel Kalem"],
    "Basın ve Halkla İlişkiler Müşavirliği": ["Basın ve Halkla İlişkiler"],
    "Dış İlişkiler ve Avrupa Birliği Genel Müdürlüğü": ["Dış İlişkiler", "Avrupa Birliği"],
    "Uluslararası İşgücü Genel Müdürlüğü": ["Uluslararası İşgücü"],
    "Çalışma ve Sosyal Güvenlik Eğitim ve Araştırma Merkezi": ["Eğitim ve Araştırma", "ÇASGEM", "CASGEM"],
    "Ereğli Kömür Havzası Amele Birliği Biriktirme ve Yardımlaşma Sandığı": ["Ereğli", "Amele Birliği"],
}

def find_rows_for_unit(unit_name):
    terms = [unit_name] + aliases.get(unit_name, [])
    terms_norm = [normalize_text(t) for t in terms]

    mask = pd.Series(False, index=df.index)

    searchable_cols = [unit_col, position_col, uid_col]
    searchable_cols = [c for c in searchable_cols if c and c in df.columns]

    for col in searchable_cols:
        values = df[col].astype(str).apply(normalize_text)

        for term in terms_norm:
            mask = mask | values.str.contains(term, na=False)

        words = [w for w in normalize_text(unit_name).split() if len(w) >= 4]

        if words:
            mask = mask | values.apply(
                lambda x: sum(1 for w in words if w in x) >= min(2, len(words))
            )

    return df[mask].copy()

cols = st.columns(5)

for idx, (top_uid, units) in enumerate(org_groups.items()):
    with cols[idx]:
        title_text = top_titles[idx] if idx < len(top_titles) else top_uid
        st.markdown(f"<div class='org-red'>{title_text}</div>", unsafe_allow_html=True)

        for unit in units:
            if st.button(unit, key=f"{top_uid}_{unit}", use_container_width=True):
                st.session_state["selected_unit"] = unit

if "selected_unit" in st.session_state:
    selected_unit = st.session_state["selected_unit"]

    st.divider()
    st.subheader(selected_unit)

    unit_df = find_rows_for_unit(selected_unit)

    if unit_df.empty:
        st.warning("Bu birim Excel içinde bulunamadı.")
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

            toggle_key = f"toggle_{i}_{uid}"

            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False

            if st.button("Yetkinlikleri Göster", key=f"btn_{i}_{uid}", use_container_width=True):
                st.session_state[toggle_key] = not st.session_state[toggle_key]

            if st.session_state[toggle_key]:
                for name_col, code_col in competency_cols:
                    comp_name = row.get(name_col, "") if name_col else ""
                    comp_code = row.get(code_col, "") if code_col else ""

                    if pd.notna(comp_name) and str(comp_name).strip():
                        st.markdown(
                            f"""
                            <div class="competency-card">
                                <b>{comp_name}</b>
                                <div class="uid-card">{comp_code}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
