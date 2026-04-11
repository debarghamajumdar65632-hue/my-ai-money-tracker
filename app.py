import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime

# --- SETUP ---
# We will put your secrets in Streamlit, not in the code!
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

# 1. Connect to Brain (Interactions API)
client = genai.Client(api_key=API_KEY)

# 2. Connect to Sheet
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

st.title("💰 AI Money Assistant")
st.info("Input salary, friend debts, or EMI details below.")

# --- APP INTERFACE ---
user_note = st.text_input("Enter expense/income details:", placeholder="e.g., Sarah owes me 20 for pizza")

if st.button("Add to Tracker"):
    if user_note:
        # Use Interactions API for smart classification [cite: 9, 35]
        interaction = client.interactions.create(
            model="gemini-3-flash-preview",
            input=f"Analyze: '{user_note}'. Return JSON ONLY: {{'tab': 'TabName', 'row': [values]}}"
        )
        
        # Parse result
        json_text = interaction.outputs[-1].text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(json_text)
        
        # Save to Google Sheet
        target_tab = ss.worksheet(result['tab'])
        target_tab.append_row(result['row'])
        st.success(f"Added to {result['tab']}!")
