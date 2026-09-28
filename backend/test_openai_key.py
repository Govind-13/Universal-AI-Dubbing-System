"""
Quick test to verify that the OpenAI API key is valid.
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[FAIL] OPENAI_API_KEY not found in .env file!")
    exit(1)

print(f"[OK] API key loaded (starts with: {api_key[:20]}...)")

# Test: Simple ChatOpenAI call via LangChain (same as translation_service uses)
print("\n--- Test: LangChain ChatOpenAI (translation) ---")
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    chat = ChatOpenAI(temperature=0, openai_api_key=api_key, max_tokens=50)
    response = chat.invoke([HumanMessage(content="Say 'Hello, the API key is working!' in one sentence.")])
    print(f"[OK] Response: {response.content}")
except Exception as e:
    print(f"[FAIL] ChatOpenAI failed: {e}")

print("\n--- Done ---")
