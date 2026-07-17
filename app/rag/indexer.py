import os
import logging
from typing import Optional, List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".rb": Language.RUBY,
    ".cpp": Language.CPP,
    ".c": Language.C,
    ".cs": Language.CSHARP,
    ".php": Language.PHP,
    ".scala": Language.SCALA,
    ".rs": Language.RUST,
}

class CodebaseIndexer:
    def __init__(self, repo_path: str, persist_directory: Optional[str] = None, diff_files: Optional[List[str]] = None):
        self.repo_path = repo_path
        self.persist_directory = persist_directory or os.path.join(repo_path, ".chroma_db")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.diff_files = diff_files or []
        
    def index_repository(self) -> Chroma:
        """
        Walks through the cloned repository, selectively indexes only the files changed in the PR,
        and uses language-aware syntactic chunking via Polyglot RAG.
        """
        documents = []
        
        # Timeout Guard: Instead of indexing the entire repo, only index modified files.
        for rel_path in self.diff_files:
            file_path = os.path.join(self.repo_path, rel_path)
            
            if not os.path.isfile(file_path):
                continue
                
            try:
                loader = TextLoader(file_path, encoding='utf-8')
                docs = loader.load()
                for doc in docs:
                    doc.metadata['source'] = rel_path
                
                # Dynamic Polyglot Code Splitting
                ext = os.path.splitext(file_path)[1].lower()
                if ext in LANGUAGE_MAP:
                    splitter = RecursiveCharacterTextSplitter.from_language(
                        language=LANGUAGE_MAP[ext],
                        chunk_size=1000,
                        chunk_overlap=200
                    )
                else:
                    # Fallback to standard text splitting for unknown extensions
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200
                    )
                    
                chunked_docs = splitter.split_documents(docs)
                documents.extend(chunked_docs)
                
            except Exception as e:
                logger.warning(f"Failed to load or chunk {file_path}: {e}")

        logger.info(f"Indexing {len(documents)} chunks from {len(self.diff_files)} changed files into ChromaDB.")
        
        # If no documents, we can just return a Chroma instance from an empty list or return early.
        # But Chroma.from_documents needs at least one document. 
        if not documents:
            logger.info("No documents to index. Returning empty VectorStore.")
            # Create an empty index by passing a dummy doc if needed, or better, use an empty Chroma directly
            # Wait, Chroma.from_documents will fail with empty list.
            vectorstore = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
        else:
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
        
        if hasattr(vectorstore, 'persist'):
            vectorstore.persist()
            
        return vectorstore
