from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Get the API key from environment
api_key = os.getenv("GEMINI_API_KEY")

# Set up the Gemini-compatible client
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)