import os
from tools import Tools
from dotenv import load_dotenv

# Model Configurations
ORCHESTRATOR_MODEL = "gemini-live-2.5-flash-native-audio"
SUBAGENT_MODEL = os.getenv("SUBAGENT_MODEL")

# App Configuration
APP_NAME = "aris_smarthome_agent"