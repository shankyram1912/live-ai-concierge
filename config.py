import os
from tools import Tools
from dotenv import load_dotenv

# Model Configurations
ORCHESTRATOR_MODEL = "gemini-live-2.5-flash-native-audio"
SUBAGENT_LITE_MODEL = os.getenv("SUBAGENT_LITE_MODEL")
SUBAGENT_PRO_MODEL = os.getenv("SUBAGENT_PRO_MODEL")

# App Configuration
APP_NAME = "ai_concierge"