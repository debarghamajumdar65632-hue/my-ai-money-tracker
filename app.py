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
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

st.set_page_config(page_title="AI Money Assistant", page_icon="💰", layout="wide")

if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("💰 AI Finance Menu")
page = st.sidebar.radio("Go to", ["Data Entry", "Financial Intelligence"])

# --- 3. PAGE: DATA ENTRY ---
if page == "Data Entry":
    st.title("✍️ Smart Transaction Entry")
    user_input = st.text_area("Paste your transactions:", height=200, 
                             placeholder="e.g. 45 for metro, lent 500 to Roy...")

    if st.button("🚀 Process & Save Everything"):
        if user_input:
            today = datetime.now().strftime("%Y-%m-%d")
            default_due = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            st.info("🤖 AI is auditing entries...")
            
            # This system message ensures AI uses your EXACT sheet headers
            system_msg = f"""
            Today is {today}. Return ONLY a JSON list: [{{'tab': '...', 'row': [...]}}].
            
            TABS & RULES:
            1. 'Transactions': [Date, Description, Amount, Category, Type (Income/Expense)]
            2. 'Friends_Debt': [Date, FriendName, Amount, Description, DueDate, Status]
            3. 'Loans_and_Savings': [Goal/Loan Name, TargetAmount, CurrentBalance, EMIAmount, Status]
            """

            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=user_input,
                    config={
                        "system_instruction": system_msg,
                        "temperature": 0.1,
                        "response_mime_type": "application/json"
                    }
                )
                
                data_entries = json.loads(response.text.strip())
                if isinstance(data_entries, dict): data_entries = [data_entries]

                saved_count = 0
                for entry in data_entries:
                    ws = ss.worksheet(entry['tab'])
                    ws.append_row([str(x) for x in entry['row']])
                    saved_count += 1
                
                st.success(f"✅ Successfully recorded {saved_count} items!")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    if st.button("🔄 Reset AI Context"):
        st.session_state.interaction_id = None
        st.rerun()

# --- 4. PAGE: FINANCIAL INTELLIGENCE ---
elif page == "Financial Intelligence":
    st.header("📊 Your Financial Cockpit")
    
    def get_data(sheet_name):
        try:
            return pd.DataFrame(ss.worksheet(sheet_name).get_all_records())
        except:
            return pd.DataFrame()

    trans_data = get_data("Transactions")
    loan_data = get_data("Loans_and_Savings")
    friend_data = get_data("Friends_Debt")

    # This variable matches the header seen in your screenshot exactly
    HEADER_NAME = "Type (Income/Expense)"

    if not trans_data.empty and HEADER_NAME in trans_data.columns:
        trans_data['Amount'] = pd.to_numeric(trans_data['Amount'], errors='coerce').fillna(0)
        
        col1, col2, col3 = st.columns(3)
        
        # Filter logic using the new header name
        expense_df = trans_data[trans_data[HEADER_NAME].astype(str).str.lower() == 'expense']
        income_df = trans_data[trans_data[HEADER_NAME].astype(str).str.lower() == 'income']
        
        with col1:
            st.metric("Total Monthly Burn", f"₹{expense_df['Amount'].sum():,.2f}")

        with col2:
            total_income = income_df['Amount'].sum()
            pending_debt = 0
            if not friend_data.empty and 'Amount' in friend_data.columns:
                friend_data['Amount'] = pd.to_numeric(friend_data['Amount'], errors='coerce').fillna(0)
                pending_debt = friend_data[friend_data['Status'] == 'Pending']['Amount'].sum()
            
            ratio = (pending_debt / total_income * 100) if total_income > 0 else 0
            st.metric("Debt-to-Income Ratio", f"{ratio:.1f}%")

        with col3:
            st.metric("Pending Recoveries", f"₹{pending_debt:,.2f}")

        st.divider()

        # Visuals
        c1, c2 = st.columns(2)
        with c1:
            if not expense_df.empty:
                st.subheader("🍕 Spending Breakdown")
                fig = px.pie(expense_df, values='Amount', names='Category', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("🎯 Goal Progress")
            if not loan_data.empty:
                for _, row in loan_data.iterrows():
                    try:
                        target = float(row['TargetAmount']) if row['TargetAmount'] else 1
                        current = float(row['CurrentBalance']) if row['CurrentBalance'] else 0
                        st.write(f"**{row['Goal/Loan Name']}**")
                        st.progress(min(current/target, 1.0))
                    except: continue
            else:
                st.info("No goals tracked yet.")
    else:
        st.warning(f"Check your spreadsheet! Column '{HEADER_NAME}' was not found.")
