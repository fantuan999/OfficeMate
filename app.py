import streamlit as st

st.set_page_config(
    page_title="OfficeMate",
    page_icon="🏢",
    layout="wide",
)

pg = st.navigation([
    st.Page("pages/qa.py",       title="QA",    icon="💬", default=True),
    st.Page("pages/upload.py",   title="知识上传", icon="📤"),
    st.Page("pages/manage.py",   title="知识管理", icon="📚"),
])
pg.run()
