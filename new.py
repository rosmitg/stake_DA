# ask_stake_chatbot.py (Improved Hybrid Mode with Visuals, Error Handling, Safe Prompts)
import streamlit as st
import openai
import sqlite3
import pandas as pd
import plotly.express as px
import re

# --- Streamlit setup ---
st.set_page_config(page_title="AskStake AI", layout="wide")
st.title("💬 AskStake — Hybrid LLM-Powered Data Assistant")

# --- OpenAI setup ---
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- Connect to DB ---
conn = sqlite3.connect("stake_cleaned_dataset.db", check_same_thread=False)

# --- Chat history ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Detect SQL query ---
def is_sql(text):
    return text.strip().lower().startswith(("select", "with", "insert", "update", "delete"))

# --- Visualize DataFrame ---
def suggest_visualization(df, key_prefix=""):
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    non_numeric_cols = df.select_dtypes(exclude='number').columns.tolist()
    if not numeric_cols or not non_numeric_cols:
        return
    with st.expander("📊 Visualize this result"):
        chart_type = st.selectbox("Select chart type", ["Bar", "Line", "Pie"], key=key_prefix + "_chart")
        x_col = st.selectbox("X-axis", non_numeric_cols, key=key_prefix + "_x")
        y_col = st.selectbox("Y-axis", numeric_cols, key=key_prefix + "_y")
        if chart_type == "Bar":
            fig = px.bar(df, x=x_col, y=y_col)
        elif chart_type == "Line":
            fig = px.line(df, x=x_col, y=y_col)
        elif chart_type == "Pie":
            fig = px.pie(df, names=x_col, values=y_col)
        st.plotly_chart(fig, use_container_width=True)

# --- Sanitize SQL to avoid CTE/table conflicts ---
def sanitize_sql(sql_code):
    real_tables = {
        "trades", "transactions", "revenue", "website_events", "obt_user",
        "withdrawals", "fundings"
    }
    declared_ctes = []

    def rename_cte(match):
        cte_name = match.group(1)
        safe_name = f"cte_{cte_name}"
        declared_ctes.append((cte_name, safe_name))
        return match.group(0).replace(cte_name, safe_name, 1)

    sql_code = re.sub(r"\bWITH\s+(\w+)\s+AS\s+\(", rename_cte, sql_code, flags=re.IGNORECASE)
    sql_code = re.sub(r",\s*(\w+)\s+AS\s+\(", rename_cte, sql_code, flags=re.IGNORECASE)

    for original, new in declared_ctes:
        if original != new:
            sql_code = re.sub(rf"\b{original}\b", new, sql_code, flags=re.IGNORECASE)

    return sql_code

# --- LLM Function ---
def ask_llm(question):
    prompt = f"""
You are a SQL assistant for Stake's internal analytics tool. Respond with only valid SQLite SQL queries unless the question is not data-related.

Schema and Notes:
- Table: transactions(user_id, transaction_type, inserted_at, status, updated_at, amount, currency, product)
- Table: website_events(event_id, event_name, data_origin, timestamp, custom_data, identifier_user)
- Table: trades(user_id, placed_at, status, updated_at, amount, currency, product, quantity, ticker)
- Table: revenue(user_id, month, year, revenue_type, amount, currency)
- Table: stake_user_metrics(user_id, month, year, metric_1, metric_2, metric_3)
- Table: obt_user(user_id, status, customer_since, is_referral, approved_since, account_status)
- Table: withdrawals(user_id, inserted_at, status, updated_at, amount, currency, product)
- Table: fundings(user_id, inserted_at, status, updated_at, amount, currency, product)

Important:
- SQLite is case-sensitive. Column values are UPPERCASE where applicable, e.g.,
    - transaction_type: 'DEPOSIT', 'WITHDRAWAL'
    - status: 'COMPLETED', 'PENDING', 'REJECTED'
    - event_name: 'SIGNUP', 'OPEN'
- Join obt_user.user_id with website_events.identifier_user
- ❗ Do NOT name CTEs the same as table names (e.g., avoid `trades`, `transactions`, etc.)
- Do not reference columns that don’t exist, such as `ue.user_id` (use `ue.identifier_user` instead)
- Return only SQL — no explanation or markdown code blocks.

Example:
SELECT user_id,
    SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN amount ELSE 0 END) AS total_deposits,
    SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount ELSE 0 END) AS total_withdrawals
FROM transactions
GROUP BY user_id;

User asked: {question}
SQL:
"""
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content.strip()

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

        # ✅ Download button for CSV
        csv = result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download result as CSV",
            data=csv,
            file_name=f"stake_query_result_{idx}.csv",
            mime='text/csv'
        )

        if not result.empty and result.shape[1] >= 2:
            suggest_visualization(result, key_prefix=f"viz_{idx}")
    else:
        st.markdown(result)
