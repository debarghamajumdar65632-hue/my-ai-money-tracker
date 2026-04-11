import streamlit as st     
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime, timedelta

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

if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# --- 2. SIDEBAR ---
st.sidebar.title("💰 AI Finance Menu")
page = st.sidebar.radio("Go to", ["Data Entry", "Financial Intelligence"])

# --- 3. PAGE: DATA ENTRY ---
if page == "Data Entry":
    st.title("✍️ Smart Transaction Entry")
    user_input = st.text_area("Paste transactions:", height=200, placeholder="e.g. spent 200 on dinner...")

    if st.button("🚀 Process & Save"):
        if user_input:
            today = datetime.now().strftime("%Y-%m-%d")
            st.info("🤖 AI is processing...")
            
            # UPDATED SYSTEM MSG: Precise Header Sync for AI writing
            system_msg = f"""
            Today is {today}. Return ONLY a JSON list: [{{'tab': '...', 'row': [...]}}].
            Headers:
            - Transactions: [Date, Description, Amount, Category, Type (Income/Expense)]
            - Friends_Debt: [Date, FriendName, Amount, Description, Due Date, Status (Pending/Paid)]
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
                st.success("✅ Recorded!")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")

# --- 4. PAGE: FINANCIAL INTELLIGENCE ---
elif page == "Financial Intelligence":
    st.header("📊 Your Financial Cockpit")
    
    def get_df(sheet_name):
        try:
            return pd.DataFrame(ss.worksheet(sheet_name).get_all_records())
        except:
            return pd.DataFrame()

    trans_data = get_df("Transactions")
    friend_data = get_df("Friends_Debt")
    loan_data = get_df("Loans_and_Savings")

    # Mapping Header Names exactly from your screenshots
    COL_TYPE = "Type (Income/Expense)"
    COL_FRIEND_STATUS = "Status (Pending/Paid)"
    COL_LOAN_TARGET = "Target/Total Amount"
    COL_LOAN_CURRENT = "Current Balance"

    if not trans_data.empty:
        trans_data['Amount'] = pd.to_numeric(trans_data['Amount'], errors='coerce').fillna(0)
        
        col1, col2, col3 = st.columns(3)
        
        # 1. Total Burn (Expenses)
        total_spent = 0
        if COL_TYPE in trans_data.columns:
            expenses = trans_data[trans_data[COL_TYPE].astype(str).str.lower() == 'expense']
            total_spent = expenses['Amount'].sum()
        
        # 2. Total Income
        total_income = 0
        if COL_TYPE in trans_data.columns:
            income_df = trans_data[trans_data[COL_TYPE].astype(str).str.lower() == 'income']
            total_income = income_df['Amount'].sum()

        # 3. Pending Recoveries (Friends)
        pending_debt = 0
        if not friend_data.empty and COL_FRIEND_STATUS in friend_data.columns:
            friend_data['Amount'] = pd.to_numeric(friend_data['Amount'], errors='coerce').fillna(0)
            # Checking for 'Pending' in the status column
            pending_mask = friend_data[COL_FRIEND_STATUS].astype(str).str.lower().str.contains('pending')
            pending_debt = friend_data[pending_mask]['Amount'].sum()

        with col1:
            st.metric("Total Monthly Burn", f"₹{total_spent:,.2f}")
        with col2:
            st.metric("Total Income", f"₹{total_income:,.2f}")
        with col3:
            st.metric("Pending Recoveries", f"₹{pending_debt:,.2f}")

        st.divider()

        # Visuals
        c1, c2 = st.columns(2)
        with c1:
            if COL_TYPE in trans_data.columns:
                expenses = trans_data[trans_data[COL_TYPE].astype(str).str.lower() == 'expense']
                if not expenses.empty:
                    st.subheader("🍕 Spending Breakdown")
                    fig = px.pie(expenses, values='Amount', names='Category', hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("🎯 Goal Progress")
            if not loan_data.empty and COL_LOAN_TARGET in loan_data.columns:
                for _, row in loan_data.iterrows():
                    try:
                        target = float(row[COL_LOAN_TARGET]) if row[COL_LOAN_TARGET] else 1
                        current = float(row[COL_LOAN_CURRENT]) if row[COL_LOAN_CURRENT] else 0
                        st.write(f"**{row['Goal/Loan Name']}**")
                        st.progress(min(current/target, 1.0))
                    except: continue
            else:
                st.info("No goals found in 'Loans_and_Savings'.")

    else:
        st.warning("No data found in 'Transactions'.")
