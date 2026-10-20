import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
POLICY_DIR = DATA_DIR / "policies"
DB_PATH = DATA_DIR / "shopeasy.sqlite"
CHROMA_DIR = BASE_DIR / "chroma_db"

load_dotenv(BASE_DIR / ".env")

MODEL_NAME = "openai/gpt-oss-20b"
REFUND_THRESHOLD_USD = 50.00
MAX_AGENT_STEPS = 12
MAX_SUPERVISOR_HOPS = 8
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "SupportCopilot")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
