import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="ÇSGB Yetkinlik Haritası", layout="wide")

BASE_DIR = Path(__file__).parent


# =========================================================
# TEMEL FONKSİYONLAR
# =========================================================

def normalize_text(x):
    if pd.isna(x):
        return ""
    x = str(x).strip().lower()
    tr_map = str.maketrans("çğıöşüİI", "cgiosuii")
    x = x.translate(tr_map)
    x = re.sub(r"\s+", " ", x)
    return x


def clean_value(x):
    if pd.isna(x):
        return ""
    text = str(x).strip()
    if text.lower() in ["nan", "none", "null"]:
        return ""
    return text


def is_position_uid(value):
    text = clean_value(value).upper()
    return bool(re.match(r"^(ÇSGB|CSGB|ÇSGK|CSGK)-", text))


def is_competency_code(value):
    text = clean_value(value).upper()
    return bool(re.match(r"^[A-ZÇĞİÖŞÜ]{2,5}-[A-ZÇĞİÖŞÜ0-9]{2,8}-\d{2}$", text))


def find_excel_file():
    files = list(BASE_DIR.glob("*.xlsx"))

    if not files:
        return None

    priority_words = [
        "çalışma",
        "csgb",
        "çsgb",
        "kodlama",
        "yetkinlik",
        "matrisi",
    ]

    for file in files:
        filename = normalize_text(file.name)
        if any(normalize_text(w) in filename for w in priority_words):
            return file

    return files[0]


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


# =========================================================
# EXCEL OKUMA
# =========================================================

EXCEL_FILE = find_excel_file()

if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı. Excel dosyasını app.py ile aynı klasöre koy.")
    st.stop()


@st.cache_data(show_spinner=False)
def read_all_sheets(path):
    xls = pd.ExcelFile(path, engine="openpyxl")
    sheets = {}

    for sheet in xls.sheet_names:
        best_df = None
        best_header = None
        best_score = -999

        for header_row in range(0, 15):
            try:
                temp = pd.read_excel(
                    path,
                    sheet_name=sheet,
                    header=header_row,
                    engine="openpyxl",
                )

                temp.columns = [str(c).strip() for c in temp.columns]
                temp = temp.dropna(how="all")

                if temp.empty:
                    continue

                cols = " ".join(normalize_text(c) for c in temp.columns)
                sample = " ".join(
                    temp.astype(str)
                    .head(100)
                    .fillna("")
                    .values
                    .flatten()
                    .tolist()
                )

                score = 0

                if "uid" in cols:
                    score += 20
                if "ana birim" in cols:
                    score += 20
                if "pozisyon" in cols:
                    score += 20
                if "yetkinlik" in cols:
                    score += 15
                if "ÇSGB-" in sample or "CSGB-" in sample or "ÇSGK-" in sample:
                    score += 20

                if score > best_score:
                    best_score = score
                    best_df = temp
                    best_header = header_row

            except Exception:
                pass

        if best_df is not None:
            sheets[sheet] = {
                "df": best_df,
                "header": best_header,
            }

    return sheets


sheets = read_all_sheets(EXCEL_FILE)

if not sheets:
    st.error("Excel okunamadı.")
    st.stop()


# =========================================================
# ÇSGB KODLAMA SAYFASI
# =========================================================

def looks_like_org_sheet(df):
    cols = " ".join(normalize_text(c) for c in df.columns)

    has_uid = "uid" in cols
    has_unit = "ana birim" in cols or "kurum" in cols
    has_position = "pozisyon" in cols or "birim adi" in cols

    has_real_uid = False

    for col in df.columns:
        sample = df[col].dropna().astype(str).head(300).tolist()
        if any(is_position_uid(v) for v in sample):
            has_real_uid = True
            break

    return has_uid and has_unit and has_position and has_real_uid


def select_org_sheet(sheets_dict):
    preferred_names = [
        "ÇSGB Kodlama",
        "CSGB Kodlama",
        "Kodlama",
        "ÇSGB_Kodlama",
        "CSGB_Kodlama",
    ]

    for preferred in preferred_names:
        for sheet_name, payload in sheets_dict.items():
            if normalize_text(sheet_name) == normalize_text(preferred):
                df = payload["df"]
                if looks_like_org_sheet(df):
                    return sheet_name, df, payload["header"]

    best_sheet = None
    best_df = None
    best_header = None
    best_score = -999

    for sheet_name, payload in sheets_dict.items():
        df = payload["df"]
        sheet_norm = normalize_text(sheet_name)
        cols = " ".join(normalize_text(c) for c in df.columns)

        if "master" in sheet_norm:
            continue

        score = 0

        if looks_like_org_sheet(df):
            score += 100
        if "kodlama" in sheet_norm:
            score += 40
        if "uid" in cols:
            score += 20
        if "ana birim" in cols:
            score += 20
        if "pozisyon" in cols:
            score += 20
        if "yetkinlik kodu" in cols and "ana birim" not in cols:
            score -= 100

        if score > best_score:
            best_score = score
            best_sheet = sheet_name
            best_df = df
            best_header = payload["header"]

    return best_sheet, best_df, best_header


org_sheet, org_raw_df, org_header = select_org_sheet(sheets)

if org_raw_df is None or org_raw_df.empty:
    st.error("ÇSGB Kodlama / organizasyon sayfası bulunamadı.")
    st.stop()


# =========================================================
# ORGANİZASYON KOLONLARI
# =========================================================

uid_col = find_col(org_raw_df, ["UID"], exact=True)

baglilik_col = find_col(
    org_raw_df,
    ["Bağlılık Kodu", "Baglilik Kodu"],
)

unit_col = find_col(
    org_raw_df,
    ["Ana Birim / Kurum", "Ana Birim", "Kurum"],
)

level_col = find_col(
    org_raw_df,
    ["Seviye"],
    exact=True,
)

position_type_col = find_col(
    org_raw_df,
    ["Pozisyon Türü", "Pozisyon Turu"],
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
        "Birim Adi",
    ],
)

main_code_col = find_col(
    org_raw_df,
    ["Ana Birim Kodu"],
)

if uid_col is None or unit_col is None or position_col is None:
    st.error("ÇSGB Kodlama sayfasında UID, Ana Birim / Kurum veya Pozisyon / Birim Adı kolonu bulunamadı.")
    st.write("Okunan organizasyon sheet:", org_sheet)
    st.write("Kolonlar:", list(org_raw_df.columns))
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
    main_code_col,
]:
    if col and col in org_df.columns:
        org_df[col] = org_df[col].apply(clean_value)

org_df = org_df[org_df[uid_col].apply(is_position_uid)].copy()

org_df = org_df[
    (org_df[uid_col] != "")
    & (org_df[unit_col] != "")
    & (org_df[position_col] != "")
].copy()

org_df = org_df.drop_duplicates(subset=[uid_col]).reset_index(drop=True)


# =========================================================
# MASTER YETKİNLİK KOD -> AD LOOKUP
# =========================================================

def build_master_competency_lookup(sheets_dict):
    lookup = {}

    for sheet_name, payload in sheets_dict.items():
        df = payload["df"]
        sheet_norm = normalize_text(sheet_name)
        cols_norm = " ".join(normalize_text(c) for c in df.columns)

        is_master = "master" in sheet_norm
        has_master_cols = "yetkinlik kodu" in cols_norm and (
            "yetkinlik adi" in cols_norm or "yetkinlik adı" in cols_norm
        )

        if not is_master and not has_master_cols:
            continue

        code_col = find_col(
            df,
            ["Yetkinlik Kodu", "Kod", "Kodu"],
            forbidden=["uid", "pozisyon", "birim"],
        )

        name_col = find_col(
            df,
            ["Yetkinlik Adı", "Yetkinlik Adi", "Yetkinlik"],
            forbidden=["kodu", "kod", "uid"],
        )

        if code_col is None or name_col is None:
            continue

        for _, row in df.iterrows():
            code = clean_value(row.get(code_col, "")).upper()
            name = clean_value(row.get(name_col, ""))

            if is_competency_code(code) and name:
                lookup[code] = name

    return lookup


master_lookup = build_master_competency_lookup(sheets)


# =========================================================
# YETKİNLİK MATRİSİ
# =========================================================

def find_uid_col_for_comp_sheet(df):
    col = find_col(
        df,
        ["UID", "Pozisyon UID", "Birim UID", "Pozisyon Kodu", "Birim Kodu"],
        exact=True,
    )

    if col:
        return col

    for c in df.columns:
        sample = df[c].dropna().astype(str).head(300).tolist()
        if any(is_position_uid(v) for v in sample):
            return c

    return None


def find_competency_columns(df):
    result = []
    col_map = {normalize_text(c): c for c in df.columns}

    for i in range(1, 11):
        name_col = None
        code_col = None

        name_candidates = {
            f"yetkinlik {i} adi",
            f"yetkinlik {i} ad",
            f"yetkinlik {i} adı",
            f"yetkinlik{i} adi",
            f"yetkinlik{i} ad",
            f"yetkinlik{i} adı",
        }

        code_candidates = {
            f"yetkinlik {i} kodu",
            f"yetkinlik {i} kod",
            f"yetkinlik{i} kodu",
            f"yetkinlik{i} kod",
        }

        single_candidates = {
            f"yetkinlik {i}",
            f"yetkinlik{i}",
        }

        for norm_col, original_col in col_map.items():
            if norm_col in code_candidates:
                code_col = original_col
                break

        for norm_col, original_col in col_map.items():
            if norm_col in name_candidates:
                name_col = original_col
                break

        if name_col is None:
            for norm_col, original_col in col_map.items():
                if norm_col in single_candidates:
                    name_col = original_col
                    break

        if name_col or code_col:
            result.append((name_col, code_col))

    return result


def split_competency_value(value):
    text = clean_value(value)

    if not text:
        return "", ""

    m = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,5}-[A-ZÇĞİÖŞÜ0-9]{2,8}-\d{2})\s*[-–—]\s*(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if m:
        return m.group(2).strip(), m.group(1).strip().upper()

    m2 = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,5}-[A-ZÇĞİÖŞÜ0-9]{2,8}-\d{2})$",
        text,
        flags=re.IGNORECASE,
    )

    if m2:
        return "", m2.group(1).strip().upper()

    return text, ""


def is_valid_competency_matrix(sheet_name, df):
    sheet_norm = normalize_text(sheet_name)
    cols = " ".join(normalize_text(c) for c in df.columns)

    if "master" in sheet_norm:
        return False

    if "kodlama" in sheet_norm:
        return False

    if "yetkinlik" not in cols:
        return False

    uid_candidate = find_uid_col_for_comp_sheet(df)

    if uid_candidate is None:
        return False

    comp_cols = find_competency_columns(df)

    if not comp_cols:
        return False

    sample = df[uid_candidate].dropna().astype(str).head(300).tolist()

    if not any(is_position_uid(v) for v in sample):
        return False

    return True


def choose_primary_competency_sheet(sheets_dict):
    preferred_order = [
        "Yetkinlik Matrisi v03",
        "Yetkinlik Matrisi",
        "Yetkinlik Matrisi v02",
        "ÇSGB Yetkinlik Matrisi",
        "CSGB Yetkinlik Matrisi",
    ]

    for preferred in preferred_order:
        for sheet_name, payload in sheets_dict.items():
            if normalize_text(sheet_name) == normalize_text(preferred):
                df = payload["df"]
                if is_valid_competency_matrix(sheet_name, df):
                    return sheet_name, df

    candidates = []

    for sheet_name, payload in sheets_dict.items():
        df = payload["df"]

        if not is_valid_competency_matrix(sheet_name, df):
            continue

        cols = " ".join(normalize_text(c) for c in df.columns)
        sheet_norm = normalize_text(sheet_name)

        score = 0

        if "yetkinlik matrisi" in sheet_norm:
            score += 50
        if "yetkinlik 1 kodu" in cols:
            score += 30
        if "yetkinlik 1 adi" in cols or "yetkinlik 1 adı" in cols:
            score += 30
        if "agirlik" in cols or "ağırlık" in cols:
            score += 10

        candidates.append((score, sheet_name, df))

    if not candidates:
        return None, None

    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1], candidates[0][2]


def build_competency_map_from_excel(sheets_dict):
    comp_map = {}

    selected_sheet, df = choose_primary_competency_sheet(sheets_dict)

    if df is None:
        return comp_map, None

    uid_candidate = find_uid_col_for_comp_sheet(df)
    comp_cols = find_competency_columns(df)

    if uid_candidate is None or not comp_cols:
        return comp_map, selected_sheet

    temp = df.copy()
    temp[uid_candidate] = temp[uid_candidate].apply(clean_value)

    temp = temp[temp[uid_candidate].apply(is_position_uid)].copy()
    temp = temp.drop_duplicates(subset=[uid_candidate], keep="first")

    for _, row in temp.iterrows():
        uid = clean_value(row.get(uid_candidate, ""))

        if not uid:
            continue

        comp_map[uid] = []
        seen = set()

        for name_col, code_col in comp_cols:
            raw_name = row.get(name_col, "") if name_col else ""
            raw_code = row.get(code_col, "") if code_col else ""

            comp_name = clean_value(raw_name)
            comp_code = clean_value(raw_code).upper()

            if comp_name:
                parsed_name, parsed_code = split_competency_value(comp_name)

                if parsed_code:
                    comp_name = parsed_name
                    comp_code = parsed_code

            if comp_code:
                parsed_name, parsed_code = split_competency_value(comp_code)

                if parsed_code:
                    comp_code = parsed_code

                    if parsed_name and not comp_name:
                        comp_name = parsed_name

            if comp_code and not comp_name:
                comp_name = master_lookup.get(comp_code, "")

            if not comp_code and not comp_name:
                continue

            if is_position_uid(comp_name) or is_position_uid(comp_code):
                continue

            key = (comp_code, comp_name)

            if key in seen:
                continue

            seen.add(key)

            comp_map[uid].append(
                {
                    "code": comp_code,
                    "name": comp_name,
                }
            )

    return comp_map, selected_sheet


competency_map, selected_competency_sheet = build_competency_map_from_excel(sheets)


def get_competencies_for_uid(uid):
    uid = clean_value(uid)

    # Kritik: sadece birebir UID eşleşmesi.
    # Prefix, benzer UID, ana birim mirası, fallback yok.
    return competency_map.get(uid, [])


# =========================================================
# ORGANİZASYON GRUPLARI
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
    uid = clean_value(row.get(uid_col, "")).upper()
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

    uid = clean_value(row.get(uid_col, ""))
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


# =========================================================
# BİRİM DETAYLARI
# =========================================================

def get_rows_for_unit(unit_uid, unit_name):
    unit_uid = clean_value(unit_uid)
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
        uid = clean_value(row.get(uid_col, "")).upper()
        pos = normalize_text(row.get(position_col, ""))
        unit = normalize_text(row.get(unit_col, ""))
        level = normalize_text(row.get(level_col, "")) if level_col else ""

        is_main = (
            uid == unit_uid.upper()
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
            unsafe_allow_html=True,
        )

        for _, unit_row in group_units.iterrows():
            unit_name = clean_value(unit_row[position_col])
            unit_uid = clean_value(unit_row[uid_col])

            if st.button(
                unit_name,
                key=f"unit_btn_{group_code}_{unit_uid}",
                use_container_width=True,
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
            uid = clean_value(row.get(uid_col, ""))

            st.markdown(
                f"""
                <div class="detail-card">
                    <b>{position_name}</b>
                    <div class="uid-card">{uid}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            toggle_key = f"toggle_{uid}"

            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False

            if st.button(
                "Yetkinlikleri Göster",
                key=f"btn_{uid}",
                use_container_width=True,
            ):
                st.session_state[toggle_key] = not st.session_state[toggle_key]

            if st.session_state[toggle_key]:
                competencies = get_competencies_for_uid(uid)

                if not competencies:
                    st.info("Bu UID için Excel’de yetkinlik bulunamadı.")

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
                            unsafe_allow_html=True,
                        )
