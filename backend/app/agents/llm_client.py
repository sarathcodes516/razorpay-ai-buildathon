import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def call_gemini_json(system_prompt: str, user_input: str, retries: int = 1) -> dict:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "dummy_key"))
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    attempt = 0
    current_input = user_input
    
    while attempt <= retries:
        try:
            response = model.generate_content(current_input)
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error on attempt {attempt}: {e}")
            current_input = f"{user_input}\n\nSYSTEM WARNING: Your previous response was not valid JSON. You MUST return ONLY valid JSON."
            attempt += 1
        except Exception as e:
            print(f"LLM Error: {e}")
            break
            
    # Safe Fallback if LLM repeatedly fails
    return {
        "message": "I'm experiencing a slight glitch in my system. Let me escalate this to a human concierge for you.",
        "items": [],
        "discount_pct": 0.0
    }
