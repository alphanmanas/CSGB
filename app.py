import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(
    page_title="ÇSGB Yetkinlik Haritası",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
DEFAULT_EXCEL_PATH = BASE_DIR / "data" / "csgb_yetkinlik.xlsx"

TARGET_ORG_SHEET = "ÇSGB Kodlama"
TARGET_COMPETENCY_SHEET = "Yetkinlik Matrisi"
TARGET_MASTER_SHEET = "Master Yetkinlik Listesi"


# =========================================================
# TEMEL FONKSİYONLAR
# =========================================================

def normalize_text(x):
    if pd.isna(x):
        return ""

    text = str(x).strip()

    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.replace('"', "")
    text = text.replace("'", "")

    tr_map = str.maketrans({
        "Ç": "c", "ç": "c",
        "Ğ": "g", "ğ": "g",
        "İ": "i", "I": "i", "ı": "i",
        "Ö": "o", "ö": "o",
        "Ş": "s", "ş": "s",
        "Ü": "u", "ü": "u",
    })

    text = text.translate(tr_map)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_value(x):
    if pd.isna(x):
        return ""

    text = str(x).strip()
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")

    if text.lower() in ["nan", "none", "null"]:
        return ""

    return text.strip()


def normalize_uid(x):
    text = clean_value(x).upper()
    text = text.replace("CSGB-", "ÇSGB-")
    text = text.replace("CSGK-", "ÇSGK-")
    return text


def is_position_uid(value):
    text = normalize_uid(value)
    return bool(re.match(r"^(ÇSGB|ÇSGK)-", text))


def is_competency_code(value):
    text = clean_value(value).upper()
    return bool(re.match(r"^[A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,12}-\d{2}$", text))


def find_col(df, candidates, exact=False, forbidden=None):
    forbidden = [normalize_text(x) for x in (forbidden or [])]
    candidates_norm = [normalize_text(c) for c in candidates]

    for col in df.columns:
        col_norm = normalize_text(col)

        if any(f in col_norm for f in forbidden):
            continue

        if col_norm in candidates_norm:
            return col

    if not exact:
        for col in df.columns:
            col_norm = normalize_text(col)

            if any(f in col_norm for f in forbidden):
                continue

            for cand in candidates_norm:
                if cand and cand in col_norm:
                    return col

    return None


def find_excel_file():
    if DEFAULT_EXCEL_PATH.exists():
        return DEFAULT_EXCEL_PATH

    files = list(BASE_DIR.glob("*.xlsx"))

    data_dir = BASE_DIR / "data"
    if data_dir.exists():
        files.extend(list(data_dir.glob("*.xlsx")))

    if not files:
        return None

    for file in files:
        name = normalize_text(file.name)
        if "csgb" in name or "yetkinlik" in name or "kodlama" in name:
            return file

    return files[0]


def read_sheet_best_header(path, sheet_name):
    best_df = None
    best_score = -999
    best_header = None

    for header_row in range(0, 15):
        try:
            df = pd.read_excel(
                path,
                sheet_name=sheet_name,
                header=header_row,
                engine="openpyxl"
            )

            df.columns = [str(c).strip() for c in df.columns]
            df = df.dropna(how="all")

            if df.empty:
                continue

            cols = " ".join(normalize_text(c) for c in df.columns)

            sample = " ".join(
                df.astype(str)
                .head(100)
                .fillna("")
                .values
                .flatten()
                .tolist()
            )

            score = 0

            if "uid" in cols:
                score += 50
            if "ana birim" in cols:
                score += 30
            if "pozisyon" in cols:
                score += 30
            if "yetkinlik" in cols:
                score += 40
            if "yetkinlik kod" in cols:
                score += 50
            if "ÇSGB-" in sample or "CSGB-" in sample or "ÇSGK-" in sample or "CSGK-" in sample:
                score += 50

            if score > best_score:
                best_score = score
                best_df = df
                best_header = header_row

        except Exception:
            pass

    return best_df, best_header


def get_exact_sheet(path, target_sheet, required=True):
    xls = pd.ExcelFile(path, engine="openpyxl")

    for sheet_name in xls.sheet_names:
        if normalize_text(sheet_name) == normalize_text(target_sheet):
            df, header = read_sheet_best_header(path, sheet_name)

            if df is None:
                st.error(f"'{target_sheet}' sayfası okunamadı.")
                st.stop()

            return sheet_name, df, header

    if required:
        st.error(f"Excel içinde '{target_sheet}' sayfası bulunamadı.")
        st.write("Bulunan sayfalar:", xls.sheet_names)
        st.stop()

    return None, pd.DataFrame(), None


# =========================================================
# EXCEL YÜKLE
# =========================================================

EXCEL_FILE = find_excel_file()

if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı. Excel dosyasını app.py ile aynı klasöre veya data/csgb_yetkinlik.xlsx yoluna koy.")
    st.stop()

org_sheet, org_raw_df, org_header = get_exact_sheet(EXCEL_FILE, TARGET_ORG_SHEET, required=True)
comp_sheet, comp_raw_df, comp_header = get_exact_sheet(EXCEL_FILE, TARGET_COMPETENCY_SHEET, required=True)
master_sheet, master_raw_df, master_header = get_exact_sheet(EXCEL_FILE, TARGET_MASTER_SHEET, required=False)


# =========================================================
# ORGANİZASYON KOLONLARI
# =========================================================

uid_col = find_col(org_raw_df, ["UID"], exact=True)

baglilik_col = find_col(
    org_raw_df,
    ["Bağlılık Kodu", "Baglilik Kodu"]
)

unit_col = find_col(
    org_raw_df,
    ["Ana Birim / Kurum", "Ana Birim", "Kurum"]
)

level_col = find_col(
    org_raw_df,
    ["Seviye"],
    exact=True
)

position_type_col = find_col(
    org_raw_df,
    ["Pozisyon Türü", "Pozisyon Turu"]
)

position_col = find_col(
    org_raw_df,
    [
        "Pozisyon / Birim Adı",
        "Pozisyon / Birim Adi",
        "Pozisyon Adı",
        "Pozisyon Adi",
        "Pozisyon",
        "Birim Adı",
        "Birim Adi"
    ]
)

main_code_col = find_col(
    org_raw_df,
    ["Ana Birim Kodu"]
)

if uid_col is None or unit_col is None or position_col is None:
    st.error("ÇSGB Kodlama sayfasında gerekli kolonlar bulunamadı.")
    st.write("Bulunan kolonlar:", list(org_raw_df.columns))
    st.stop()


# =========================================================
# ORGANİZASYON VERİSİ
# =========================================================

org_df = org_raw_df.copy()
org_df["_excel_order"] = range(len(org_df))

for col in [
    uid_col,
    baglilik_col,
    unit_col,
    level_col,
    position_type_col,
    position_col,
    main_code_col
]:
    if col and col in org_df.columns:
        org_df[col] = org_df[col].apply(clean_value)

org_df[uid_col] = org_df[uid_col].apply(normalize_uid)

org_df = org_df[org_df[uid_col].apply(is_position_uid)].copy()

org_df = org_df[
    (org_df[uid_col] != "")
    & (org_df[unit_col] != "")
    & (org_df[position_col] != "")
].copy()

org_df = org_df.drop_duplicates(subset=[uid_col], keep="first").reset_index(drop=True)


# =========================================================
# MASTER KOD -> AD
# =========================================================

def build_master_lookup(master_df):
    lookup = {}

    if master_df is None or master_df.empty:
        return lookup

    code_col = find_col(
        master_df,
        ["Yetkinlik Kodu", "Kod", "Kodu"],
        forbidden=["uid", "pozisyon", "birim"]
    )

    name_col = find_col(
        master_df,
        ["Yetkinlik Adı", "Yetkinlik Adi", "Yetkinlik"],
        forbidden=["kodu", "kod", "uid"]
    )

    if code_col is None or name_col is None:
        return lookup

    for _, row in master_df.iterrows():
        code = clean_value(row.get(code_col, "")).upper()
        name = clean_value(row.get(name_col, ""))

        if is_competency_code(code) and name:
            lookup[code] = name

    return lookup


master_lookup = build_master_lookup(master_raw_df)


# =========================================================
# YETKİNLİK MATRİSİ KOLONLARI
# =========================================================

def find_comp_uid_col(df):
    col = find_col(
        df,
        ["UID", "Pozisyon UID", "Birim UID", "Pozisyon Kodu", "Birim Kodu"],
        exact=True
    )

    if col:
        return col

    for c in df.columns:
        sample = df[c].dropna().astype(str).head(300).tolist()

        if any(is_position_uid(v) for v in sample):
            return c

    return None


def find_competency_columns(df):
    """
    Sadece Yetkinlik 1-10 Ad/Kod sütunlarını yakalar.
    Ağırlık, Seviye, Hedef, Ölçüm gibi yardımcı sütunları almaz.
    """
    cols = [(normalize_text(c), c) for c in df.columns]
    result = []

    forbidden_words = [
        "agirlik",
        "agırlık",
        "ağırlık",
        "seviye",
        "hedef",
        "olcum",
        "ölçüm",
        "tip",
        "tur",
        "tür",
        "aciklama",
        "açıklama",
        "not"
    ]

    for i in range(1, 11):
        code_col = None
        name_col = None

        for norm, original in cols:
            if any(w in norm for w in forbidden_words):
                continue

            code_patterns = [
                f"yetkinlik {i} kodu",
                f"yetkinlik {i} kod",
                f"yetkinlik{i} kodu",
                f"yetkinlik{i} kod",
                f"yetkinlik kodu {i}",
                f"yetkinlik kod {i}",
                f"{i}. yetkinlik kodu",
                f"{i}. yetkinlik kod"
            ]

            if norm in code_patterns:
                code_col = original
                break

        for norm, original in cols:
            if any(w in norm for w in forbidden_words):
                continue

            name_patterns = [
                f"yetkinlik {i} adi",
                f"yetkinlik {i} ad",
                f"yetkinlik{i} adi",
                f"yetkinlik{i} ad",
                f"yetkinlik adi {i}",
                f"yetkinlik ad {i}",
                f"{i}. yetkinlik adi",
                f"{i}. yetkinlik ad"
            ]

            if norm in name_patterns:
                name_col = original
                break

        if name_col is None and code_col is None:
            for norm, original in cols:
                if any(w in norm for w in forbidden_words):
                    continue

                plain_patterns = [
                    f"yetkinlik {i}",
                    f"yetkinlik{i}",
                    f"{i}. yetkinlik"
                ]

                if norm in plain_patterns:
                    name_col = original
                    break

        if name_col or code_col:
            result.append((name_col, code_col))

    return result


def split_comp_value(value):
    text = clean_value(value)

    if not text:
        return "", ""

    match = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,12}-\d{2})\s*[-–—|]\s*(.+)$",
        text,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(2).strip(), match.group(1).strip().upper()

    match = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,12}-\d{2})$",
        text,
        flags=re.IGNORECASE
    )

    if match:
        return "", match.group(1).strip().upper()

    return text, ""


comp_uid_col = find_comp_uid_col(comp_raw_df)
comp_cols = find_competency_columns(comp_raw_df)

if comp_uid_col is None:
    st.error("Yetkinlik Matrisi sayfasında UID kolonu bulunamadı.")
    st.write("Bulunan kolonlar:", list(comp_raw_df.columns))
    st.stop()

if not comp_cols:
    st.error("Yetkinlik Matrisi sayfasında Yetkinlik 1-10 Ad/Kod kolonları bulunamadı.")
    st.write("Bulunan kolonlar:", list(comp_raw_df.columns))
    st.stop()


# =========================================================
# YETKİNLİK MAP
# =========================================================

def build_competency_map(df):
    comp_map = {}

    temp = df.copy()
    temp[comp_uid_col] = temp[comp_uid_col].apply(normalize_uid)
    temp = temp[temp[comp_uid_col].apply(is_position_uid)].copy()

    for _, row in temp.iterrows():
        uid = normalize_uid(row.get(comp_uid_col, ""))

        if not uid:
            continue

        competencies = []
        seen = set()

        for name_col, code_col in comp_cols:
            raw_name = row.get(name_col, "") if name_col else ""
            raw_code = row.get(code_col, "") if code_col else ""

            comp_name = clean_value(raw_name)
            comp_code = clean_value(raw_code).upper()

            if comp_name:
                parsed_name, parsed_code = split_comp_value(comp_name)

                if parsed_code:
                    comp_name = parsed_name
                    comp_code = parsed_code

            if comp_code:
                parsed_name, parsed_code = split_comp_value(comp_code)

                if parsed_code:
                    comp_code = parsed_code

                    if parsed_name and not comp_name:
                        comp_name = parsed_name

            if comp_code and not comp_name:
                comp_name = master_lookup.get(comp_code, "")

            if not comp_name and not comp_code:
                continue

            if is_position_uid(comp_name) or is_position_uid(comp_code):
                continue

            key = (comp_code, comp_name)

            if key in seen:
                continue

            seen.add(key)

            competencies.append(
                {
                    "code": comp_code,
                    "name": comp_name
                }
            )

        if uid not in comp_map:
            comp_map[uid] = competencies

    return comp_map


competency_map = build_competency_map(comp_raw_df)


def get_competencies_for_uid(uid):
    uid = normalize_uid(uid)
    return competency_map.get(uid, [])


# =========================================================
# ORGANİZASYON GRUPLAMA
# =========================================================

def is_top_manager_row(row):
    pos = normalize_text(row.get(position_col, ""))
    unit = normalize_text(row.get(unit_col, ""))

    return (
        pos == "bakan"
        or unit == "bakan"
        or "bakan yardimcisi" in pos
        or "bakan yardimcisi" in unit
    )


def is_main_unit_row(row):
    uid = normalize_uid(row.get(uid_col, ""))
    level = normalize_text(row.get(level_col, "")) if level_col else ""
    ptype = normalize_text(row.get(position_type_col, "")) if position_type_col else ""

    return (
        "ana birim" in level
        or "ana birim" in ptype
        or uid.endswith("-XXX")
    )


def get_group_code(row):
    if baglilik_col and baglilik_col in row:
        code = clean_value(row.get(baglilik_col, ""))

        if code:
            return code

    uid = normalize_uid(row.get(uid_col, ""))
    parts = uid.split("-")

    if len(parts) >= 2:
        return parts[1]

    return "DİĞER"


main_units_df = org_df[org_df.apply(is_main_unit_row, axis=1)].copy()
main_units_df = main_units_df[~main_units_df.apply(is_top_manager_row, axis=1)].copy()

main_units_df["_group"] = main_units_df.apply(get_group_code, axis=1)
main_units_df = main_units_df.sort_values("_excel_order")

preferred_order = ["BY1", "BY2", "BY3", "BY4", "BAK"]

all_groups = main_units_df["_group"].dropna().unique().tolist()
ordered_groups = [g for g in preferred_order if g in all_groups]
ordered_groups += [g for g in all_groups if g not in ordered_groups]


def group_title(group_code):
    if str(group_code).startswith("BY"):
        return "Bakan Yardımcısı"

    if group_code == "BAK":
        return "Bağlı Birimler"

    return str(group_code)


def get_rows_for_unit(unit_uid, unit_name):
    unit_uid = normalize_uid(unit_uid)
    unit_name_norm = normalize_text(unit_name)

    unit_code = ""

    main_row = org_df[org_df[uid_col] == unit_uid]

    if not main_row.empty and main_code_col:
        unit_code = clean_value(main_row.iloc[0].get(main_code_col, ""))

    rows = org_df[
        org_df[unit_col].astype(str).apply(normalize_text) == unit_name_norm
    ].copy()

    if unit_code and main_code_col:
        rows_by_code = org_df[
            org_df[main_code_col].astype(str).apply(clean_value) == unit_code
        ].copy()

        rows = pd.concat([rows, rows_by_code], ignore_index=True)

    if rows.empty and unit_uid:
        prefix = "-".join(unit_uid.split("-")[:3])

        rows = org_df[
            org_df[uid_col].astype(str).str.startswith(prefix, na=False)
        ].copy()

    rows = rows[rows[uid_col].apply(is_position_uid)].copy()
    rows = rows.drop_duplicates(subset=[uid_col])

    if rows.empty:
        return rows

    def sort_key(row):
        uid = normalize_uid(row.get(uid_col, ""))
        pos = normalize_text(row.get(position_col, ""))
        unit = normalize_text(row.get(unit_col, ""))
        level = normalize_text(row.get(level_col, "")) if level_col else ""

        is_main = (
            uid == unit_uid
            or uid.endswith("-XXX")
            or pos == unit_name_norm
            or ("ana birim" in level and unit == unit_name_norm)
        )

        return (0 if is_main else 1, row.get("_excel_order", 999999))

    rows["_sort"] = rows.apply(sort_key, axis=1)
    rows = rows.sort_values("_sort").drop(columns=["_sort"])

    return rows


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
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
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# BAŞLIK
# =========================================================

st.markdown(
    """
<div class="title-box">
    <div class="title-red">T.C. Çalışma ve Sosyal Güvenlik Bakanlığı</div>
    <div style="font-size:22px;">Yetkinlik Haritası Çalışması</div>
</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# ORGANİZASYON ŞEMASI
# =========================================================

if not ordered_groups:
    st.warning("Excel içinde gösterilecek ana birim grubu bulunamadı.")
    st.stop()

cols = st.columns(len(ordered_groups))

for idx, group_code in enumerate(ordered_groups):
    group_units = main_units_df[main_units_df["_group"] == group_code].copy()

    with cols[idx]:
        st.markdown(
            f"<div class='org-red'>{group_title(group_code)}</div>",
            unsafe_allow_html=True
        )

        for _, unit_row in group_units.iterrows():
            unit_name = clean_value(unit_row[position_col])
            unit_uid = normalize_uid(unit_row[uid_col])

            if st.button(
                unit_name,
                key=f"unit_btn_{group_code}_{unit_uid}",
                use_container_width=True
            ):
                st.session_state["selected_unit_name"] = unit_name
                st.session_state["selected_unit_uid"] = unit_uid

                for key in list(st.session_state.keys()):
                    if str(key).startswith("toggle_"):
                        del st.session_state[key]


# =========================================================
# SEÇİLEN BİRİM DETAYI
# =========================================================

if "selected_unit_name" in st.session_state and "selected_unit_uid" in st.session_state:
    selected_unit_name = st.session_state["selected_unit_name"]
    selected_unit_uid = st.session_state["selected_unit_uid"]

    st.divider()
    st.subheader(selected_unit_name)

    unit_df = get_rows_for_unit(selected_unit_uid, selected_unit_name)

    if unit_df.empty:
        st.warning("Bu birim Excel içinde bulunamadı.")

    else:
        for _, row in unit_df.iterrows():
            position_name = clean_value(row.get(position_col, ""))
            uid = normalize_uid(row.get(uid_col, ""))

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
                competencies = get_competencies_for_uid(uid)

                if not competencies:
                    st.info("Bu UID için Yetkinlik Matrisi sayfasında yetkinlik bulunamadı.")

                else:
                    for comp in competencies:
                        comp_name = clean_value(comp.get("name", ""))
                        comp_code = clean_value(comp.get("code", ""))

                        if not comp_name and not comp_code:
                            continue

                        st.markdown(
                            f"""
                            <div class="competency-card">
                                <b>{comp_name}</b>
                                <div class="uid-card">{comp_code}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )


# =========================================================
# VERİ KAYNAĞI BİLGİSİ
# =========================================================

st.divider()

with st.expander("Veri kaynağı bilgisi", expanded=False):
    st.write("Okunan Excel:", EXCEL_FILE.name)
    st.write("Organizasyon Sayfası:", org_sheet)
    st.write("Yetkinlik Sayfası:", comp_sheet)
    st.write("Master Sayfası:", master_sheet)
    st.write("Organizasyon UID Sayısı:", len(org_df))
    st.write("Yetkinlik UID Sayısı:", len(competency_map))
    st.write("Yetkinlik Matrisi UID kolonu:", comp_uid_col)
    st.write("Okunan Yetkinlik Ad/Kod Kolonları:", [(str(a), str(b)) for a, b in comp_cols])
