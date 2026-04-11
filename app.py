import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime, timedelta

# --- 1. SETUP & SECRETS ---
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

st.set_page_config(page_title="AI Money Assistant", page_icon="💰")
st.title("💰 AI Money Assistant")

if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

user_input = st.text_area("✍️ Paste your full list of transactions:", height=200, 
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
           - Use High-Thinking to calculate EMI if % and years are provided.
        
        Return ONLY a JSON list: [{{"tab": "...", "row": [...]}}, ...]
        """

        try:
            interaction = client.interactions.create(
                model="gemini-3-flash-preview",
                input=user_input,
                system_instruction=system_msg,
                previous_interaction_id=st.session_state.interaction_id,
                generation_config={
                    "thinking_level": "high",
                    "temperature": 0.1
                }
            )
            
            st.session_state.interaction_id = interaction.id
            response_text = interaction.outputs[-1].text.strip()
            
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            
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

if st.button("🔄 Reset Conversation"):
    st.session_state.interaction_id = None
    st.rerun()
