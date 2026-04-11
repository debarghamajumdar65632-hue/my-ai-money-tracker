import streamlit as st     
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime, timedelta

# --- 1. SETUP & SECRETS ---
# Make sure these keys exist in your .streamlit/secrets.toml
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets
@st.cache_resource
def init_gsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open("My_AI_Finance_Manager")

ss = init_gsheet()

st.set_page_config(page_title="AI Money Assistant", page_icon="💰")

# Initialize Session State
if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Data Entry", "Financial Intelligence"])

# --- 3. PAGE: DATA ENTRY ---
if page == "Data Entry":
    st.title("✍️ Transaction Entry")
    user_input = st.text_area("Paste your full list of transactions:", height=200, 
                             placeholder="e.g. 45 for metro, lent 500 to Roy, 5 lakh loan...")

    if st.button("🚀 Process & Save Everything"):
        if user_input:
            today = datetime.now().strftime("%Y-%m-%d")
            default_due = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
            st.info("AI is auditing entries and calculating due dates...")
            
            system_msg = f"""
            Today is {today}. Default Due Date is {default_due}.
            Break down EVERY SINGLE transaction into a separate JSON object in a list. 
            
            TABS & RULES:
            1. 'Transactions': [Date, Description, Amount, Category, Type]
            2. 'Friends_Debt': [Date, FriendName, Amount, Description, DueDate, Status]
               - RULE: If no due date is mentioned, use the default: {default_due}.
               - If they 'gave back', Status is 'Paid'. If you 'lent', Status is 'Pending'.
            3. 'Loans_and_Savings': [Goal/Loan Name, TargetAmount, CurrentBalance, EMIAmount, Status]
            
            Return ONLY a JSON list: [{{"tab": "...", "row": [...]}}, ...]
            """

            try:
                # Note: Using the official client.models.generate_content for standard Gemini API
                # Adjust if using a specific 'interactions' preview SDK
                response = client.models.generate_content(
                    model="gemini-2.0-flash", # Updated to a stable version name
                    contents=user_input,
                    config={
                        "system_instruction": system_msg,
                        "temperature": 0.1,
                        "response_mime_type": "application/json"
                    }
                )
                
                response_text = response.text.strip()
                data_entries = json.loads(response_text)
                
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

# --- 4. PAGE: DASHBOARD ---
elif page == "Financial Intelligence":
    st.header("📊 Your Financial Cockpit")
    
    # Helper to load data safely
    def get_data(sheet_name):
        data = ss.worksheet(sheet_name).get_all_records()
        return pd.DataFrame(data)

    trans_data = get_data("Transactions")
    loan_data = get_data("Loans_and_Savings")
    friend_data = get_data("Friends_Debt")

    if not trans_data.empty:
        # Convert types
        trans_data['Amount'] = pd.to_numeric(trans_data['Amount'], errors='coerce').fillna(0)
        
        # 2. METRICS PILLAR
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_spent = trans_data[trans_data['Type'].str.lower() == 'expense']['Amount'].sum()
            st.metric("Total Monthly Burn", f"₹{total_spent:,.2f}")

        with col2:
            total_income = trans_data[trans_data['Type'].str.lower() == 'income']['Amount'].sum()
            pending_debt = 0
            if not friend_data.empty:
                friend_data['Amount'] = pd.to_numeric(friend_data['Amount'], errors='coerce').fillna(0)
                pending_debt = friend_data[friend_data['Status'] == 'Pending']['Amount'].sum()
            
            ratio = (pending_debt / total_income * 100) if total_income > 0 else 0
            st.metric("Debt-to-Income Ratio", f"{ratio:.1f}%")

        # 3. VISUALIZATION PILLAR
        st.subheader("🎯 Goal Progress")
        if not loan_data.empty:
            for _, row in loan_data.iterrows():
                target = float(row['TargetAmount']) if row['TargetAmount'] else 1
                current = float(row['CurrentBalance']) if row['CurrentBalance'] else 0
                progress = min(current / target, 1.0)
                
                st.write(f"**{row['Goal/Loan Name']}**")
                st.progress(progress)
                st.caption(f"₹{current:,.0f} of ₹{target:,.0f} ({progress*100:.1f}%)")
        else:
            st.info("No goals tracked yet.")

        # 4. AUDITOR SUGGESTIONS
        st.subheader("🤖 AI Auditor Suggestions")
        if ratio > 40:
            st.warning("⚠️ High Debt Warning: Your obligations exceed 40% of your income.")
        
        recurring = trans_data['Description'].value_counts()
        if not recurring.empty and recurring.max() > 1:
            subs = recurring[recurring > 1].index.tolist()
            st.info(f"🧐 Possible Subscriptions: {', '.join(subs)}.")
    else:
        st.warning("No transaction data found. Go to 'Data Entry' to add some!")
