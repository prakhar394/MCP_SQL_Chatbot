import os
import sys
from dotenv import load_dotenv
import pandas as pd
from langchain_community.document_loaders.csv_loader import CSVLoader
from openai import AsyncOpenAI
import json
from typing import Any
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    # Fallback for older langchain versions
    try:
        from langchain.embeddings import HuggingFaceEmbeddings
    except ImportError:
        # If HuggingFaceEmbeddings is not available, use a simpler approach
        from langchain_community.embeddings import FakeEmbeddings
        HuggingFaceEmbeddings = None
from langchain_community.vectorstores import FAISS
import instructor
import asyncio
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Simplified format to only show the message
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("RAG")

# Load environment variables from a .env file
load_dotenv()
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# Get the absolute path to the data directory
data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
# path_parts = os.path.join(data_dir, "all_parts.csv")
path_repairs = os.path.join(data_dir, "all_repairs.csv")
path_blogs = os.path.join(data_dir, "partselect_blogs.csv")

def encode_csv(path, save_path):
    """
    Encodes a csv into a vector store using HuggingFace embeddings and saves it to disk.

    Args:
        path: The path to the csv file.
        save_path: The path where the vector store will be saved.

    Returns:
        A FAISS vector store containing the encoded book content.
    """
    import os
    
    # Check if the vector store already exists
    if os.path.exists(save_path):
        # Try to load the existing vector store
        if HuggingFaceEmbeddings is None:
            raise ImportError("HuggingFaceEmbeddings is not available. Please install sentence-transformers and compatible huggingface_hub.")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        try:
            vectorstore = FAISS.load_local(save_path, embeddings, allow_dangerous_deserialization=True)
            logger.info(f"Loaded existing vector store from {save_path}")
            return vectorstore
        except (AssertionError, ValueError, Exception) as e:
            # Vector store was created with different embeddings (likely OpenAI)
            logger.warning(f"Vector store at {save_path} was created with different embeddings (error: {type(e).__name__}). Regenerating with HuggingFace embeddings...")
            # Delete the old vector store files
            import shutil
            try:
                if os.path.isdir(save_path):
                    shutil.rmtree(save_path)
                    logger.info(f"Deleted directory: {save_path}")
                else:
                    # FAISS stores files as directory with index.faiss and index.pkl
                    # Or as separate .faiss and .pkl files
                    if os.path.exists(save_path):
                        if os.path.isdir(save_path):
                            shutil.rmtree(save_path)
                        else:
                            os.remove(save_path)
                    # Also check for .faiss and .pkl files in the same directory
                    base_dir = os.path.dirname(save_path) if os.path.dirname(save_path) else "."
                    base_name = os.path.basename(save_path)
                    for ext in [".faiss", ".pkl"]:
                        file_path = os.path.join(base_dir, base_name + ext)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted file: {file_path}")
            except Exception as del_error:
                logger.error(f"Error deleting old vector store: {del_error}")
            # Fall through to create new vector store
    
    # Load CSV documents
    loader = CSVLoader(file_path=path)
    docs = loader.load_and_split()

    # Create embeddings using HuggingFace (free, local)
    if HuggingFaceEmbeddings is None:
        raise ImportError("HuggingFaceEmbeddings is not available. Please install sentence-transformers and compatible huggingface_hub.")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )

    # Create vector store
    vectorstore = FAISS.from_documents(docs, embeddings)
    
    # Save the vector store to disk
    vectorstore.save_local(save_path)
    logger.info(f"Created and saved new vector store to {save_path}")
    
    return vectorstore

# Encode the csv files into vector stores
# Get the directory where this script is located for saving vector stores
rag_server_dir = os.path.dirname(os.path.abspath(__file__))

# parts_vector_store = encode_csv(path_parts, os.path.join(rag_server_dir, "parts_vector_store"))
repairs_vector_store = encode_csv(path_repairs, os.path.join(rag_server_dir, "repairs_vector_store"))
blogs_vector_store = encode_csv(path_blogs, os.path.join(rag_server_dir, "blogs_vector_store"))
# parts_query_retriever = parts_vector_store.as_retriever(search_kwargs={"k": 5})
repairs_query_retriever = repairs_vector_store.as_retriever(search_kwargs={"k": 5})
blogs_query_retriever = blogs_vector_store.as_retriever(search_kwargs={"k": 5})

# Define the tools
@mcp.tool()
async def searchRAG(table: str, query: str) -> list[str]:
    """Search one of the tables for the query using RAG.
    The tables are:
    - repairs
        - appliance: The appliance that the repair is for.
        - symptom: The symptom or issue that the repair is for.
        - parts: The parts that are needed to fix the issue.
        - url: The URL to the repair guide.
        - difficulty: The difficulty level of the repair.
    - blogs
        - title: The title of the blog post.
        - url: The URL to the blog post.
    Args:
        table: The table to search.
        query: The query to search the table for.
    """
    try:
        # Get documents from the appropriate retriever
        if table == "repairs":
            docs = repairs_query_retriever.invoke(query)
        elif table == "blogs":
            docs = blogs_query_retriever.invoke(query)
        else:
            raise ValueError(f"Invalid table: {table}")
            
        # Extract context from documents
        context = [doc.page_content for doc in docs]
        
        if not context:
            logger.warning("No documents found")
            return ["No relevant documents found."]
            
        # check document relevance with timeout
        class GradeDocuments(BaseModel):
            """Score for relevance check on retrieved documents."""
            confidence_score: float = Field(
                description="How confident are you that the document is relevant to the question? Give a score between 0 and 1. 0 is not relevant, 1 is very relevant."
            )

        relevant_docs = []
        confidence_scores = []
        
        for doc in context:
            try:
                # Set a timeout for the API call
                async with asyncio.timeout(10):  # 10 second timeout
                    response = await client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": """You are a helpful assistant that grades the relevance of documents to a question.
                                You must respond with a JSON object containing:
                                - "confidence_score": number between 0 and 1 (0 = not relevant, 1 = very relevant)
                                
                                Example response: {"confidence_score": 0.85}"""},
                            {"role": "user", "content": f"Question: {query}\nDocument: {doc}\n\nHow relevant is this document to the question? Return only valid JSON with confidence_score, no other text."},
                        ],
                        temperature=0.1
                    )
                    
                    # Parse JSON response
                    response_text = response.choices[0].message.content.strip()
                    # Remove markdown code blocks if present
                    if response_text.startswith("```json"):
                        response_text = response_text[7:]
                    if response_text.startswith("```"):
                        response_text = response_text[3:]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3]
                    response_text = response_text.strip()
                    
                    try:
                        result = GradeDocuments.model_validate_json(response_text)
                        confidence_scores.append(result.confidence_score)
                        if result.confidence_score > 0.5:
                            relevant_docs.append(doc)
                    except Exception as parse_error:
                        logger.warning(f"Failed to parse relevance score, defaulting to include document. Error: {parse_error}, Response: {response_text}")
                        # If parsing fails, include the document to be safe
                        relevant_docs.append(doc)
                        confidence_scores.append(0.6)  # Default confidence
                
            except asyncio.TimeoutError:
                logger.warning("Timeout checking document relevance")
                relevant_docs.append(doc)
                confidence_scores.append(0.6)  # Default confidence on timeout
            except Exception as e:
                logger.error(f"Error grading document: {type(e).__name__}: {str(e)}")
                # Include document on error to be safe
                relevant_docs.append(doc)
                confidence_scores.append(0.6)  # Default confidence
                
        # Log the summary of relevant documents and confidence scores
        logger.info(f"Found {len(relevant_docs)}/{len(context)} relevant documents")
        logger.info(f"Confidence scores: {[round(score, 2) for score in confidence_scores]}")
                
        if len(relevant_docs) == 0:
            return ["No relevant documents found."]
        else:
            return relevant_docs
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.error(f"Error in searchRAG: {error_msg}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return [f"Error searching {table}: {error_msg}"]

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')