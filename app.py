import streamlit as st     
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime, timedelta

# --- 1. SETUP & SECRETS ---
# Ensure these keys are set in your Streamlit Cloud Secrets
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets with caching to improve speed
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

# Initialize Session State for AI Context
if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("💰 AI Finance Menu")
page = st.sidebar.radio("Go to", ["Data Entry", "Financial Intelligence"])

# --- 3. PAGE: DATA ENTRY ---
if page == "Data Entry":
    st.title("✍️ Smart Transaction Entry")
    st.markdown("Type your transactions naturally (e.g., *'spent 200 on pizza'* or *'lent 1000 to Sarah'*)")
    
    user_input = st.text_area("Paste your full list of transactions:", height=200, 
                             placeholder="e.g. 45 for metro, lent 500 to Roy, 5 lakh loan at 8% for 2 years...")

    if st.button("🚀 Process & Save Everything"):
        if user_input:
            today = datetime.now().strftime("%Y-%m-%d")
            default_due = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
            st.info("🤖 AI is auditing entries and calculating due dates...")
            
            system_msg = f"""
            Today is {today}. Default Due Date is {default_due}.
            Break down EVERY SINGLE transaction into a separate JSON object in a list. 
            
            TABS & RULES:
            1. 'Transactions': [Date, Description, Amount, Category, Type]
            2. 'Friends_Debt': [Date, FriendName, Amount, Description, DueDate, Status]
               - RULE: If no due date is mentioned, use {default_due}.
               - If they 'gave back', Status is 'Paid'. If you 'lent', Status is 'Pending'.
            3. 'Loans_and_Savings': [Goal/Loan Name, TargetAmount, CurrentBalance, EMIAmount, Status]
               - Calculate EMI if interest and years are provided.
            
            Return ONLY a JSON list: [{{"tab": "...", "row": [...]}}, ...]
            """

            try:
                # Using Gemini 2.0 Flash for speed and JSON reliability
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
                
                st.success(f"✅ Successfully recorded {saved_count} items to Google Sheets!")
                st.balloons()

            except Exception as e:
                st.error(f"❌ Error processing input: {e}")
        else:
            st.warning("Please enter some text first!")

    if st.button("🔄 Reset AI Context"):
        st.session_state.interaction_id = None
        st.rerun()

# --- 4. PAGE: FINANCIAL INTELLIGENCE ---
elif page == "Financial Intelligence":
    st.header("📊 Your Financial Cockpit")
    
    # Helper to load data safely from sheets
    def get_df(sheet_name):
        try:
            data = ss.worksheet(sheet_name).get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()

    trans_data = get_df("Transactions")
    loan_data = get_df("Loans_and_Savings")
    friend_data = get_df("Friends_Debt")

    if not trans_data.empty:
        # Data Cleaning: Ensure Amount is numeric
        trans_data['Amount'] = pd.to_numeric(trans_data['Amount'], errors='coerce').fillna(0)
        
        # 1. TOP LEVEL METRICS
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_spent = trans_data[trans_data['Type'].str.lower() == 'expense']['Amount'].sum()
            st.metric("Total Monthly Burn", f"₹{total_spent:,.2f}")

        with col2:
            total_income = trans_data[trans_data['Type'].str.lower() == 'income']['Amount'].sum()
            pending_debt = 0
            if not friend_data.empty:
                friend_data['Amount'] = pd.to_numeric(friend_data['Amount'], errors='coerce').fillna(0)
                pending_debt = friend_data[friend_data['Status'].str.lower() == 'pending']['Amount'].sum()
            
            ratio = (pending_debt / total_income * 100) if total_income > 0 else 0
            st.metric("Debt-to-Income Ratio", f"{ratio:.1f}%")

        with col3:
            st.metric("Total Income", f"₹{total_income:,.2f}")

        st.divider()

        # 2. VISUALIZATIONS
        v_col1, v_col2 = st.columns(2)

        with v_col1:
            st.subheader("🍕 Spending by Category")
            expense_df = trans_data[trans_data['Type'].str.lower() == 'expense']
            if not expense_df.empty:
                fig = px.pie(expense_df, values='Amount', names='Category', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Add expenses to see the breakdown.")

        with v_col2:
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
                st.info("No active goals or loans found.")

        # 3. AI AUDITOR
        st.divider()
        st.subheader("🤖 AI Auditor Suggestions")
        if ratio > 40:
            st.warning("⚠️ **High Debt Warning**: Your pending debts are over 40% of your income. Avoid further lending.")
        
        recurring = trans_data['Description'].value_counts()
        if not recurring.empty and recurring.max() > 1:
            subs = recurring[recurring > 1].index.tolist()
            st.info(f"🧐 **Subscription Alert**: You have multiple entries for: *{', '.join(subs)}*. Are these recurring bills?")
            
    else:
        st.warning("No data found! Go to the 'Data Entry' page and paste your transactions first.")
