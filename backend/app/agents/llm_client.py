import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def call_gemini_json(system_prompt: str, user_input: str) -> dict:
    """Calls Gemini 2.5 Flash and forces it to return strict JSON."""
    # Configure at call time so the key is always read from the current env
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "dummy_key"))
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    try:
        response = model.generate_content(user_input)
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"message": "Sorry, my system glitched.", "items": [], "discount_pct": 0.0}
