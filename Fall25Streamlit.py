import streamlit as st
import pandas as pd
import json
import requests
from pathlib import Path

# ------------------ Paths / Constants ------------------
BASE_DIR = Path(__file__).resolve().parent
AA_FILE      = BASE_DIR / "AAF25.csv"
DB_FILE      = BASE_DIR / "DearbornF25.csv"
FLINT_FILE   = BASE_DIR / "FlintF25.csv"
MONTHLY_FILE = BASE_DIR / "MonthlySept25.csv"
AUG_DUES_FILE = BASE_DIR / "AugDues.csv"
AUG_DUES_G_FILE = BASE_DIR / "AugDuesG.csv"
LEO_PREFIX   = "leo"  # case-insensitive prefix for lecturers

# ------------------ Helpers ------------------
@st.cache_data
def load_buildings():
    url = "https://raw.githubusercontent.com/umsi-amadaman/LEOcourseschedules/main/UMICHbuildings_dict.json"
    return requests.get(url).json()

@st.cache_data
def load_monthly():
    return pd.read_csv(MONTHLY_FILE, dtype=str)

@st.cache_data
def load_dues():
    """Load both dues files and combine them."""
    try:
        aug_dues = pd.read_csv(AUG_DUES_FILE, dtype=str)
        aug_dues_g = pd.read_csv(AUG_DUES_G_FILE, dtype=str)
        # Combine both dues files
        all_dues = pd.concat([aug_dues, aug_dues_g], ignore_index=True)
        return all_dues
    except FileNotFoundError as e:
        st.warning(f"Dues file not found: {e}")
        return pd.DataFrame()

def merge_monthly_and_dues(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    """Merge schedule with Monthly and add dues status based on AugDues files."""
    monthly = load_monthly()
    dues_df = load_dues()
    
    # numeric-safe IDs for robust merge
    df[id_col] = pd.to_numeric(df[id_col], errors="coerce")
    monthly["UM ID"] = pd.to_numeric(monthly["UM ID"], errors="coerce")
    
    # Merge with monthly data
    merged = df.merge(monthly, left_on=id_col, right_on="UM ID", how="left")

    # Keep lecturers (case-insensitive) and non-blank titles
    mask = merged["Job Title"].fillna("").str.lower().str.startswith(LEO_PREFIX)
    merged = merged[mask & merged["Job Title"].str.strip().ne("")]
    
    # Add dues status if dues data is available
    if not dues_df.empty and "UM ID" in dues_df.columns:
        dues_df["UM ID"] = pd.to_numeric(dues_df["UM ID"], errors="coerce")
        merged["Dues Status"] = merged["UM ID"].isin(dues_df["UM ID"]).map({True: "Paid", False: "Not Paid"})
    else:
        merged["Dues Status"] = "Unknown"
    
    return merged

# ------------------ Ann Arbor ------------------

def show_ann_arbor():
    st.header("Ann Arbor Schedule by Day and Subject")
    raw = pd.read_csv(AA_FILE, dtype=str)
    merged = merge_monthly_and_dues(raw, "Class Instr ID")

    # Drop columns similar to summer version
    aa_drop = [
        "Class Instr ID", "Facility ID", 
        "Employee Last Name", "Employee First Name",
        "UM ID", "Rec #", "Class Indc", "Job Code", "Hire Begin Date", "Appointment Start Date",
        "Appointment End Date", "Comp Frequency", "Appointment Period", "Appointment Period Descr",
        "Comp Rate", "Home Address 1", "Home Address 2", "Home Address 3", "Home City", "Home State",
        "Home Postal", "Home County", "Home Country", "Home Phone", "UM Address 1", "UM Address 2",
        "UM Address 3", "UM City", "UM State", "UM Postal", "UM County", "UM Country", "UM Phone",
        "Employee Status", "Employeee Status Descr", "uniqname", "Class Mtg Nbr",
        "Term", "Class Nbr", "Department ID", "Employee Status Descr"
    ]
    merged.drop(columns=[c for c in aa_drop if c in merged.columns], inplace=True)

    # Day / Subject filters
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_map = {"Monday": "Mon", "Tuesday": "Tues", "Wednesday": "Wed", "Thursday": "Thurs", "Friday": "Fri"}
    sel_day = st.selectbox("Select Day", days, key="aa_day")
    day_df = merged[merged[day_map[sel_day]].eq("Y")]

    subj_opts = sorted(day_df["Subject"].dropna().unique())
    sel_subj = st.selectbox("Select Subject", ["All"] + subj_opts, key="aa_subj")
    if sel_subj != "All":
        day_df = day_df[day_df["Subject"] == sel_subj]

    st.dataframe(day_df)
    st.write(f"Total classes: {len(day_df)}")

# ------------------ Dearborn ------------------

def show_dearborn():
    st.header("Dearborn Schedule by Day and Subject")

    raw = pd.read_csv(DB_FILE, dtype=str).dropna(axis=1, how="all")
    raw.columns = [c.strip() for c in raw.columns]

    # Rename columns to match summer version structure
    rename_map = {
        "Subject Code": "Subject",
        "SEQ Number": "Seq Number",
        "Primary Instructor ID": "Instructor ID",
        "Primary Instructor Last Name": "Last",
        "Primary Instructor First Name": "First",
        "Room Code": "Room",
        "Building Code": "Bldg",
        "Monday Indicator": "Monday",
        "Tuesday Indicator": "Tuesday",
        "Wednesday Indicator": "Wednesday",
        "Thursday Indicator": "Thursday",
        "Friday Indicator": "Friday",
        "Saturday Indicator": "Saturday",
        "Sunday Indicator": "Sunday",
    }
    raw.rename(columns=rename_map, inplace=True)

    merged = merge_monthly_and_dues(raw, "Instructor ID")

    # Drop columns
    db_drop = [
        "Class Instr ID", "Facility ID", "Facility Descr", "Employee Last Name", "Employee First Name",
        "UM ID", "Rec #", "Class Indc", "Job Code", "Hire Begin Date", "Appointment Start Date",
        "Appointment End Date", "Comp Frequency", "Appointment Period", "Appointment Period Descr",
        "Comp Rate", "Home Address 1", "Home Address 2", "Home Address 3", "Home City", "Home State",
        "Home Postal", "Home County", "Home Country", "Home Phone", "UM Address 1", "UM Address 2",
        "UM Address 3", "UM City", "UM State", "UM Postal", "UM County", "UM Country", "UM Phone",
        "Employee Status", "Employeee Status Descr", "uniqname", "Class Mtg Nbr",
        "Term", "Class Nbr", "Department ID", "Employee Status Descr",
        "Term Code", "Seq Number", "Instructor ID"
    ]
    merged.drop(columns=[c for c in db_drop if c in merged.columns], inplace=True)

    # Add location mapping
    bdict = load_buildings()
    merged["Location"] = merged["Bldg"].map(bdict).fillna(merged["Bldg"]) + " " + merged["Room"].fillna("")

    # Day / Subject filters
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    sel_day = st.selectbox("Select Day", days, key="db_day")
    day_df = merged[merged[sel_day].isin(["M", "T", "W", "R", "F", "X"])]

    subj_opts = sorted(day_df["Subject"].dropna().unique())
    sel_subj = st.selectbox("Select Subject", ["All"] + subj_opts, key="db_subj")
    if sel_subj != "All":
        day_df = day_df[day_df["Subject"] == sel_subj]

    st.dataframe(day_df)
    st.write(f"Total classes: {len(day_df)}")

# ------------------ Flint ------------------

def show_flint():
    st.header("Flint Schedule by Day and Subject")
    raw = pd.read_csv(FLINT_FILE, dtype=str)
    
    # Rename columns to match expected format (Flint uses uppercase)
    rename_map = {
        "TERM": "Term",
        "TERM_DESCRSHORT": "Term Descrshort", 
        "CRSE_DESCR": "Crse Descr",
        "SUBJECT": "Subject",
        "CATALOG_NUMBR": "Catalog Nbr",
        "CLASS_INST_ID": "Instructor ID",
        "CLASS_INSTR_NAME": "Class Instr Name",
        "CLASS_MTG_NBR": "Class Mtg Nbr",
        "FACILITY_ID": "Facility ID",
        "FACILITY_DESC": "Facility Descr",
        "MEETING_START_DT": "Meeting Start Dt",
        "MEETING_END_DT": "Meeting End Dt", 
        "MEETING_TIME_START": "Meeting Time Start",
        "MEETING_TIME_END": "Meeting Time End",
        "MON": "Mon",
        "TUES": "Tues",
        "WED": "Wed", 
        "THURS": "Thurs",
        "FRI": "Fri",
        "SAT": "Sat",
        "SUN": "Sun",
        "JOBCODE_DESCR": "Job Code Descr"
    }
    raw.rename(columns=rename_map, inplace=True)
    
    merged = merge_monthly_and_dues(raw, "Instructor ID")

    # Drop columns
    flint_drop = [
        "Instructor ID", "Facility ID", "Employee Last Name", "Employee First Name",
        "UM ID", "Rec #", "Class Indc", "Job Code", "Hire Begin Date", "Appointment Start Date",
        "Appointment End Date", "Comp Frequency", "Appointment Period", "Appointment Period Descr",
        "Comp Rate", "Home Address 1", "Home Address 2", "Home Address 3", "Home City", "Home State",
        "Home Postal", "Home County", "Home Country", "Home Phone", "UM Address 1", "UM Address 2",
        "UM Address 3", "UM City", "UM State", "UM Postal", "UM County", "UM Country", "UM Phone",
        "Employee Status", "Employeee Status Descr", "uniqname", "Class Mtg Nbr",
        "Term", "Class Nbr", "Department ID", "Employee Status Descr"
    ]
    merged.drop(columns=[c for c in flint_drop if c in merged.columns], inplace=True)

    # Day / Subject filters
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    dow_map = {"Monday": "Mon", "Tuesday": "Tues", "Wednesday": "Wed", "Thursday": "Thurs", "Friday": "Fri"}
    sel_day = st.selectbox("Select Day", days, key="fl_day")
    day_df = merged[merged[dow_map[sel_day]].eq("X")]

    subj_opts = sorted(day_df["Subject"].dropna().unique())
    sel_subj = st.selectbox("Select Subject", ["All"] + subj_opts, key="fl_subj")
    if sel_subj != "All":
        day_df = day_df[day_df["Subject"] == sel_subj]

    st.dataframe(day_df)
    st.write(f"Total classes: {len(day_df)}")

# ------------------ Main ------------------

st.title("UM Fall 2025 Schedule Explorer")
campus = st.selectbox("Select a Campus", ["Ann Arbor", "Dearborn", "Flint"])
if campus == "Ann Arbor":
    show_ann_arbor()
elif campus == "Dearborn":
    show_dearborn()
else:
    show_flint()
