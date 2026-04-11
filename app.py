import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime

# --- 1. SETUP & SECRETS ---
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

# Connect to Gemini 3
client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

st.set_page_config(page_title="AI Money Assistant", page_icon="💰")
st.title("💰 AI Money Assistant")

# Memory management for conversation follow-ups
if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# Input area
user_input = st.text_area("✍️ Paste your full list of transactions:", height=200, 
                         placeholder="e.g. 45 for metro, tomato for 25, 5 lakh loan at 9.5%, Roy paid back 500...")

if st.button("🚀 Process & Save Every Item"):
    if user_input:
        st.info("AI is performing a meticulous audit to ensure all items are recorded...")
        
        # SYSTEM PROMPT: Forces zero-loss itemization and loan math
        system_msg = """
        You are a meticulous financial auditor. 
        Break down EVERY SINGLE transaction into a separate JSON object in a list. 
        DO NOT summarize. If there are 5 expenses, create 5 objects.
        
        Tabs:
        1. 'Transactions': [Date, Description, Amount, Category, Type]
        2. 'Friends_Debt': [Date, FriendName, Amount, Description, DueDate, Status]
        3. 'Loans_and_Savings': [Goal/Loan Name, TargetAmount, CurrentBalance, EMIAmount, Status]
        
        LOGIC:
        - For 'gave back' or 'owed', use 'Friends_Debt'. Status='Paid' if they gave it back.
        - For Loans with % interest: CALCULATE the EMI using standard formula.
        - For EMIs with 'months left': Calculate Total and Balance.
        
        Return ONLY a JSON list: [{"tab": "...", "row": [...]}, ...]
        """

        try:
            # High Thinking for the 5-lakh loan math
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
            if isinstance(data_entries, dict): 
                data_entries = [data_entries]

            # SAVE EVERY ROW ONE BY ONE
            saved_count = 0
            for entry in data_entries:
                ws = ss.worksheet(entry['tab'])
                # Convert all values to string to prevent Error 400
                ws.append_row([str(x) for x in entry['row']])
                saved_count += 1
            
            st.success(f"✅ Successfully recorded {saved_count} items into your sheet!")
            st.balloons()

        except Exception as e:
            st.error(f"❌ Error: {e}")

if st.button("🔄 Reset Conversation"):
    st.session_state.interaction_id = None
    st.rerun()
