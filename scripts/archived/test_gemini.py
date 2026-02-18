import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
loaded = load_dotenv()
print(f"load_dotenv() returned: {loaded}")

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
print(f"API key found: {api_key is not None}")
print(f"API key value: {api_key[:20] if api_key else 'None'}...")

if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env")
    exit(1)

# Configure Gemini
genai.configure(api_key=api_key)

print("\nTesting Gemini API...")
try:
    # Create a model instance
    model = genai.GenerativeModel('gemini-2.5-flash')

    # Generate content with a simple prompt
    response = model.generate_content("Say 'Hello from Gemini!' in a single sentence.")

    print("[SUCCESS] Gemini API is working!")
    print(f"   Response: {response.text}")

except Exception as e:
    print(f"[ERROR] Gemini API error: {type(e).__name__}")
    print(f"   {str(e)}")
    exit(1)
