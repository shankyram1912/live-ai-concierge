"""
test_use_context_cache.py

A script to test querying a Vertex AI Context Cache.
It dynamically finds the cache for a specific agent and asks it a question.
"""

import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
import config
import warnings
import os
import manage_context_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)   
logger = logging.getLogger(__name__)

# Suppress Pydantic serialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables first
load_dotenv(override=True)

def get_genai_client():
    """Initializes the Google GenAI client natively for Vertex AI."""
    return genai.Client()

def ask_agent_with_cache(agent_name: str, question: str) -> str:
    """
    Finds the active cache for the agent and generates a response.
    """
    client = get_genai_client()
    
    logger.info(f"[{agent_name}] Looking for active context cache...")
            
    if not manage_context_cache.check_agent_cache(agent_name):
        logger.info(f"No active context cache found for agent '{agent_name}'. Please run create_agent_cache() first.")
        manage_context_cache.create_agent_cache(agent_name)
        
    logger.info(f"[{agent_name}] Querying Gemini using Context Cache...")
    
    # Generate content using the cached context
    response = client.models.generate_content(
        model=config.SUBAGENT_MODEL, # Must match the model the cache was created with
        contents=question,
        config=types.GenerateContentConfig(
            cached_content=active_cache_name, # This links the prompt to the pre-loaded cache!
            temperature=0.2 # Lower temperature for more factual responses
        )
    )
    
    return response.text

if __name__ == "__main__":
    # Test Parameters
    test_agent = "FARAH"
    test_question = "What is the policy on dietary restrictions according to the guide?"
    
    print("="*60)
    print(f"Testing Agent: {test_agent}")
    print(f"Question: '{test_question}'")
    print("="*60)
    
    try:
        answer = ask_agent_with_cache(test_agent, test_question)
        print("\n🤖 AGENT RESPONSE:\n")
        print(answer)
        print("\n" + "="*60)
    except Exception as e:
        logger.error(f"Test Failed: {str(e)}")