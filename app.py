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

def find_file(extension):
    files = list(BASE_DIR.glob(f"*{extension}"))
    return files[0] if files else None

EXCEL_FILE = find_file(".xlsx")

@st.cache_data
def load_data(path):
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = load_data(EXCEL_FILE)

uid_col = [c for c in df.columns if "UID" in c.upper() or "KOD" in c.upper()][0]
unit_col = [c for c in df.columns if "BİRİM" in c.upper() or "KURUM" in c.upper()][0]
position_col = [c for c in df.columns if "POZİSYON" in c.upper() or "ADI" in c.upper()][0]

competency_cols = [(f"Yetkinlik {i} Adı", f"Yetkinlik {i} Kodu") for i in range(1,6)]

st.markdown("""
<style>
.title-box {
    border:2px solid #ddd;
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
}
.uid-card {
    background:#d8f2fb;
    padding:8px;
    margin-top:6px;
    text-align:center;
    font-weight:700;
}
.competency-card {
    margin-left:25px;
    padding:10px;
    border:1px solid #ddd;
    border-radius:6px;
}
</style>
""", unsafe_allow_html=True)

# BAŞLIK
st.markdown("""
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Yetkinlik Haritası Çalışması</div>
</div>
""", unsafe_allow_html=True)

org_groups = {
    "BY1": [
        "Dış İlişkiler ve Avrupa Birliği Genel Müdürlüğü",
        "Sosyal Güvenlik Kurumu",
        "Strateji Geliştirme Başkanlığı",
    ],
    "BY2": [
        "Bilgi Teknolojileri Genel Müdürlüğü",
        "Hukuk Hizmetleri Genel Müdürlüğü",
        "Çalışma ve Sosyal Güvenlik Eğitim ve Araştırma Merkezi",
        "Ereğli Kömür Havzası Amele Birliği Biriktirme ve Yardımlaşma Sandığı",
    ],
    "BY3": [
        "Çalışma Genel Müdürlüğü",
        "Uluslararası İşgücü Genel Müdürlüğü",
        "Mesleki Yeterlilik Kurumu",
    ],
    "BY4": [
        "İş Sağlığı ve Güvenliği Genel Müdürlüğü",
        "Türkiye İş Kurumu Genel Müdürlüğü",
    ],
    "BAK": [
        "Basın ve Halkla İlişkiler Müşavirliği",
        "Destek Hizmetleri Dairesi Başkanlığı",
        "İç Denetim Birimi Başkanlığı",
        "Özel Kalem Müdürlüğü",
        "Personel Dairesi Başkanlığı",
        "Rehberlik ve Teftiş Başkanlığı",
    ],
}

titles = [
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bakan Yardımcısı",
    "Bağlı Birimler"
]

cols = st.columns(5)

for idx, (k, units) in enumerate(org_groups.items()):
    with cols[idx]:
        st.markdown(f"<div class='org-red'>{titles[idx]}</div>", unsafe_allow_html=True)

        for unit in units:
            if st.button(unit, key=f"{k}_{unit}", use_container_width=True):
                st.session_state["selected_unit"] = unit

# ALT KISIM
if "selected_unit" in st.session_state:
    selected = st.session_state["selected_unit"]

    st.divider()
    st.subheader(selected)

    sub_df = df[df[unit_col].astype(str).str.contains(selected, case=False, na=False)]

    for i, row in sub_df.iterrows():
        st.markdown(f"""
        <div class="detail-card">
            <b>{row[position_col]}</b>
            <div class="uid-card">{row[uid_col]}</div>
        </div>
        """, unsafe_allow_html=True)

        toggle = f"toggle_{i}"

        if toggle not in st.session_state:
            st.session_state[toggle] = False

        if st.button("Yetkinlikleri Göster", key=f"btn_{i}"):
            st.session_state[toggle] = not st.session_state[toggle]

        if st.session_state[toggle]:
            for name, code in competency_cols:
                if name in df.columns:
                    st.markdown(f"""
                    <div class="competency-card">
                        <b>{row[name]}</b><br>
                        {row[code]}
                    </div>
                    """, unsafe_allow_html=True)
