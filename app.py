import streamlit as st     
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime, timedelta
import pytz # Added for timezone handling

# --- 1. SETUP & SECRETS ---
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

client = genai.Client(api_key=API_KEY)

@st.cache_resource
def init_gsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open("My_AI_Finance_Manager")

try:
    ss = init_gsheet()
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

st.set_page_config(page_title="AI Money Assistant", page_icon="💰", layout="wide")

# --- 2. DYNAMIC DATE LOGIC ---
# Get current time in India (IST) instead of server time (UTC)
IST = pytz.timezone('Asia/Kolkata')
today_ist = datetime.now(IST)
today_str = today_ist.strftime("%Y-%m-%d")

# --- 3. SIDEBAR ---
st.sidebar.title("💰 AI Finance Menu")
st.sidebar.info(f"📅 Local Date: {today_str}") # Shows you what date the AI is using
page = st.sidebar.radio("Go to", ["Data Entry", "Financial Intelligence"])

# --- 4. PAGE: DATA ENTRY ---
if page == "Data Entry":
    st.title("✍️ Smart Transaction Entry")
    
    user_input = st.text_area("Paste transactions:", height=200, placeholder="e.g. spent 200 on dinner...")

    if st.button("🚀 Process & Save"):
        if user_input:
            default_due = (today_ist + timedelta(days=7)).strftime("%Y-%m-%d")
            st.info(f"🤖 AI is processing for date: {today_str}")
            
            system_msg = f"""
            CRITICAL: Today's date is EXACTLY {today_str}. 
            If the user says 'today', 'yesterday' (which would be {(today_ist - timedelta(days=1)).strftime('%Y-%m-%d')}), or just mentions a day, use {today_str} as the base reference.
            
            Return ONLY a JSON list: [{{'tab': '...', 'row': [...]}}].
            Headers:
            - Transactions: [Date, Description, Amount, Category, Type (Income/Expense)]
            - Friends_Debt: [Date, Friend Name, Amount, Description, Due Date, Status (Pending/Paid)]
            - Loans_and_Savings: [Goal/Loan Name, Target/Total Amount, Current Balance, EMI / Monthly Save, Status]
            """

            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=user_input,
                    config={"system_instruction": system_msg, "temperature": 0.1, "response_mime_type": "application/json"}
                )
                data_entries = json.loads(response.text.strip())
                
                for entry in data_entries:
                    ss.worksheet(entry['tab']).append_row([str(x) for x in entry['row']])
                
                st.success(f"✅ Successfully recorded for {today_str}!")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")

# --- 5. PAGE: FINANCIAL INTELLIGENCE ---
elif page == "Financial Intelligence":
    st.header("📊 Your Financial Cockpit")
    
    # [Rest of the Dashboard logic remains exactly the same as previously fixed]
    # (Including the specific header names for Type, Status, and Loans)
    def get_df(sheet_name):
        try:
            return pd.DataFrame(ss.worksheet(sheet_name).get_all_records())
        except:
            return pd.DataFrame()

    trans_data = get_df("Transactions")
    friend_data = get_df("Friends_Debt")
    loan_data = get_df("Loans_and_Savings")

    COL_TYPE = "Type (Income/Expense)"
    COL_FRIEND_STATUS = "Status (Pending/Paid)"
    COL_LOAN_TARGET = "Target/Total Amount"
    COL_LOAN_CURRENT = "Current Balance"

    if not trans_data.empty and COL_TYPE in trans_data.columns:
        trans_data['Amount'] = pd.to_numeric(trans_data['Amount'], errors='coerce').fillna(0)
        
        col1, col2, col3 = st.columns(3)
        expenses = trans_data[trans_data[COL_TYPE].astype(str).str.lower() == 'expense']
        income_df = trans_data[trans_data[COL_TYPE].astype(str).str.lower() == 'income']

        with col1:
            st.metric("Total Monthly Burn", f"₹{expenses['Amount'].sum():,.2f}")
        with col2:
            st.metric("Total Income", f"₹{income_df['Amount'].sum():,.2f}")
        with col3:
            pending_debt = 0
            if not friend_data.empty and COL_FRIEND_STATUS in friend_data.columns:
                friend_data['Amount'] = pd.to_numeric(friend_data['Amount'], errors='coerce').fillna(0)
                mask = friend_data[COL_FRIEND_STATUS].astype(str).str.lower().str.contains('pending')
                pending_debt = friend_data[mask]['Amount'].sum()
            st.metric("Pending Recoveries", f"₹{pending_debt:,.2f}")

        st.divider()
        if not expenses.empty:
            fig = px.pie(expenses, values='Amount', names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data found or headers mismatch.")
