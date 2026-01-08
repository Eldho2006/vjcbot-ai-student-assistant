
import os
import sys
from dotenv import load_dotenv

# Force UTF-8 for Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Load env vars BEFORE importing module that uses them at top-level
load_dotenv()

from ai_engine import ai_engine

print("--- TEST 1: LOCAL KNOWLEDGE BASE ---")
query_local = "What does BLTU stand for?"
print(f"Query: {query_local}")
try:
    answer = ai_engine.get_answer(query_local)
    print(f"Result:\n{answer}\n")
except Exception as e:
    print(f"Error: {e}\n")

print("-" * 30)

print("--- TEST 2: WEB SEARCH ---")
query_web = "What is the current stock price of Google?"
print(f"Query: {query_web}")
try:
    answer = ai_engine.get_answer(query_web)
    print(f"Result:\n{answer}\n")
except Exception as e:
    print(f"Error: {e}\n")
