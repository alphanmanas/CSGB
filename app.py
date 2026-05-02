import streamlit as st
import pandas as pd
from pathlib import Path
import re
from collections import Counter
from io import BytesIO

st.set_page_config(
    page_title="ÇSGB Yetkinlik Haritası",
    layout="wide"
)

# =========================================================
# SABİT AYARLAR
# =========================================================

BASE_DIR = Path(__file__).parent
DEFAULT_EXCEL_PATH = BASE_DIR / "data" / "csgb_yetkinlik.xlsx"

TARGET_ORG_SHEET = "ÇSGB Kodlama"
TARGET_COMPETENCY_SHEET = "Yetkinlik Matrisi"
TARGET_MASTER_SHEET = "Master Yetkinlik Listesi"

REPEATED_SET_WARNING_LIMIT = 6


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
    return bool(re.match(r"^[A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,10}-\d{2}$", text))


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

    files = []

    files.extend(list(BASE_DIR.glob("*.xlsx")))

    data_dir = BASE_DIR / "data"
    if data_dir.exists():
        files.extend(list(data_dir.glob("*.xlsx")))

    if not files:
        return None

    return files[0]


# =========================================================
# EXCEL OKUMA
# =========================================================

EXCEL_FILE = find_excel_file()

if EXCEL_FILE is None:
    st.error("Excel dosyası bulunamadı. Dosyayı data/csgb_yetkinlik.xlsx olarak koy.")
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
                    score += 30
                if "ana birim" in cols:
                    score += 20
                if "pozisyon" in cols:
                    score += 20
                if "yetkinlik" in cols:
                    score += 20
                if "ÇSGB-" in sample or "CSGB-" in sample or "ÇSGK-" in sample or "CSGK-" in sample:
                    score += 30

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


def get_sheet_exact(sheets_dict, target_name):
    for sheet_name, payload in sheets_dict.items():
        if normalize_text(sheet_name) == normalize_text(target_name):
            return sheet_name, payload["df"], payload["header"]

    st.error(f"Excel içinde '{target_name}' sayfası bulunamadı.")
    st.write("Bulunan sayfalar:", list(sheets_dict.keys()))
    st.stop()


org_sheet, org_raw_df, org_header = get_sheet_exact(sheets, TARGET_ORG_SHEET)
comp_sheet, comp_raw_df, comp_header = get_sheet_exact(sheets, TARGET_COMPETENCY_SHEET)
master_sheet, master_raw_df, master_header = get_sheet_exact(sheets, TARGET_MASTER_SHEET)


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

org_duplicate_uids = org_df[org_df.duplicated(subset=[uid_col], keep=False)].copy()

org_df = org_df.drop_duplicates(subset=[uid_col], keep="first").reset_index(drop=True)


# =========================================================
# MASTER YETKİNLİK LİSTESİ
# SADECE KOD -> AD İÇİN
# =========================================================

def build_master_lookup(master_df):
    lookup = {}

    code_col = find_col(
        master_df,
        ["Yetkinlik Kodu", "Kod", "Kodu"],
        forbidden=["uid", "pozisyon", "birim"],
    )

    name_col = find_col(
        master_df,
        ["Yetkinlik Adı", "Yetkinlik Adi", "Yetkinlik"],
        forbidden=["kodu", "kod", "uid"],
    )

    if code_col is None or name_col is None:
        st.warning("Master Yetkinlik Listesi içinde Yetkinlik Kodu / Yetkinlik Adı kolonları bulunamadı.")
        return lookup

    for _, row in master_df.iterrows():
        code = clean_value(row.get(code_col, "")).upper()
        name = clean_value(row.get(name_col, ""))

        if is_competency_code(code) and name:
            lookup[code] = name

    return lookup


master_lookup = build_master_lookup(master_raw_df)


# =========================================================
# YETKİNLİK MATRİSİ OKUMA
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
        r"^([A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,10}-\d{2})\s*[-–—]\s*(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if m:
        return m.group(2).strip(), m.group(1).strip().upper()

    m2 = re.match(
        r"^([A-ZÇĞİÖŞÜ]{2,6}-[A-ZÇĞİÖŞÜ0-9]{2,10}-\d{2})$",
        text,
        flags=re.IGNORECASE,
    )

    if m2:
        return "", m2.group(1).strip().upper()

    return text, ""


comp_uid_col = find_uid_col_for_comp_sheet(comp_raw_df)
comp_cols = find_competency_columns(comp_raw_df)

if comp_uid_col is None:
    st.error("Yetkinlik Matrisi sayfasında UID kolonu bulunamadı.")
    st.write("Kolonlar:", list(comp_raw_df.columns))
    st.stop()

if not comp_cols:
    st.error("Yetkinlik Matrisi sayfasında Yetkinlik 1-10 kolonları bulunamadı.")
    st.write("Kolonlar:", list(comp_raw_df.columns))
    st.stop()


def build_competency_map(df):
    comp_map = {}
    raw_rows = []

    temp = df.copy()
    temp[comp_uid_col] = temp[comp_uid_col].apply(clean_value)
    temp = temp[temp[comp_uid_col].apply(is_position_uid)].copy()

    duplicate_comp_uids_df = temp[temp.duplicated(subset=[comp_uid_col], keep=False)].copy()

    for _, row in temp.iterrows():
        uid = clean_value(row.get(comp_uid_col, ""))

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

            competencies.append(
                {
                    "code": comp_code,
                    "name": comp_name,
                }
            )

        raw_rows.append(
            {
                "UID": uid,
                "Yetkinlik Sayısı": len(competencies),
                "Yetkinlik Seti": " | ".join([c["code"] for c in competencies]),
            }
        )

        if uid not in comp_map:
            comp_map[uid] = competencies

    summary_df = pd.DataFrame(raw_rows)

    return comp_map, summary_df, duplicate_comp_uids_df


competency_map, comp_summary_df, comp_duplicate_uids_df = build_competency_map(comp_raw_df)


# =========================================================
# TEKRAR EDEN SET KONTROLÜ
# =========================================================

def comp_signature(comps):
    codes = sorted([
        clean_value(c.get("code", "")).upper()
        for c in comps
        if clean_value(c.get("code", ""))
    ])
    return tuple(codes)


signature_counter = Counter()

for uid, comps in competency_map.items():
    sig = comp_signature(comps)
    if sig:
        signature_counter[sig] += 1


def is_repeated_set_uid(uid):
    uid = clean_value(uid)
    comps = competency_map.get(uid, [])

    if not comps:
        return False

    sig = comp_signature(comps)

    if not sig:
        return False

    return signature_counter.get(sig, 0) >= REPEATED_SET_WARNING_LIMIT


def get_repeated_set_info(uid):
    uid = clean_value(uid)
    comps = competency_map.get(uid, [])

    if not comps:
        return {
            "is_repeated": False,
            "message": "Bu UID için Yetkinlik Matrisi içinde yetkinlik bulunamadı.",
            "affected_df": pd.DataFrame(),
        }

    sig = comp_signature(comps)
    repeat_count = signature_counter.get(sig, 0)

    if repeat_count < REPEATED_SET_WARNING_LIMIT:
        return {
            "is_repeated": False,
            "message": "",
            "affected_df": pd.DataFrame(),
        }

    affected_rows = []

    for other_uid, other_comps in competency_map.items():
        if comp_signature(other_comps) == sig:
            org_match = org_df[org_df[uid_col] == other_uid]

            unit_name = ""
            position_name = ""

            if not org_match.empty:
                unit_name = clean_value(org_match.iloc[0].get(unit_col, ""))
                position_name = clean_value(org_match.iloc[0].get(position_col, ""))

            affected_rows.append(
                {
                    "UID": other_uid,
                    "Ana Birim / Kurum": unit_name,
                    "Pozisyon / Birim Adı": position_name,
                    "Yetkinlik Seti": " | ".join(sig),
                }
            )

    affected_df = pd.DataFrame(affected_rows)

    return {
        "is_repeated": True,
        "message": (
            f"Bu UID’nin yetkinlik seti {repeat_count} farklı UID’de birebir aynı görünüyor. "
            f"Yetkinlikler Excel’deki UID satırından aynen gösterilmektedir."
        ),
        "affected_df": affected_df,
    }


def get_competencies_for_uid(uid):
    uid = clean_value(uid)
    return competency_map.get(uid, [])


# =========================================================
# KALİTE KONTROL RAPORLARI
# =========================================================

def build_quality_reports():
    org_uids = set(org_df[uid_col].dropna().astype(str))
    comp_uids = set(competency_map.keys())

    org_without_comp = org_df[~org_df[uid_col].isin(comp_uids)][
        [uid_col, unit_col, position_col]
    ].copy()
    org_without_comp.columns = ["UID", "Ana Birim / Kurum", "Pozisyon / Birim Adı"]

    comp_without_org = pd.DataFrame({
        "UID": sorted(list(comp_uids - org_uids))
    })

    repeated_rows = []

    for sig, count in signature_counter.items():
        if count >= REPEATED_SET_WARNING_LIMIT:
            for uid, comps in competency_map.items():
                if comp_signature(comps) == sig:
                    org_match = org_df[org_df[uid_col] == uid]

                    unit_name = ""
                    position_name = ""

                    if not org_match.empty:
                        unit_name = clean_value(org_match.iloc[0].get(unit_col, ""))
                        position_name = clean_value(org_match.iloc[0].get(position_col, ""))

                    repeated_rows.append(
                        {
                            "UID": uid,
                            "Ana Birim / Kurum": unit_name,
                            "Pozisyon / Birim Adı": position_name,
                            "Tekrar Sayısı": count,
                            "Yetkinlik Seti": " | ".join(sig),
                            "Durum": "Tekrar eden set - sadece uyarı",
                        }
                    )

    repeated_sets = pd.DataFrame(repeated_rows)

    competency_counts = []

    for uid in sorted(org_uids):
        comps = competency_map.get(uid, [])
        org_match = org_df[org_df[uid_col] == uid]

        unit_name = ""
        position_name = ""

        if not org_match.empty:
            unit_name = clean_value(org_match.iloc[0].get(unit_col, ""))
            position_name = clean_value(org_match.iloc[0].get(position_col, ""))

        competency_counts.append(
            {
                "UID": uid,
                "Ana Birim / Kurum": unit_name,
                "Pozisyon / Birim Adı": position_name,
                "Yetkinlik Sayısı": len(comps),
                "Tekrar Eden Set mi": "Evet" if is_repeated_set_uid(uid) else "Hayır",
            }
        )

    competency_counts_df = pd.DataFrame(competency_counts)

    master_missing_rows = []

    for uid, comps in competency_map.items():
        org_match = org_df[org_df[uid_col] == uid]
        position_name = ""

        if not org_match.empty:
            position_name = clean_value(org_match.iloc[0].get(position_col, ""))

        for comp in comps:
            code = clean_value(comp.get("code", "")).upper()
            name = clean_value(comp.get("name", ""))

            if code and code not in master_lookup:
                master_missing_rows.append(
                    {
                        "UID": uid,
                        "Pozisyon / Birim Adı": position_name,
                        "Yetkinlik Kodu": code,
                        "Yetkinlik Adı": name,
                        "Sorun": "Kod Master Yetkinlik Listesi içinde bulunamadı",
                    }
                )

    master_missing = pd.DataFrame(master_missing_rows)

    duplicate_org = pd.DataFrame()
    if not org_duplicate_uids.empty:
        duplicate_org = org_duplicate_uids[[uid_col, unit_col, position_col]].copy()
        duplicate_org.columns = ["UID", "Ana Birim / Kurum", "Pozisyon / Birim Adı"]

    duplicate_comp = pd.DataFrame()
    if not comp_duplicate_uids_df.empty:
        duplicate_comp = comp_duplicate_uids_df[[comp_uid_col]].copy()
        duplicate_comp.columns = ["UID"]

    return {
        "Organizasyonda Var Yetkinlikte Yok": org_without_comp,
        "Yetkinlikte Var Organizasyonda Yok": comp_without_org,
        "Tekrar Eden Yetkinlik Setleri": repeated_sets,
        "UID Yetkinlik Sayıları": competency_counts_df,
        "Master Listede Olmayan Kodlar": master_missing,
        "Organizasyonda Tekrarlı UID": duplicate_org,
        "Yetkinlik Matrisinde Tekrarlı UID": duplicate_comp,
    }


quality_reports = build_quality_reports()


def quality_reports_to_excel(reports):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in reports.items():
            safe_name = sheet_name[:31]
            if df is None or df.empty:
                pd.DataFrame({"Sonuç": ["Kayıt yok"]}).to_excel(
                    writer,
                    sheet_name=safe_name,
                    index=False,
                )
            else:
                df.to_excel(
                    writer,
                    sheet_name=safe_name,
                    index=False,
                )

    output.seek(0)
    return output


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
                repeat_info = get_repeated_set_info(uid)

                if repeat_info["message"]:
                    if repeat_info["is_repeated"]:
                        st.warning(repeat_info["message"])

                        if not repeat_info["affected_df"].empty:
                            with st.expander("Aynı yetkinlik setinin geçtiği UID’leri göster", expanded=False):
                                st.dataframe(
                                    repeat_info["affected_df"],
                                    use_container_width=True
                                )
                    else:
                        st.info(repeat_info["message"])

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


# =========================================================
# KALİTE KONTROL RAPORU
# =========================================================

st.divider()

with st.expander("Yetkinlik Kalite Kontrol Raporu", expanded=False):
    st.write("Bu bölüm sadece Excel verisini kontrol eder. Yetkinlik tahmini yapılmaz.")

    st.write("Okunan Excel:", EXCEL_FILE.name)
    st.write("Organizasyon Sayfası:", org_sheet)
    st.write("Yetkinlik Sayfası:", comp_sheet)
    st.write("Master Sayfası:", master_sheet)
    st.write("Organizasyon UID Sayısı:", len(org_df))
    st.write("Yetkinlik UID Sayısı:", len(competency_map))
    st.write("Tekrar eden set uyarı eşiği:", REPEATED_SET_WARNING_LIMIT)

    for report_name, report_df in quality_reports.items():
        st.markdown(f"### {report_name}")

        if report_df is None or report_df.empty:
            st.success("Kayıt yok.")
        else:
            st.dataframe(report_df, use_container_width=True)

    report_file = quality_reports_to_excel(quality_reports)

    st.download_button(
        label="Kalite Kontrol Raporunu Excel İndir",
        data=report_file,
        file_name="yetkinlik_kalite_kontrol_raporu.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
