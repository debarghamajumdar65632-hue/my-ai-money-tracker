import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime

# --- SETUP ---
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

client = genai.Client(api_key=API_KEY)

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

st.title("💰 AI Money Assistant")
user_note = st.text_area("✍️ Paste your expenses, friend debts, or EMI details:", height=150)

if st.button("🚀 Process & Save All"):
    if user_note:
        st.info("AI is sorting your data into the correct tabs...")
        
        # We define the MAP for every tab based on your screenshots
        prompt = f"""
        Analyze: '{user_note}'. 
        You must return a JSON LIST of objects. Sort items into these exact tabs:
        
        1. 'Transactions' (For general spend):
           row: [Date, Description, Amount, Category, Type]
        
        2. 'Friends_Debt' (If a friend name is mentioned):
           row: [Date, Friend Name, Amount, Description, Due Date, Status(Pending)]
        
        3. 'Loans_and_Savings' (For EMIs or Loan details):
           row: [Goal/Loan Name, Target Amount, Current Balance, EMI/Monthly Save, Status]

        Return ONLY the JSON list.
        """

        try:
            interaction = client.interactions.create(
                model="gemini-3-flash-preview",
                input=prompt
            )
            
            raw_text = interaction.outputs[-1].text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            
            data_entries = json.loads(raw_text)
            if isinstance(data_entries, dict): data_entries = [data_entries]

            for entry in data_entries:
                tab_name = entry['tab']
                ws = ss.worksheet(tab_name)
                
                # Convert everything to string for safety
                clean_row = [str(x) for x in entry['row']]
                ws.append_row(clean_row)
            
            st.success(f"✅ Successfully sorted {len(data_entries)} items into your tabs!")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error: {e}")
