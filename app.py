import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="ÇSGB Yetkinlik Haritası", layout="wide")

BASE_DIR = Path(__file__).parent


# =========================================================
# TEMEL YARDIMCI FONKSİYONLAR
# =========================================================

def normalize_text(x):
    if pd.isna(x):
        return ""
    x = str(x).strip().lower()
    tr_map = str.maketrans("çğıöşüİ", "cgiosui")
    x = x.translate(tr_map)
    x = re.sub(r"\s+", " ", x)
    return x


def clean_value(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def is_csgb_uid(value):
    """
    Pozisyon/Birim UID kontrolü.
    KY-HRK-06, OF-DEN-02 gibi master yetkinlik kodlarını dışarıda bırakır.
    """
    text = clean_value(value).upper()
    return bool(re.match(r"^(ÇSGB|CSGB|ÇSGK|CSGK)-", text))


def find_file(extension, keywords):
    files = list(BASE_DIR.glob(f"*{extension}"))
    if not files:
        return None

    for f in files:
        name = normalize_text(f.name)
        if any(normalize_text(k) in name for k in keywords):
            return f

    return files[0]


EXCEL_FILE = find_file(
    ".xlsx",
    ["çalışma", "csgb", "çsgb", "yetkinlik", "matrisi"]
)


# =========================================================
# EXCEL OKUMA
# =========================================================

def score_header(columns):
    joined = " ".join([normalize_text(c) for c in columns])
    score = 0

    for k in [
        "uid",
        "ana birim",
        "kurum",
        "pozisyon",
        "birim adi",
        "yetkinlik 1",
        "yetkinlik 1 adi",
        "yetkinlik 1 kodu",
    ]:
        if normalize_text(k) in joined:
            score += 1

    return score


@st.cache_data
def load_excel_matrix(path):
    """
    Öncelik doğru yetkinlik matrisi sheet'indedir.
    Yanlışlıkla MASTER_YETKINLIK_LISTESI veya ÇSGB Kodlama okunmasın diye
    özellikle Yetkinlik Matrisi v03 aranır.
    """
    xls = pd.ExcelFile(path, engine="openpyxl")

    preferred_sheets = [
        "Yetkinlik Matrisi v03",
        "Yetkinlik Matrisi",
        "Yetkinlik Matrisi v02",
    ]

    # 1) Önce tercih edilen sheet adlarını ara
    for preferred in preferred_sheets:
        for sheet in xls.sheet_names:
            if normalize_text(sheet) == normalize_text(preferred):
                for header_row in range(0, 10):
                    try:
                        temp = pd.read_excel(
                            path,
                            sheet_name=sheet,
                            header=header_row,
                            engine="openpyxl"
                        )
                        temp.columns = [str(c).strip() for c in temp.columns]
                        temp = temp.dropna(how="all")

                        joined_cols = " ".join([normalize_text(c) for c in temp.columns])

                        if "uid" in joined_cols and "yetkinlik" in joined_cols:
                            return temp, sheet, header_row
                    except Exception:
                        pass

    # 2) Sheet adı tutmazsa en iyi aday sheet'i bul
    best_df = None
    best_score = -1
    best_sheet = None
    best_header = None

    for sheet in xls.sheet_names:
        # Master yetkinlik listesini doğrudan ele
        if "master" in normalize_text(sheet):
            continue

        for header_row in range(0, 10):
            try:
                temp = pd.read_excel(
                    path,
                    sheet_name=sheet,
                    header=header_row,
                    engine="openpyxl"
                )
                temp.columns = [str(c).strip() for c in temp.columns]
                temp = temp.dropna(how="all")

                if temp.empty:
                    continue

                score = score_header(temp.columns)
                sample_text = " ".join(
                    temp.astype(str).head(50).fillna("").values.flatten().tolist()
                )

                if "ÇSGB-" in sample_text or "CSGB-" in sample_text or "ÇSGK-" in sample_text:
                    score += 8

                if "KY-HRK" in sample_text or "OF-DEN" in sample_text:
                    score -= 2

                if score > best_score:
                    best_score = score
                    best_df = temp
                    best_sheet = sheet
                    best_header = header_row

            except Exception:
                pass

    return best_df, best_sheet, best_header


if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı. app.py ile aynı klasöre Excel dosyasını koyun.")
    st.stop()

df, loaded_sheet, loaded_header = load_excel_matrix(EXCEL_FILE)

if df is None or df.empty:
    st.error("Excel okunamadı veya uygun Yetkinlik Matrisi sheet'i bulunamadı.")
    st.stop()

df.columns = [str(c).strip() for c in df.columns]
df = df.dropna(how="all").copy()


# =========================================================
# KOLON BULMA
# =========================================================

def find_col_exact(possible_names):
    possible = [normalize_text(x) for x in possible_names]

    for col in df.columns:
        if normalize_text(col) in possible:
            return col

    return None


def find_col_soft(possible_names):
    possible = [normalize_text(x) for x in possible_names]

    # Önce tam eşleşme
    for col in df.columns:
        col_norm = normalize_text(col)
        if col_norm in possible:
            return col

    # Sonra kontrollü yakın eşleşme
    for col in df.columns:
        col_norm = normalize_text(col)
        for p in possible:
            if p in col_norm:
                return col

    return None


uid_col = find_col_soft([
    "UID",
    "Pozisyon UID",
    "Birim UID",
    "Pozisyon Kodu",
    "Birim Kodu",
])

if uid_col is None:
    for col in df.columns:
        sample_values = df[col].dropna().astype(str).head(200).tolist()
        if any(is_csgb_uid(v) for v in sample_values):
            uid_col = col
            break

unit_col = find_col_soft([
    "Ana Birim / Kurum",
    "Ana Birim",
    "Kurum",
    "Üst Birim",
])

position_col = find_col_soft([
    "Pozisyon / Birim Adı",
    "Pozisyon Adı",
    "Pozisyon",
    "Birim Adı",
    "Ad",
    "Unvan",
])

if uid_col is None or unit_col is None or position_col is None:
    st.error("UID, Ana Birim/Kurum veya Pozisyon/Birim Adı kolonu bulunamadı.")
    st.write("Algılanan kolonlar:", list(df.columns))
    st.stop()


# =========================================================
# SADECE ÇSGB POZİSYON SATIRLARINI TUT
# =========================================================

df[uid_col] = df[uid_col].astype(str).str.strip()

df = df[df[uid_col].apply(is_csgb_uid)].copy()

df = df[
    df[position_col].notna() &
    df[unit_col].notna()
].copy()

df = df.drop_duplicates(subset=[uid_col]).reset_index(drop=True)


# =========================================================
# YETKİNLİK KOLONLARI
# =========================================================

def find_competency_columns(dataframe):
    """
    Yetkinlik kolonlarını güvenli şekilde bulur.
    Ağırlık, seviye, ölçüm tipi kolonlarını yetkinlik adı sanmaz.
    """
    result = []
    normalized_map = {
        normalize_text(col): col
        for col in dataframe.columns
    }

    for i in range(1, 6):
        name_col = None
        code_col = None

        code_candidates = [
            f"yetkinlik {i} kodu",
            f"yetkinlik {i} kod",
            f"yetkinlik{i} kodu",
            f"yetkinlik{i} kod",
        ]

        name_candidates = [
            f"yetkinlik {i} adi",
            f"yetkinlik {i} ad",
            f"yetkinlik{i} adi",
            f"yetkinlik{i} ad",
        ]

        single_candidates = [
            f"yetkinlik {i}",
            f"yetkinlik{i}",
        ]

        # Kod kolonunu kesin bul
        for norm_col, original_col in normalized_map.items():
            if norm_col in code_candidates:
                code_col = original_col
                break

        # Ad kolonunu kesin bul
        for norm_col, original_col in normalized_map.items():
            if norm_col in name_candidates:
                name_col = original_col
                break

        # Eski v02 formatında tek kolon varsa
        if name_col is None:
            for norm_col, original_col in normalized_map.items():
                if norm_col in single_candidates:
                    name_col = original_col
                    break

        if name_col or code_col:
            result.append((name_col, code_col))

    return result


competency_cols = find_competency_columns(df)


def split_competency_value(value):
    """
    'OF-DEN-02 - Risk Bazlı Denetim'
    veya
    'OF-DEN-02 – Risk Bazlı Denetim'
    formatını ad/kod olarak ayırır.
    """
    if pd.isna(value):
        return "", ""

    text = str(value).strip()

    m = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,3}-[A-ZÇĞİÖŞÜ]{2,5}-\d{2})\s*[-–]\s*(.+)$",
        text
    )

    if m:
        code = m.group(1).strip()
        name = m.group(2).strip()
        return name, code

    # Sadece kod gelirse
    m2 = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,3}-[A-ZÇĞİÖŞÜ]{2,5}-\d{2})$",
        text
    )

    if m2:
        return "", m2.group(1).strip()

    return text, ""


def get_competencies_from_row(row):
    competencies = []

    for name_col, code_col in competency_cols:
        raw_name = row.get(name_col, "") if name_col else ""
        raw_code = row.get(code_col, "") if code_col else ""

        comp_name = clean_value(raw_name)
        comp_code = clean_value(raw_code)

        # Tek hücrede "KOD - AD" varsa parçala
        if comp_name:
            parsed_name, parsed_code = split_competency_value(comp_name)
            if parsed_code:
                comp_name = parsed_name
                comp_code = parsed_code

        # Kod kolonuna yanlışlıkla "KOD - AD" gelirse parçala
        if comp_code and " - " in comp_code:
            parsed_name, parsed_code = split_competency_value(comp_code)
            if parsed_code:
                comp_name = parsed_name
                comp_code = parsed_code

        # Boş veya yanlış değerleri temizle
        if not comp_name and not comp_code:
            continue

        # UID gibi pozisyon kodu yetkinlik olarak görünmesin
        if is_csgb_uid(comp_name) or is_csgb_uid(comp_code):
            continue

        competencies.append({
            "name": comp_name,
            "code": comp_code
        })

    return competencies


# =========================================================
# ORGANİZASYON GRUPLARI
# =========================================================

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
    "Bağlı Birimler",
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
    """
    Birime ait satırları güvenli biçimde bulur.
    Önce Ana Birim/Kurum kolonuna bakar.
    Master yetkinlik satırları zaten df filtresinde temizlendiği için
    KY-HRK-06 gibi kodlar pozisyon olarak gelmez.
    """
    terms = [unit_name] + aliases.get(unit_name, [])
    terms_norm = [normalize_text(t) for t in terms]

    unit_values = df[unit_col].astype(str).apply(normalize_text)

    mask = pd.Series(False, index=df.index)

    # Ana Birim/Kurum tam eşleşme
    for term in terms_norm:
        mask = mask | (unit_values == term)

    # Ana Birim/Kurum içerir eşleşme
    if not mask.any():
        for term in terms_norm:
            mask = mask | unit_values.str.contains(term, na=False, regex=False)

    # Son çare: pozisyon adında ara
    if not mask.any():
        pos_values = df[position_col].astype(str).apply(normalize_text)
        for term in terms_norm:
            mask = mask | pos_values.str.contains(term, na=False, regex=False)

    unit_df = df[mask].copy()

    unit_df = unit_df[
        unit_df[uid_col].apply(is_csgb_uid) &
        unit_df[position_col].notna()
    ].copy()

    unit_df = unit_df.drop_duplicates(subset=[uid_col])

    # Ana birim satırı en üste gelsin
    def sort_key(row):
        uid = clean_value(row[uid_col]).upper()
        pos = normalize_text(row[position_col])
        unit = normalize_text(row[unit_col])

        is_main = (
            uid.endswith("-XXX") or
            pos == normalize_text(unit_name) or
            unit == normalize_text(unit_name)
        )

        return (0 if is_main else 1, uid)

    if not unit_df.empty:
        unit_df["_sort_key"] = unit_df.apply(sort_key, axis=1)
        unit_df = unit_df.sort_values("_sort_key").drop(columns=["_sort_key"])

    return unit_df


def get_unit_uid(unit_name):
    unit_df = find_rows_for_unit(unit_name)

    if unit_df.empty:
        return ""

    # Ana birim / kurum satırını seçmeye çalış
    exact = unit_df[
        unit_df[position_col].astype(str).apply(normalize_text) == normalize_text(unit_name)
    ]

    if not exact.empty:
        return clean_value(exact.iloc[0][uid_col])

    xxx = unit_df[
        unit_df[uid_col].astype(str).str.upper().str.endswith("-XXX")
    ]

    if not xxx.empty:
        return clean_value(xxx.iloc[0][uid_col])

    return clean_value(unit_df.iloc[0][uid_col])


# =========================================================
# CSS
# =========================================================

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
    font-size:18px;
    font-weight:800;
    margin-bottom:18px;
    box-shadow:0 3px 8px rgba(0,0,0,0.25);
}
.stButton button {
    font-weight:700 !important;
    min-height:34px;
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
.small-note {
    font-size:12px;
    color:#666;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# ÜST BAŞLIK
# =========================================================

st.markdown("""
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Yetkinlik Haritası Çalışması</div>
</div>
""", unsafe_allow_html=True)

with st.expander("Veri kontrol bilgisi", expanded=False):
    st.write("Okunan Excel:", EXCEL_FILE.name)
    st.write("Okunan Sheet:", loaded_sheet)
    st.write("Header Satırı:", loaded_header)
    st.write("UID Kolonu:", uid_col)
    st.write("Ana Birim / Kurum Kolonu:", unit_col)
    st.write("Pozisyon / Birim Adı Kolonu:", position_col)
    st.write("Yetkinlik Kolonları:", competency_cols)
    st.write("Kullanılan pozisyon satırı sayısı:", len(df))


# =========================================================
# ORGANİZASYON ŞEMASI
# =========================================================

cols = st.columns(5)

for idx, (top_uid, units) in enumerate(org_groups.items()):
    with cols[idx]:
        title_text = top_titles[idx] if idx < len(top_titles) else top_uid

        st.markdown(
            f"""
            <div class='org-red'>
                {title_text}
                <div style="font-size:12px; margin-top:4px;">{top_uid}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        for unit in units:
            unit_uid = get_unit_uid(unit)
            button_label = unit

            if st.button(button_label, key=f"{top_uid}_{unit}", use_container_width=True):
                st.session_state["selected_unit"] = unit

                # Eski açık yetkinlikleri kapat
                for k in list(st.session_state.keys()):
                    if str(k).startswith("toggle_"):
                        del st.session_state[k]

            if unit_uid:
                st.markdown(
                    f"<div class='small-note'>{unit_uid}</div>",
                    unsafe_allow_html=True
                )


# =========================================================
# SEÇİLEN BİRİM DETAYI
# =========================================================

if "selected_unit" in st.session_state:
    selected_unit = st.session_state["selected_unit"]

    st.divider()
    st.subheader(selected_unit)

    unit_df = find_rows_for_unit(selected_unit)

    if unit_df.empty:
        st.warning("Bu birim Excel içinde bulunamadı.")
    else:
        for i, row in unit_df.iterrows():
            position_name = clean_value(row.get(position_col, ""))
            uid = clean_value(row.get(uid_col, ""))

            st.markdown(
                f"""
                <div class="detail-card">
                    <b>{position_name}</b>
                    <div class="uid-card">{uid}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            toggle_key = f"toggle_{uid}"

            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False

            if st.button(
                "Yetkinlikleri Göster",
                key=f"btn_{uid}",
                use_container_width=True
            ):
                st.session_state[toggle_key] = not st.session_state[toggle_key]

            if st.session_state[toggle_key]:
                competencies = get_competencies_from_row(row)

                if not competencies:
                    st.info("Bu satır için yetkinlik bulunamadı.")
                else:
                    for comp in competencies:
                        comp_name = comp["name"]
                        comp_code = comp["code"]

                        st.markdown(
                            f"""
                            <div class="competency-card">
                                <b>{comp_name}</b>
                                <div class="uid-card">{comp_code}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
