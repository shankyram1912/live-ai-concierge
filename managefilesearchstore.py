"""
managefilesearchstore.py

Backend module to manage Gemini File Search stores for Concierge AI Agents.
"""

import os
import time
from urllib.parse import urlparse

from google.cloud import firestore
from google.cloud import storage
from google import genai
from google.genai import types

# Configurations
PROJECT_ID = "genai-e2e-demos"
DATABASE_ID = "live-concierge-ai"
TEMP_DIR = "./temp"

MIME_TYPE_MAPPING = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf"
}

# ----------------------------------------------------------------------------
# Initialization & Setup
# ----------------------------------------------------------------------------

def get_firestore_client():
    """Initializes and returns the Firestore client connected to the specific DB."""
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

def get_storage_client():
    """Initializes and returns the Cloud Storage client."""
    return storage.Client(project=PROJECT_ID)

def get_genai_client():
    """Initializes and returns the Google GenAI client using VM Service Account credentials."""
    # Relies entirely on the VM's Application Default Credentials (ADC)
    return genai.Client()

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _validate_file_type(file_path: str) -> str:
    """Validates the file extension against supported MIME types."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in MIME_TYPE_MAPPING:
        raise ValueError(
            f"Unsupported file extension: {ext}. "
            f"Allowed extensions are: {', '.join(MIME_TYPE_MAPPING.keys())}"
        )
    return MIME_TYPE_MAPPING[ext]

def _download_knowledge_file(gs_path: str, agent_name: str) -> str:
    """Downloads a file from a Google Cloud Storage gs:// URI to a local temp folder."""
    if not gs_path.startswith("gs://"):
        raise ValueError(f"Invalid storage path. Expected gs:// URI, got: {gs_path}")
        
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    parsed_uri = urlparse(gs_path)
    bucket_name = parsed_uri.netloc
    blob_name = parsed_uri.path.lstrip('/')
    
    local_file_path = os.path.join(TEMP_DIR, os.path.basename(blob_name))
    
    storage_client = get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    print(f"[{agent_name}] Downloading knowledge base from GCS...")
    blob.download_to_filename(local_file_path)
    print(f"[{agent_name}] File downloaded to: {local_file_path}")
    
    return local_file_path

# ----------------------------------------------------------------------------
# Modular Deletion and Creation Methods
# ----------------------------------------------------------------------------

def delete_agent_file_search_store(agent_name: str):
    """Checks if a File Search Store exists for the agent and deletes it."""
    client = get_genai_client()
    
    print(f"[{agent_name}] Checking for existing File Search Stores...")
    
    for store in client.file_search_stores.list():
        if store.display_name == agent_name:
            print(f"[{agent_name}] Found existing store '{store.name}'. Deleting...")
            # force=True also deletes all contained imported documents within the store
            client.file_search_stores.delete(name=store.name, config={'force': True})
            print(f"[{agent_name}] Successfully deleted old store.")

def build_agent_file_search_store(agent_name: str, local_file_path: str):
    """Creates the Multimodal File Search Store and imports the agent's file."""
    client = get_genai_client()
    _validate_file_type(local_file_path)  # Early validation before hitting API
    
    # 1. Upload file (File name will be visible in citations)
    print(f"[{agent_name}] Uploading file to Gemini...")
    sample_file = client.files.upload(
        file=local_file_path, 
        config={'name': f"{agent_name}_KnowledgeBase"}
    )
    print(f"[{agent_name}] File uploaded: {sample_file.name}")
    
    # 2. Create the File Search Store
    print(f"[{agent_name}] Creating File Search Store...")
    file_search_store = client.file_search_stores.create(
        config={
            'display_name': agent_name,
            'embedding_model': 'models/gemini-embedding-2'
        }
    )
    print(f"[{agent_name}] Store created successfully: {file_search_store.name}")
    
    # 3. Import the file into the store
    print(f"[{agent_name}] Importing file into the Store for embeddings indexing...")
    operation = client.file_search_stores.import_file(
        file_search_store_name=file_search_store.name,
        file_name=sample_file.name
    )
    
    # 4. Wait for operation to complete
    while not operation.done:
        print(f"[{agent_name}] Indexing in progress... waiting 5 seconds.")
        time.sleep(5)
        operation = client.operations.get(operation)
        
    print(f"[{agent_name}] Import operation completed successfully!")
    return file_search_store

# ----------------------------------------------------------------------------
# Main API Methods
# ----------------------------------------------------------------------------

def create_agent_file_search(agent_name: str):
    """
    Creates a Gemini File Search Store for the given agent from scratch.
    Validates against Firestore, downloads the file, and builds the store.
    """
    print(f"--- Starting File Search Creation for '{agent_name}' ---")
    
    db = get_firestore_client()
    doc_ref = db.collection('ai-agents').document(agent_name)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise Exception(f"Agent '{agent_name}' not found in database.")
        
    data = doc.to_dict()
    gs_path = data.get('knowledgeFilePath')
    
    if not gs_path:
        raise Exception(f"Agent '{agent_name}' has no knowledge file configured in Firestore.")
        
    local_file_path = _download_knowledge_file(gs_path, agent_name)
    store = build_agent_file_search_store(agent_name, local_file_path)
    
    print(f"--- Completed File Search Creation for '{agent_name}' ---")
    return store

def update_agent_file_search(agent_name: str):
    """
    Updates the File Search store for a given agent by completely 
    deleting the old one and re-creating it with the latest Firestore data.
    """
    print(f"--- Starting File Search Update for '{agent_name}' ---")
    
    db = get_firestore_client()
    doc_ref = db.collection('ai-agents').document(agent_name)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise Exception(f"Agent '{agent_name}' not found in database.")
        
    data = doc.to_dict()
    gs_path = data.get('knowledgeFilePath')
    
    if not gs_path:
        raise Exception(f"Agent '{agent_name}' has no knowledge file configured in Firestore.")
        
    local_file_path = _download_knowledge_file(gs_path, agent_name)
    
    # Purge existing before building new
    delete_agent_file_search_store(agent_name)
    store = build_agent_file_search_store(agent_name, local_file_path)
    
    print(f"--- Completed File Search Update for '{agent_name}' ---")
    return store