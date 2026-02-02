import streamlit as st
from llm_layer.rag_pipeline import RAGPipeline

from config import (
    ES_API_KEY,
    ES_HOST,
    ES_INDEX,
    ES_PASSWORD,
    ES_USERNAME,
    require_groq_api_key,
)

st.set_page_config(page_title="RAG Test", layout="centered")
st.title("🧪 RAG Quick Test")


@st.cache_resource
def load_pipeline():
    return RAGPipeline(
        groq_api_key=require_groq_api_key(),
        es_host=ES_HOST,
        es_username=ES_USERNAME,
        es_password=ES_PASSWORD,
        es_api_key=ES_API_KEY,
        index_name=ES_INDEX,
    )


try:
    require_groq_api_key()
except ValueError as e:
    st.error(str(e))
else:
    pipeline = load_pipeline()
    question = st.text_input("Ask a question about GitHub repos")
    if st.button("Ask"):
        if not question:
            st.warning("Enter a question")
        else:
            with st.spinner("Thinking..."):
                result = pipeline.ask(question, return_metadata=True)
                st.subheader("Answer")
                st.write(result["answer"])
