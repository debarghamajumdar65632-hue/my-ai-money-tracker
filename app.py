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

user_note = st.text_area("✍️ Paste your list of expenses here:", height=150)

if st.button("🚀 Process & Save Rows"):
    if user_note:
        st.info("AI is splitting your list into rows...")
        
        # We use the Interactions API to turn text into a structured list
        prompt = f"""
        Analyze: '{user_note}'. 
        If there are multiple expenses, you MUST return a JSON LIST of objects.
        Each object MUST have:
        "tab": "Transactions",
        "row": [Date, Description, Amount, Category, Type]
        
        Return ONLY the JSON list. Do not include any other text.
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
            
            # Ensure we are working with a list even if only one item was sent [cite: 1271]
            if isinstance(data_entries, dict):
                data_entries = [data_entries]

            # The FIX: Loop through each item and save it as a NEW ROW
            for entry in data_entries:
                tab_name = entry.get('tab', 'Transactions')
                
                # Double check tab name to avoid errors
                if "friend" in tab_name.lower(): tab_name = "Friends_Debt"
                elif "loan" in tab_name.lower(): tab_name = "Loans_and_Savings"
                else: tab_name = "Transactions"
                
                ws = ss.worksheet(tab_name)
                
                # Convert all values to strings to prevent formatting errors
                clean_row = [str(x) for x in entry['row']]
                
                # This command adds a brand new row for every item
                ws.append_row(clean_row)
            
            st.success(f"✅ Success! Added {len(data_entries)} separate rows to your sheet.")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error: {e}")
