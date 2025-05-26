import re
import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def is_sql(text):
    return text.strip().lower().startswith(("select", "with", "insert", "update", "delete"))

def sanitize_sql(sql_code):
    conflict_names = {
        "trades": "cte_trades",
        "transactions": "cte_transactions",
        "revenue": "cte_revenue",
        "website_events": "cte_events",
        "obt_user": "cte_users",
        "withdrawals": "cte_withdrawals",
        "fundings": "cte_fundings"
    }

    declared_ctes = []

    def rename_cte(match):
        cte_name = match.group(1)
        new_name = conflict_names.get(cte_name.lower(), f"cte_{cte_name}")
        declared_ctes.append((cte_name, new_name))
        return match.group(0).replace(cte_name, new_name, 1)

    sql_code = re.sub(r"\bWITH\s+(\w+)\s+AS\s+\(", rename_cte, sql_code, flags=re.IGNORECASE)
    sql_code = re.sub(r"\b,\s*(\w+)\s+AS\s+\(", rename_cte, sql_code, flags=re.IGNORECASE)

    for old_name, new_name in declared_ctes:
        if old_name != new_name:
            sql_code = re.sub(rf"\b{old_name}\b", new_name, sql_code, flags=re.IGNORECASE)

    return sql_code

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
- ❗ Do NOT name CTEs the same as table names (e.g., avoid trades, transactions, etc.)
- Do not reference columns that don’t exist, such as ue.user_id (use ue.identifier_user instead)
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
