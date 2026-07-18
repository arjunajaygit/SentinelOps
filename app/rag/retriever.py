import logging
from langchain_chroma import Chroma
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

class CodebaseRetriever:
    def __init__(self, persist_directory: str):
        self.persist_directory = persist_directory
        self.embeddings = get_embeddings()
        self.vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )

    def get_context_for_code(self, query: str, filename: str = None, dependent_files: list = None) -> str:
        """
        Retrieves semantically similar code snippets from the codebase for a given query.
        Returns a formatted string containing the source files and their contents.
        """
        if filename and dependent_files:
            filter_kwargs = {"source": {"$in": [filename] + dependent_files}}
        elif filename:
            filter_kwargs = {"source": filename}
        else:
            filter_kwargs = None
            
        docs = self.vectorstore.similarity_search(query, k=5, filter=filter_kwargs)
        if not docs:
            return "No relevant context found in the codebase."
            
        context_parts = []
        for doc in docs:
            source = doc.metadata.get('source', 'Unknown File')
            context_parts.append(f"--- Context from {source} ---\n{doc.page_content}")
            
        return "\n\n".join(context_parts)

    async def aget_context_for_code(self, query: str, filename: str = None, dependent_files: list = None) -> str:
        """
        Asynchronously retrieves semantically similar code snippets.
        """
        if filename and dependent_files:
            filter_kwargs = {"source": {"$in": [filename] + dependent_files}}
        elif filename:
            filter_kwargs = {"source": filename}
        else:
            filter_kwargs = None
            
        docs = await self.vectorstore.asimilarity_search(query, k=5, filter=filter_kwargs)
        if not docs:
            return "No relevant context found in the codebase."
            
        context_parts = []
        for doc in docs:
            source = doc.metadata.get('source', 'Unknown File')
            context_parts.append(f"--- Context from {source} ---\n{doc.page_content}")
            
        return "\n\n".join(context_parts)
