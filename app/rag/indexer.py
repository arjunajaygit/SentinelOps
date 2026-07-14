import os
import logging
from typing import Optional
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)

class CodebaseIndexer:
    def __init__(self, repo_path: str, persist_directory: Optional[str] = None):
        self.repo_path = repo_path
        # Store vector DB in the temp dir of the clone by default
        self.persist_directory = persist_directory or os.path.join(repo_path, ".chroma_db")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
    def index_repository(self) -> Chroma:
        """
        Walks through the cloned repository, chunks Python code, and indexes it into ChromaDB.
        """
        documents = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories like .git or .chroma_db
            dirs[:] = [d for d in dirs if not d.startswith('.')]
                
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        loader = TextLoader(file_path, encoding='utf-8')
                        docs = loader.load()
                        # Add relative path to metadata
                        rel_path = os.path.relpath(file_path, self.repo_path)
                        for doc in docs:
                            doc.metadata['source'] = rel_path
                        documents.extend(docs)
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")

        # Split documents using Python specific splitter
        python_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.PYTHON, 
            chunk_size=1000, 
            chunk_overlap=200
        )
        
        chunked_docs = python_splitter.split_documents(documents)
        logger.info(f"Indexing {len(chunked_docs)} chunks into ChromaDB at {self.persist_directory}.")
        
        vectorstore = Chroma.from_documents(
            documents=chunked_docs,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        
        # In newer Chroma/LangChain, persist is automatic on creation or handled by the client,
        # but we call it if available just in case.
        if hasattr(vectorstore, 'persist'):
            vectorstore.persist()
            
        return vectorstore
