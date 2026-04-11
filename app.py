import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime

# --- 1. SETUP ---
# Fetching keys from Streamlit Secrets
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

# Connect to Gemini 3 Brain (Interactions API) [cite: 9, 22]
client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

# --- 2. INTERFACE ---
st.title("💰 AI Money Assistant")
st.write("Ensure your Sheet tabs are exactly: **Transactions**, **Friends_Debt**, **Loans_and_Savings**")

# Input options
uploaded_image = st.file_uploader("📷 Scan Receipt", type=['png', 'jpg', 'jpeg'])
user_note = st.text_input("✍️ Type details:", placeholder="e.g., 45 for metro, or Lent 50 to Sarah")

# --- 3. STABLE LOGIC ---
if st.button("🚀 Save to Tracker"):
    input_data = None
    prompt_instruction = """
    Return ONLY JSON with:
    "tab": (Must be 'Transactions', 'Friends_Debt', or 'Loans_and_Savings'),
    "row": [Date(YYYY-MM-DD), Description, Amount, Category, Type]
    """

    if uploaded_image:
        st.info("Scanning...")
        # Multimodal input for receipt scanning [cite: 124, 132]
        input_data = [
            {"type": "text", "text": f"Read this receipt. {prompt_instruction}"},
            {"type": "image", "data": uploaded_image.getvalue(), "mime_type": uploaded_image.type}
        ]
    elif user_note:
        st.info("Analyzing...")
        input_data = f"{prompt_instruction}\nInput: {user_note}"

    if input_data:
        try:
            # Using Interactions API for reliable extraction [cite: 9, 41]
            interaction = client.interactions.create(
                model="gemini-3-flash-preview",
                input=input_data
            )
            
            # Clean and parse JSON [cite: 977, 978]
            raw_text = interaction.outputs[-1].text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(raw_text)
            
            # FORCE VALIDATION: This prevents the WorksheetNotFound error
            valid_tabs = ["Transactions", "Friends_Debt", "Loans_and_Savings"]
            suggested_tab = result['tab'].strip()
            
            # If AI makes a typo, we fix it here
            if suggested_tab not in valid_tabs:
                if "friend" in suggested_tab.lower(): suggested_tab = "Friends_Debt"
                elif "loan" in suggested_tab.lower(): suggested_tab = "Loans_and_Savings"
                else: suggested_tab = "Transactions"

            # Save to sheet
            target_tab = ss.worksheet(suggested_tab)
            
            # We convert everything to a string (text) to prevent the [400] error
            row_to_save = [str(item) for item in result['row']]
            
            target_tab.append_row(row_to_save)
            
            st.success(f"✅ Saved to {suggested_tab}!")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error: {e}")
