import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import re

# --- CONFIGURATION ---
SOCIETY_UPI_ID = "treasurer@upi"  # REPLACE with actual UPI ID
SOCIETY_NAME_SHORT = "RPE Association"
SOCIETY_NAME_FULL = "RPE Owners/Residents Association"
GOOGLE_SHEET_NAME = "Society_Payments_DB"
JSON_KEY_FILE = "service_account.json"
MONTHLY_FEE = 300

# --- COMPACT STYLING ---
def local_css():
    st.markdown(
        """
        <style>
        /* Compact Main Container */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
        
        /* Compact Header */
        .main-header {
            background-color: var(--secondary-background-color);
            padding: 12px 15px; /* Reduced padding */
            border-radius: 8px;
            border-left: 5px solid #FF4B4B;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .main-title {
            color: var(--text-color);
            font-size: 22px; /* Smaller font */
            font-weight: bold;
            margin: 0;
            font-family: 'Segoe UI', sans-serif;
        }
        .sub-title {
            color: var(--text-color);
            opacity: 0.8;
            font-size: 14px;
            margin: 0;
        }
        
        /* Compact Form */
        div[data-testid="stForm"] {
            background-color: var(--secondary-background-color);
            padding: 15px; /* Reduced padding */
            border-radius: 8px;
            border: 1px solid rgba(128, 128, 128, 0.2); 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Tighten Input Spacing */
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important; /* Reduced gap between elements */
        }
        
        /* Disabled Input Style */
        input[disabled] {
            color: var(--text-color) !important;
            -webkit-text-fill-color: var(--text-color) !important;
            opacity: 1 !important;
            font-weight: bold !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Updated Connection Function for Streamlit Cloud
def get_google_sheet():
    # Use Streamlit Secrets instead of a local file
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(GOOGLE_SHEET_NAME).sheet1

# --- HELPER: GENERATE MONTH LIST ---
def get_target_months(p_type, year, qtr=None, month=None):
    if p_type == "Year":
        return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    elif p_type == "Quarter":
        if qtr == "Q1": return ["Jan", "Feb", "Mar"]
        if qtr == "Q2": return ["Apr", "May", "Jun"]
        if qtr == "Q3": return ["Jul", "Aug", "Sep"]
        if qtr == "Q4": return ["Oct", "Nov", "Dec"]
    else:
        return [month]

# --- HELPER: NATURAL SORTING ---
def natural_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]

# --- PAGE SETUP ---
st.set_page_config(page_title=SOCIETY_NAME_SHORT, page_icon="🏢", layout="wide") # Added 'wide' for desktop
local_css()

# Custom Header
st.markdown(f"""
    <div class="main-header">
        <div class="main-title">🏢 {SOCIETY_NAME_FULL}</div>
        <div class="sub-title">Payment Portal</div>
    </div>
""", unsafe_allow_html=True)

# --- LOAD DATA ---
try:
    df = pd.read_csv("data.csv")
    df.columns = df.columns.str.strip()
    df['Plot No.'] = df['Plot No.'].astype(str)
    
    if 'Lane No.' in df.columns:
        df = df.dropna(subset=['Lane No.'])
        df['Lane No.'] = df['Lane No.'].astype(str).str.replace(r'\.0$', '', regex=True)
    else:
        st.error("⚠️ Column 'Lane No.' not found in data.csv.")
        st.stop()
        
except FileNotFoundError:
    st.error("❌ Critical Error: 'data.csv' not found.")
    st.stop()

# --- COMPACT LAYOUT CONTAINER ---
# We use one container for Identity & Payment details to keep them tight
with st.container():
    # Split into 3 small columns for Identity
    c_lane, c_plot, c_info = st.columns([1, 1, 2])
    
    with c_lane:
        unique_lanes = sorted(df['Lane No.'].unique(), key=natural_key)
        selected_lane = st.selectbox("Lane", unique_lanes)
        
    with c_plot:
        filtered_plots = sorted(df[df['Lane No.'] == selected_lane]['Plot No.'].unique(), key=natural_key)
        plot_no = st.selectbox("Plot", filtered_plots)
        
    # Fetch Data
    resident_data = df[df['Plot No.'] == plot_no].iloc[0]
    resident_name = resident_data['Name']
    
    with c_info:
        # Check Dues
        msg = f"👤 **{resident_name}**"
        if 'Past Dues' in df.columns:
            past_dues = resident_data['Past Dues']
            try:
                past_dues = float(str(past_dues).replace(',', '').replace('₹', ''))
            except:
                past_dues = 0
            
            if past_dues > 0:
                st.error(f"{msg} | ⚠️ **Past Dues: ₹{int(past_dues)}**")
            else:
                st.success(f"{msg} | ✅ **No Past Dues**")
        else:
            st.info(msg)

    # --- PAYMENT DETAILS (TIGHT ROW) ---
    c_type, c_time, c_amt = st.columns([1.5, 2, 1.5])
    
    with c_type:
        period_type = st.radio("Period", ["Year", "Quarter", "Month"], horizontal=True, label_visibility="collapsed")

    with c_time:
        # Nested columns for super compact Year/Month selection
        t1, t2 = st.columns(2)
        years = [str(y) for y in range(2022, 2029)]
        selected_year = t1.selectbox("Year", years, label_visibility="collapsed")
        
        selected_qtr = None; selected_month = None
        if period_type == "Quarter":
            selected_qtr = t2.selectbox("Qtr", ["Q1", "Q2", "Q3", "Q4"], label_visibility="collapsed")
        elif period_type == "Month":
            selected_month = t2.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], label_visibility="collapsed")

    # Calculation
    if period_type == "Year": auto_amount = MONTHLY_FEE * 12
    elif period_type == "Quarter": auto_amount = MONTHLY_FEE * 3
    else: auto_amount = MONTHLY_FEE * 1

    with c_amt:
        st.markdown(f"**Total: ₹{auto_amount}**")
        st.caption(f"(₹{MONTHLY_FEE}/m)")

# --- FLASHY WARNING (COMPACT) ---
st.markdown("""
    <div style='background-color: #ffebee; border-left: 4px solid #d32f2f; padding: 10px; border-radius: 4px; margin-bottom: 10px; font-size: 0.9rem;'>
        <strong style='color: #b71c1c;'>⚠️ CRITICAL:</strong> 
        <span style='color: #c62828;'>Payment will NOT be recorded until Proof is submitted below.</span>
    </div>
""", unsafe_allow_html=True)

# --- PAY BUTTONS ---
# Generate Link
if period_type == "Year": note_suffix = f"{selected_year}"
elif period_type == "Quarter": note_suffix = f"{selected_qtr}_{selected_year}"
else: note_suffix = f"{selected_month}_{selected_year}"

upi_note = f"{plot_no}_{note_suffix}"
upi_url = f"upi://pay?pa={SOCIETY_UPI_ID}&pn={SOCIETY_NAME_SHORT}&am={auto_amount}&tn={upi_note}"

b1, b2 = st.columns(2)
b1.link_button("🔵 Pay via PhonePe", upi_url, use_container_width=True)
b2.link_button("🟢 Pay via GPay", upi_url, use_container_width=True)

# --- PROOF FORM (COMPACT) ---
with st.form("verify_form", border=True):
    st.write("**Submit Payment Proof**")
    
    # Row 1: Amount & UTR
    f1, f2 = st.columns(2)
    with f1:
        amount_paid_user = st.number_input("Amount Paid (₹)", value=int(auto_amount), step=1)
    with f2:
        txn_id = st.text_input("UTR / Transaction ID")
        
    # Row 2: File Upload & Checkbox
    uploaded_file = st.file_uploader("Screenshot (Optional)", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
    paid_confirm = st.checkbox(f"I transferred ₹{amount_paid_user}")
    
    # Submit
    if st.form_submit_button("✅ Verify & Record Payment", use_container_width=True):
        if not paid_confirm:
            st.error("Please confirm the checkbox.")
        elif not txn_id and not uploaded_file:
            st.error("Provide UTR or Screenshot.")
        else:
            with st.spinner("Recording..."):
                try:
                    target_months = get_target_months(period_type, selected_year, selected_qtr, selected_month)
                    if len(target_months) > 0: split_amount = amount_paid_user / len(target_months)
                    else: split_amount = amount_paid_user

                    receipt_status = "Uploaded" if uploaded_file else "None"
                    final_txn = txn_id if txn_id else "Screenshot"
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    sheet = get_google_sheet()
                    rows_to_add = []
                    
                    for m in target_months:
                        row = [
                            current_time, plot_no, resident_name, f"{m} {selected_year}",
                            split_amount, final_txn, receipt_status,
                            f"Part of {period_type}", "Pending"
                        ]
                        rows_to_add.append(row)
                    
                    for row in rows_to_add: sheet.append_row(row)
                    st.success("Saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# --- LEDGER (COMPACT) ---
with st.expander(f"📜 History: {plot_no}", expanded=True):
    try:
        sheet = get_google_sheet()
        data = sheet.get_all_records()
        if data:
            history_df = pd.DataFrame(data)
            history_df.columns = history_df.columns.str.strip()
            history_df['Plot No'] = history_df['Plot No'].astype(str)
            my_history = history_df[history_df['Plot No'] == str(plot_no)]
            
            if not my_history.empty:
                my_history = my_history.rename(columns={
                    "Date": "Date", "Period": "Period", "Amount": "Amt", 
                    "Transaction ID": "UTR", "Verified": "Status", 
                    "verified": "Status", "Payment verified": "Status"
                })
                if "Status" not in my_history.columns: my_history["Status"] = "Pending"
                st.dataframe(my_history[["Date", "Period", "Amt", "UTR", "Status"]], use_container_width=True, hide_index=True)
            else:
                st.info("No records.")
        else:
            st.info("Empty ledger.")
    except:
        st.warning("Loading...")