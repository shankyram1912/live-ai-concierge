import os
from typing import Optional
import logging
from google.cloud import firestore
from google.adk.agents import LlmAgent

import config

logger = logging.getLogger(__name__)

# Configurations
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATABASE_ID = os.getenv("GOOGLE_CLOUD_FIRESTORE")
MODEL_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION_GLOBAL")

# ----------------------------------------------------------------------------
# Initialization & Setup
# ----------------------------------------------------------------------------

def get_firestore_client():
    """Initializes and returns the Firestore client connected to the specific DB."""
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

db = get_firestore_client()

# ==========================================
# Static Base Instructions
# ==========================================
BASE_TOOLS_AND_RULES = """

"""

# ==========================================
# Dynamic Agent Factory
# ==========================================
def get_concierge_agent(agent_name: str) -> LlmAgent:
    """
    Fetches agent configuration from Firestore and dynamically builds 
    an LlmAgent with injected prompts. Raises an exception if the agent is not found.
    """
    # Fetch agent config from Firestore (exceptions here will intentionally bubble up)
    doc_ref = db.collection("ai-agents").document(agent_name)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise ValueError(f"Agent '{agent_name}' not found in Firestore.")
        
    data = doc.to_dict()
    purpose = data.get("purpose", "")
    instructions = data.get("customerHandlingInstructions", "")
    knowledge_base = data.get("knowledgeBase", "")

    # Construct the final dynamic instruction string
    dynamic_instruction = f"""
      <purpose>
      {purpose}
      </purpose>

      <customer_handling_instructions>
      {instructions}
      </customer_handling_instructions>
      
      <knowledge_base>
      {knowledge_base}
      </knowledge_base>      

    {BASE_TOOLS_AND_RULES}
    """
    
    logger.info(f"Successfully loaded agent config for: {agent_name}\n {dynamic_instruction}")

    return LlmAgent(
        name=agent_name,
        model=config.ORCHESTRATOR_MODEL,
        instruction=dynamic_instruction,
        tools=[]  # Wrapper tools for subagents can be added here
    )