# """
# Streamlit Frontend for GitHub Repository RAG System
# Interactive web interface for asking questions about GitHub repositories.
# """

# import os
# import sys
# import json
# import streamlit as st
# from datetime import datetime
# from pathlib import Path

# # Add parent directory to path for imports
# sys.path.insert(0, str(Path(__file__).parent))

# from llm_layer.rag_pipeline import RAGPipeline
# from data_processing import ElasticsearchClient


# # Page configuration
# st.set_page_config(
#     page_title="GitHub Repository Q&A",
#     page_icon="🔍",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# # Custom CSS
# st.markdown("""
# <style>
#     .main-header {
#         font-size: 3rem;
#         font-weight: bold;
#         text-align: center;
#         margin-bottom: 1rem;
#         background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
#         -webkit-background-clip: text;
#         -webkit-text-fill-color: transparent;
#     }
#     .sub-header {
#         text-align: center;
#         color: #666;
#         margin-bottom: 2rem;
#     }
#     .question-box {
#         background-color: #f0f2f6;
#         padding: 1rem;
#         border-radius: 0.5rem;
#         margin: 1rem 0;
#     }
#     .answer-box {
#         background-color: #e8f4f8;
#         padding: 1.5rem;
#         border-radius: 0.5rem;
#         border-left: 4px solid #667eea;
#         margin: 1rem 0;
#     }
#     .source-card {
#         background-color: #ffffff;
#         padding: 1rem;
#         border-radius: 0.5rem;
#         border: 1px solid #e0e0e0;
#         margin: 0.5rem 0;
#     }
#     .stat-card {
#         background-color: #f8f9fa;
#         padding: 1rem;
#         border-radius: 0.5rem;
#         text-align: center;
#     }
#     .stButton>button {
#         width: 100%;
#         background-color: #667eea;
#         color: white;
#     }
# </style>
# """, unsafe_allow_html=True)


# def initialize_session_state():
#     """Initialize session state variables."""
#     if "pipeline" not in st.session_state:
#         st.session_state.pipeline = None
#     if "conversation_history" not in st.session_state:
#         st.session_state.conversation_history = []
#     if "es_stats" not in st.session_state:
#         st.session_state.es_stats = None
#     if "initialized" not in st.session_state:
#         st.session_state.initialized = False


# def get_es_stats(es_host, es_username=None, es_password=None, es_api_key=None, index_name="github_projects"):
#     """Get Elasticsearch index statistics."""
#     try:
#         es_client = ElasticsearchClient(
#             hosts=es_host,
#             username=es_username,
#             password=es_password,
#             api_key=es_api_key,
#         )
        
#         # Get total documents
#         total_docs = es_client.count_documents(index_name)
        
#         # Get index info
#         index_info = es_client.client.indices.stats(index=index_name)
#         index_size = index_info['indices'][index_name]['total']['store']['size_in_bytes']
        
#         es_client.close()
        
#         return {
#             "total_projects": total_docs,
#             "index_size_mb": round(index_size / (1024 * 1024), 2),
#             "status": "connected"
#         }
#     except Exception as e:
#         return {
#             "total_projects": 0,
#             "index_size_mb": 0,
#             "status": f"error: {str(e)}"
#         }


# def initialize_pipeline(groq_api_key, es_host, es_username, es_password, es_api_key, index_name):
#     """Initialize the RAG pipeline."""
#     try:
#         with st.spinner("🔄 Initializing RAG pipeline..."):
#             pipeline = RAGPipeline(
#                 groq_api_key=groq_api_key,
#                 es_host=es_host,
#                 es_username=es_username,
#                 es_password=es_password,
#                 es_api_key=es_api_key,
#                 index_name=index_name,
#             )
#             st.session_state.pipeline = pipeline
#             st.session_state.initialized = True
            
#             # Get ES stats
#             st.session_state.es_stats = get_es_stats(
#                 es_host, es_username, es_password, es_api_key, index_name
#             )
            
#             st.success("✅ Pipeline initialized successfully!")
#             return True
#     except Exception as e:
#         st.error(f"❌ Failed to initialize pipeline: {str(e)}")
#         return False


# def display_source_card(source, index):
#     """Display a source card with project information."""
#     with st.container():
#         col1, col2 = st.columns([3, 1])
        
#         with col1:
#             st.markdown(f"### {index}. [{source['full_name']}]({source['url']})")
#             if source['description']:
#                 st.markdown(f"*{source['description']}*")
        
#         with col2:
#             if source['stars'] is not None:
#                 st.metric("⭐ Stars", f"{source['stars']:,}")
        
#         # Additional info in expandable section
#         with st.expander("More details"):
#             cols = st.columns(3)
#             with cols[0]:
#                 if source['language']:
#                     st.markdown(f"**Language:** {source['language']}")
#             with cols[1]:
#                 st.markdown(f"**Name:** {source['name']}")
#             with cols[2]:
#                 if source['url']:
#                     st.markdown(f"[🔗 View on GitHub]({source['url']})")


# def display_conversation_history():
#     """Display conversation history."""
#     if st.session_state.conversation_history:
#         st.markdown("### 📜 Conversation History")
#         for i, item in enumerate(reversed(st.session_state.conversation_history[-5:])):
#             with st.expander(f"Q: {item['question'][:50]}..." if len(item['question']) > 50 else f"Q: {item['question']}", expanded=(i==0)):
#                 st.markdown(f"**Question:** {item['question']}")
#                 st.markdown(f"**Time:** {item['timestamp']}")
#                 st.markdown("**Answer:**")
#                 st.markdown(item['answer'])
#                 if item.get('sources'):
#                     st.markdown(f"*{len(item['sources'])} sources used*")


# def sidebar_config():
#     """Sidebar configuration and settings."""
#     with st.sidebar:
#         st.markdown("## ⚙️ Configuration")
        
#         # API Keys
#         st.markdown("### 🔑 API Keys")
#         groq_api_key = st.text_input(
#             "Groq API Key",
#             type="password",
#             value=os.environ.get("GROQ_API_KEY", ""),
#             help="Get your key from https://console.groq.com"
#         )
        
#         # Elasticsearch Settings
#         st.markdown("### 🔍 Elasticsearch Settings")
#         es_host = st.text_input(
#             "ES Host",
#             value=os.environ.get("ES_HOST", "http://localhost:9200"),
#             help="Elasticsearch host URL"
#         )
        
#         index_name = st.text_input(
#             "Index Name",
#             value=os.environ.get("ES_INDEX", "github_projects"),
#             help="Name of the Elasticsearch index"
#         )
        
#         # Optional ES auth
#         with st.expander("🔐 ES Authentication (Optional)"):
#             es_auth_type = st.radio("Auth Type", ["None", "API Key", "Username/Password"])
            
#             es_api_key = None
#             es_username = None
#             es_password = None
            
#             if es_auth_type == "API Key":
#                 es_api_key = st.text_input("ES API Key", type="password", value=os.environ.get("ES_API_KEY", ""))
#             elif es_auth_type == "Username/Password":
#                 es_username = st.text_input("ES Username", value=os.environ.get("ES_USERNAME", ""))
#                 es_password = st.text_input("ES Password", type="password", value=os.environ.get("ES_PASSWORD", ""))
        
#         # Model Settings
#         st.markdown("### 🤖 Model Settings")
#         query_model = st.selectbox(
#             "Query Model",
#             ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
#             help="Model for query generation"
#         )
        
#         answer_model = st.selectbox(
#             "Answer Model",
#             ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
#             help="Model for answer generation"
#         )
        
#         max_results = st.slider("Max Results", 1, 20, 5, help="Maximum number of search results")
#         include_commits = st.checkbox("Include Commits", value=False, help="Include commit information in answers")
        
#         # Initialize button
#         st.markdown("---")
#         if st.button("🚀 Initialize Pipeline", type="primary"):
#             if not groq_api_key:
#                 st.error("❌ Please provide Groq API Key")
#             else:
#                 initialize_pipeline(groq_api_key, es_host, es_username, es_password, es_api_key, index_name)
        
#         # Status
#         if st.session_state.initialized:
#             st.success("✅ Pipeline Ready")
#             if st.session_state.es_stats:
#                 st.markdown("### 📊 Index Stats")
#                 st.metric("Total Projects", st.session_state.es_stats['total_projects'])
#                 st.metric("Index Size", f"{st.session_state.es_stats['index_size_mb']} MB")
#         else:
#             st.warning("⚠️ Pipeline not initialized")
        
#         # Actions
#         st.markdown("---")
#         st.markdown("### 🔧 Actions")
        
#         if st.button("🗑️ Clear History"):
#             st.session_state.conversation_history = []
#             st.rerun()
        
#         if st.button("📥 Export Conversation"):
#             if st.session_state.conversation_history:
#                 export_data = json.dumps(st.session_state.conversation_history, indent=2)
#                 st.download_button(
#                     "Download JSON",
#                     export_data,
#                     file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
#                     mime="application/json"
#                 )
#             else:
#                 st.info("No conversation to export")
        
#         return {
#             "groq_api_key": groq_api_key,
#             "es_host": es_host,
#             "es_username": es_username,
#             "es_password": es_password,
#             "es_api_key": es_api_key,
#             "index_name": index_name,
#             "query_model": query_model,
#             "answer_model": answer_model,
#             "max_results": max_results,
#             "include_commits": include_commits,
#         }


# def main():
#     """Main application."""
#     initialize_session_state()
    
#     # Header
#     st.markdown('<div class="main-header">🔍 GitHub Repository Q&A</div>', unsafe_allow_html=True)
#     st.markdown(
#         '<div class="sub-header">Ask questions about GitHub projects powered by AI</div>',
#         unsafe_allow_html=True
#     )
    
#     # Sidebar configuration
#     config = sidebar_config()
    
#     # Main content
#     if not st.session_state.initialized:
#         # Welcome screen
#         st.markdown("## 👋 Welcome!")
#         st.markdown("""
#         This is an AI-powered search engine for GitHub repositories. 
        
#         **To get started:**
#         1. Enter your **Groq API Key** in the sidebar (get one from [console.groq.com](https://console.groq.com))
#         2. Configure Elasticsearch settings if needed
#         3. Click **Initialize Pipeline**
#         4. Start asking questions!
        
#         **Example questions:**
#         - What are the most popular Python projects?
#         - Find JavaScript web frameworks with more than 1000 stars
#         - Show me machine learning repositories
#         - Find projects with recent bug fix commits
#         """)
        
#         # Sample questions
#         st.markdown("### 💡 Try these questions:")
#         col1, col2 = st.columns(2)
#         with col1:
#             st.info("🐍 What are popular Python machine learning projects?")
#             st.info("🌐 Find JavaScript web development frameworks")
#         with col2:
#             st.info("🤖 Show me AI and deep learning repositories")
#             st.info("⚡ What are trending TypeScript projects?")
    
#     else:
#         # Question input
#         st.markdown("## 💬 Ask a Question")
        
#         # Predefined questions
#         col1, col2, col3 = st.columns(3)
#         with col1:
#             if st.button("🐍 Popular Python Projects"):
#                 st.session_state.current_question = "What are the most popular Python projects?"
#         with col2:
#             if st.button("🌐 Web Frameworks"):
#                 st.session_state.current_question = "Find popular web development frameworks"
#         with col3:
#             if st.button("🤖 ML Repositories"):
#                 st.session_state.current_question = "Show me machine learning repositories"
        
#         # Text input
#         question = st.text_input(
#             "Your Question:",
#             value=st.session_state.get("current_question", ""),
#             placeholder="e.g., What are the most starred Python projects?",
#             key="question_input"
#         )
        
#         # Ask button
#         col1, col2, col3 = st.columns([2, 1, 2])
#         with col2:
#             ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)
        
#         # Process question
#         if ask_button and question:
#             with st.spinner("🤔 Thinking..."):
#                 try:
#                     # Get answer
#                     result = st.session_state.pipeline.ask(
#                         question=question,
#                         max_results=config["max_results"],
#                         include_commits=config["include_commits"],
#                         return_metadata=True,
#                     )
                    
#                     # Display answer
#                     st.markdown("## 💡 Answer")
#                     st.markdown(f'<div class="answer-box">{result["answer"]}</div>', unsafe_allow_html=True)
                    
#                     # Display metadata
#                     col1, col2, col3 = st.columns(3)
#                     with col1:
#                         st.metric("📊 Total Results", result["total_results"])
#                     with col2:
#                         st.metric("📄 Results Shown", result["results_shown"])
#                     with col3:
#                         st.metric("🔗 Sources", len(result["sources"]))
                    
#                     # Display sources
#                     if result["sources"]:
#                         st.markdown("## 📚 Sources")
#                         for i, source in enumerate(result["sources"], 1):
#                             display_source_card(source, i)
                    
#                     # Add to history
#                     st.session_state.conversation_history.append({
#                         "question": question,
#                         "answer": result["answer"],
#                         "sources": result["sources"],
#                         "total_results": result["total_results"],
#                         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                     })
                    
#                     # Clear current question
#                     if "current_question" in st.session_state:
#                         del st.session_state.current_question
                    
#                 except Exception as e:
#                     st.error(f"❌ Error: {str(e)}")
#                     st.exception(e)
        
#         elif ask_button and not question:
#             st.warning("⚠️ Please enter a question")
        
#         # Conversation history
#         if st.session_state.conversation_history:
#             st.markdown("---")
#             display_conversation_history()


# if __name__ == "__main__":
#     main()

import streamlit as st
from llm_layer.rag_pipeline import RAGPipeline

st.set_page_config(page_title="RAG Test", layout="centered")

st.title("🧪 RAG Quick Test")

# --- Config (hardcoded or env-based) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ES_HOST = "http://localhost:9200"
INDEX_NAME = "github_projects"

# --- Initialize pipeline once ---
@st.cache_resource
def load_pipeline():
    return RAGPipeline(
        groq_api_key=GROQ_API_KEY,
        es_host=ES_HOST,
        index_name=INDEX_NAME,
    )

pipeline = load_pipeline()

# --- UI ---
question = st.text_input("Ask a question about GitHub repos")

if st.button("Ask"):
    if not question:
        st.warning("Enter a question")
    else:
        with st.spinner("Thinking..."):
            result = pipeline.ask(question)
            st.subheader("Answer")
            st.write(result["answer"])
