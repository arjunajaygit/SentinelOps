import logging
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

class CodebaseRetriever:
    def __init__(self, persist_directory: str):
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})

    def get_context_for_code(self, query: str) -> str:
        """
        Retrieves semantically similar code snippets from the codebase for a given query.
        Returns a formatted string containing the source files and their contents.
        """
        docs = self.retriever.invoke(query)
        if not docs:
            return "No relevant context found in the codebase."
            
        context_parts = []
        for doc in docs:
            source = doc.metadata.get('source', 'Unknown File')
            context_parts.append(f"--- Context from {source} ---\n{doc.page_content}")
            
        return "\n\n".join(context_parts)

    async def aget_context_for_code(self, query: str) -> str:
        """
        Asynchronously retrieves semantically similar code snippets.
        """
        docs = await self.retriever.ainvoke(query)
        if not docs:
            return "No relevant context found in the codebase."
            
        context_parts = []
        for doc in docs:
            source = doc.metadata.get('source', 'Unknown File')
            context_parts.append(f"--- Context from {source} ---\n{doc.page_content}")
            
        return "\n\n".join(context_parts)
