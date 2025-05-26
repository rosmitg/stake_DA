import streamlit as st
import sqlite3
import pandas as pd
from config import DB_PATH
from sql_utils import ask_llm, sanitize_sql, is_sql
from ui_utils import suggest_visualization

# --- Streamlit setup ---
st.set_page_config(page_title="AskStake AI", layout="wide")
st.title("💬 AskStake — Hybrid LLM-Powered Data Assistant")

# --- Connect to DB ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# --- Chat history ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Input box ---
user_input = st.chat_input("Ask about revenue, trades, users, or just chat...")

if user_input:
    llm_response = ask_llm(user_input)
    llm_response = llm_response.replace("```sql", "").replace("```", "").strip()
    is_query = is_sql(llm_response)

    if is_query:
        llm_response = sanitize_sql(llm_response)
        try:
            result_df = pd.read_sql_query(llm_response, conn)
            st.session_state.history.append((user_input, llm_response, result_df))
        except Exception as e:
            hint = ""
            if "circular reference" in str(e).lower():
                hint = "⚠️ This may be caused by naming a CTE the same as a table. Try renaming the CTE."
            st.session_state.history.append((user_input, llm_response, f"❌ SQL Error: {str(e)}\n{hint}"))
    else:
        st.session_state.history.append((user_input, None, llm_response))

# --- Display chat history ---
for idx, (user_q, sql_q, result) in enumerate(reversed(st.session_state.history)):
    st.markdown(f"**You:** {user_q}")
    if sql_q:
        st.code(sql_q, language="sql")
    if isinstance(result, pd.DataFrame):
        st.dataframe(result)
        if not result.empty and result.shape[1] >= 2:
            suggest_visualization(result, key_prefix=f"viz_{idx}")
    else:
        st.markdown(result)
