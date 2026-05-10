import argparse
import logging

# Adjust this import to match the actual name of your Python file
# where delete_agent_cache is defined (e.g., if it's in cache_manager.py, use that)
from manage_context_cache import delete_agent_cache

# Set up basic logging if your main app's logger isn't initialized here
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    parser = argparse.ArgumentParser(
        description="Delete the Gemini Context Cache for a specific AI Concierge agent agent."
    )
    
    # Require the agent_name as a positional argument
    parser.add_argument(
        "agent_name", 
        type=str, 
        help="The name of the AI agent whose cache you want to delete."
    )
    
    args = parser.parse_args()
    
    print(f"Initiating cache cleanup for agent: '{args.agent_name}'...")
    
    # Call the function we built earlier
    delete_agent_cache(args.agent_name)
    
    print("Script execution completed.")

if __name__ == "__main__":
    main()