import os
from llm_layer.rag_pipeline import RAGPipeline

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ES_HOST = "http://localhost:9200"
INDEX_NAME = "github_projects"

pipeline = RAGPipeline(
    groq_api_key=GROQ_API_KEY,
    es_host=ES_HOST,
    index_name=INDEX_NAME,
)

question = "How many projects are there in the index?"
result = pipeline.ask(question)
print(result)
