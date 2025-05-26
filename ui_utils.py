import streamlit as st
import plotly.express as px

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
