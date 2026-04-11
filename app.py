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

# --- NEW: SCAN & VOICE SECTION ---
st.subheader("📷 Scan or 🎤 Speak")
col1, col2 = st.columns(2)

with col1:
    # This adds the Scan button
    uploaded_image = st.file_uploader("Upload Receipt", type=['png', 'jpg', 'jpeg'])

with col2:
    # This adds the Voice button (for recorded files)
    uploaded_audio = st.file_uploader("Upload Voice Note", type=['mp3', 'wav', 'm4a'])

# --- TRADITIONAL TEXT SECTION ---
st.divider()
user_note = st.text_input("Or type details here:", placeholder="e.g., Sarah owes me 20 for pizza")

# --- LOGIC TO PROCESS EVERYTHING ---
if st.button("Add to Tracker"):
    input_data = []
    
    # 1. Handle Image (Scan)
    if uploaded_image:
        # According to your doc, we can send images directly
        img_bytes = uploaded_image.getvalue()
        input_data = [
            {"type": "text", "text": "Analyze this receipt. Return ONLY JSON: {'tab': 'TabName', 'row': [values]}"},
            {"type": "image", "data": img_bytes, "mime_type": uploaded_image.type}
        ]
    
    # 2. Handle Audio (Voice)
    elif uploaded_audio:
        # According to your doc, we can send audio too
        audio_bytes = uploaded_audio.getvalue()
        input_data = [
            {"type": "text", "text": "Listen to this note. Return ONLY JSON: {'tab': 'TabName', 'row': [values]}"},
            {"type": "audio", "data": audio_bytes, "mime_type": uploaded_audio.type}
        ]
    
    # 3. Handle Text
    elif user_note:
        input_data = f"Analyze: '{user_note}'. Return ONLY JSON: {{'tab': 'TabName', 'row': [values]}}"

    if input_data:
        # Using the Interactions API from your document
        interaction = client.interactions.create(
            model="gemini-3-flash-preview",
            input=input_data
        )
        
        # Parse and save
        json_text = interaction.outputs[-1].text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(json_text)
        target_tab = ss.worksheet(result['tab'])
        target_tab.append_row(result['row'])
        st.success(f"✅ Successfully added to {result['tab']}!")
