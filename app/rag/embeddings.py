import logging
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

_embeddings_instance = None

def get_embeddings():
    """
    Returns a singleton instance of the HuggingFaceEmbeddings.
    This prevents loading the heavy SentenceTransformer model multiple times per run.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info("Initializing HuggingFaceEmbeddings singleton...")
        _embeddings_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_instance
