import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import json
from datetime import datetime

# --- 1. SETUP ---
API_KEY = st.secrets["GEMINI_KEY"]
GOOGLE_CREDS = st.secrets["GOOGLE_CREDS"]

# Connect to Gemini 3 Brain (Interactions API)
client = genai.Client(api_key=API_KEY)

# Connect to Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS), scopes=scopes)
gc = gspread.authorize(creds)
ss = gc.open("My_AI_Finance_Manager")

st.set_page_config(page_title="AI Finance Assistant", page_icon="💰")
st.title("💰 AI Money Assistant")

if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

user_input = st.text_input("Enter details (e.g., '500,000 loan @ 9.5% for 7 years'):")

if st.button("🚀 Process & Calculate"):
    if user_input:
        system_msg = """
        You are a financial calculator. 
        If a user provides a loan amount, interest rate, and time, you MUST calculate the Monthly EMI.
        
        Formula: [P x R x (1+R)^N]/[(1+R)^N-1]
        
        Return ONLY JSON:
        {
          "tab": "Loans_and_Savings",
          "row": [LoanName, Principal, CurrentBalance, CalculatedEMI, Status_with_Interest_Rate]
        }
        """

        try:
            # Added thinking_summaries="auto" for better visibility [cite: 1168, 1179]
            interaction = client.interactions.create(
                model="gemini-3-flash-preview",
                input=user_input,
                system_instruction=system_msg,
                previous_interaction_id=st.session_state.interaction_id,
                generation_config={
                    "thinking_level": "high", # [cite: 1158]
                    "thinking_summaries": "auto", # [cite: 1169]
                    "temperature": 0.1
                }
            )
            
            st.session_state.interaction_id = interaction.id
            
            # Look for both reasoning summaries and text outputs [cite: 1182, 1183]
            for output in interaction.outputs:
                if output.type == "thought":
                    with st.expander("📝 AI Thinking Process"):
                        st.write(output.summary) # 
                
                elif output.type == "text":
                    response_text = output.text.strip()
                    if "{" in response_text and '"tab"' in response_text:
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        
                        result = json.loads(response_text)
                        ws = ss.worksheet(result['tab'])
                        # Always convert to string to prevent API Errors [cite: 46]
                        ws.append_row([str(x) for x in result['row']])
                        
                        st.success(f"✅ Calculation Complete & Saved to {result['tab']}!")
                        st.write(f"**Monthly EMI:** {result['row'][3]}")
                        st.balloons()
                    else:
                        st.info(f"🤖 AI: {response_text}")

        except Exception as e:
            st.error(f"❌ Error: {e}")

if st.button("🔄 Reset"):
    st.session_state.interaction_id = None
    st.rerun()
