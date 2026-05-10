"""
manage_context_cache.py

Backend module to manage Vertex AI Context Caches for Concierge AI Agents.
"""

import os
import logging
from google.cloud import firestore
from google import genai
from google.genai import types
import config
import datetime

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Configurations
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATABASE_ID = os.getenv("GOOGLE_CLOUD_FIRESTORE")
MODEL_LOCATION = os.getenv("SUBAGENT_GOOGLE_CLOUD_LOCATION")

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

def get_genai_client():
    """Initializes the Google GenAI client natively for Vertex AI."""
    # Relies entirely on the VM's Application Default Credentials (ADC)
    return genai.Client(location=MODEL_LOCATION)

def _get_mime_type(gs_path: str) -> str:
    """Validates and infers the MIME type directly from the Cloud Storage URI."""
    ext = os.path.splitext(gs_path)[1].lower()
    if ext not in MIME_TYPE_MAPPING:
        raise ValueError(
            f"Unsupported file extension: {ext}. "
            f"Allowed extensions are: {', '.join(MIME_TYPE_MAPPING.keys())}"
        )
    return MIME_TYPE_MAPPING[ext]

# ----------------------------------------------------------------------------
# Core Context Caching Methods (Matches Vertex Docs)
# ----------------------------------------------------------------------------

def build_agent_cache(agent_name: str, gs_path: str, purpose: str, instructions: str):
    """Creates a Context Cache combining the GCS document and System Instructions."""
    client = get_genai_client()
    mime_type = _get_mime_type(gs_path)
    
    logger.info(f"[{agent_name}] Preparing document directly from Cloud Storage: {gs_path}")
    
    # Vertex AI reads directly from the bucket; NO LOCAL DOWNLOAD REQUIRED!
    document_part = types.Part.from_uri(
        file_uri=gs_path,
        mime_type=mime_type
    )
    
    full_system_instruction = f"Purpose: {purpose}\n\nInstructions: {instructions}"
    
    logger.info(f"[{agent_name}] Creating Context Cache on Vertex AI...")
    
    # Create a timezone-aware datetime for Dec 31, 2050
    cache_expiration = datetime.datetime(2050, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    
    # Context Caching uses specific models (like gemini-3-flash-preview)
    cached_content = client.caches.create(
        model=config.SUBAGENT_MODEL,
        config=types.CreateCachedContentConfig(
            contents=[document_part],
            system_instruction=full_system_instruction,
            display_name=agent_name,
            expire_time=cache_expiration
        )
    )
    
    logger.info(f"[{agent_name}] Cache created successfully: {cached_content.name}, expiring at {cached_content.expire_time}.")
    return cached_content

# ----------------------------------------------------------------------------
# Main Orchestration Methods
# ----------------------------------------------------------------------------

def create_agent_cache(agent_name: str):
    """
    Creates a Gemini Context Cache for the given agent from scratch.
    Validates against Firestore, grabs the GS URI and instructions, and builds it.
    """
    logger.info(f"--- Starting Context Cache Creation for '{agent_name}' ---")
    
    db = get_firestore_client()
    doc_ref = db.collection('ai-agents').document(agent_name)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise Exception(f"Agent '{agent_name}' not found in database.")
        
    data = doc.to_dict()
    gs_path = data.get('knowledgeFilePath')
    purpose = data.get('agentPurpose', '')
    instructions = data.get('customerHandlingInstructions', '')
    
    if not gs_path:
        raise Exception(f"Agent '{agent_name}' has no knowledge file configured in Firestore.")
        
    # Delete any stale cache just in case
    delete_agent_cache(agent_name)
    
    # Build the new cache
    store = build_agent_cache(agent_name, gs_path, purpose, instructions)
    
    logger.info(f"--- Completed Context Cache Creation for '{agent_name}' ---")
    return store

def update_agent_cache(agent_name: str):
    """
    Updates the Context Cache for a given agent. 
    Because you cannot modify the contents of a cache once created, 
    this completely deletes the old one and re-creates it with the latest Firestore data.
    """
    logger.info(f"--- Starting Context Cache Update for '{agent_name}' ---")
    
    # For content changes, a full recreate is required, so we just wrap the create function
    store = create_agent_cache(agent_name)
    
    logger.info(f"--- Completed Context Cache Update for '{agent_name}' ---")
    return store

def delete_agent_cache(agent_name: str):
    """Checks if a Context Cache exists for the agent and deletes it."""
    client = get_genai_client()
    
    logger.info(f"[{agent_name}] Checking for existing Context Caches...")
    
    # List and delete matching caches
    for cache in client.caches.list():
        if cache.display_name == agent_name:
            logger.info(f"[{agent_name}] Found existing cache '{cache.name}'. Deleting...")
            client.caches.delete(name=cache.name)
            logger.info(f"[{agent_name}] Successfully deleted old cache.")
            
def check_agent_cache(agent_name: str) -> bool:
    """Checks if a Context Cache exists for the agent."""
    client = get_genai_client()
    
    logger.info(f"[{agent_name}] Checking for existing Context Caches...")
    
    # List caches and return True if a match is found
    for cache in client.caches.list():
        if cache.display_name == agent_name:
            logger.info(f"[{agent_name}] Found existing cache '{cache.name}'.")
            return True
            
    logger.info(f"[{agent_name}] No existing cache found.")
    return False            