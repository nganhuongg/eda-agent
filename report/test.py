import os
from openai import OpenAI
import openai

api_key = (os.getenv("GROQ_API_KEY") or "").strip()
base_url = (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").strip()
model = (os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant").strip()

print("openai version:", openai.__version__)
print("base_url:", repr(base_url))
print("model:", repr(model))
print("key prefix:", api_key[:8])
print("key length:", len(api_key))

client = OpenAI(api_key=api_key, base_url=base_url)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        temperature=0,
    )
    print("SUCCESS")
    print(response.choices[0].message.content)
except Exception as e:
    print("FAILED")
    print(type(e).__name__)
    print(str(e))