import os
import streamlit as st

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
DB_PATH = "stake_cleaned_dataset.db"
