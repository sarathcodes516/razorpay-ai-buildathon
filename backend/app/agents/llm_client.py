import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def call_gemini_json(system_prompt: str, user_input: str, retries: int = 1) -> dict:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "dummy_key"))
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash-lite",
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    attempt = 0
    current_input = user_input
    
    while attempt <= retries:
        try:
            response = model.generate_content(current_input)
            raw = response.text.strip()
            # Strip markdown code fences if model wraps output in ```json ... ```
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error on attempt {attempt}: {e}")
            print(f"Raw response was: {response.text[:300]}")
            current_input = f"{user_input}\n\nSYSTEM WARNING: Your previous response was not valid JSON. You MUST return ONLY a raw JSON object, no markdown, no code fences."
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
