import sys
import json
import re
from google import genai

import os

# Securely load the API key from environment variables or Streamlit secrets
DEFAULT_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not DEFAULT_API_KEY:
    try:
        import streamlit as st
        DEFAULT_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except (ImportError, FileNotFoundError, KeyError):
        pass



def clean_json_response(text):
    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()
    return text

def generate_script(topic, level, duration, focus, api_key=None, model_name="gemini-3.8-flash"):
    """
    Generates a learning script structured as JSON slides based on the given topic, 
    level, duration, and focus using Google's Gemini API.
    """
    # Configure with custom API key if provided
    current_key = api_key if api_key and api_key.strip() else DEFAULT_API_KEY
    if not current_key:
        raise ValueError("Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable, configure Streamlit secrets, or input it in the sidebar.")
    
    
    minutes = int(duration.split()[0])
    num_slides = minutes * 4  # 4 slides per minute (~15s per slide narration)
    
    prompt = f"""You are an expert educational video producer. Create a script about "{topic}" tailored for a {level} level learner with a focus on {focus}.
The target total duration is {duration} ({num_slides} slides).

Generate the script structured as a sequence of slides. For each slide, provide:
1. `slide_number` (integer, starting from 1)
2. `search_query` (2-3 words describing a highly relevant, clear image to search for on stock image sites, e.g., "cell structure diagram" or "plant leaf stomata")
3. `narration` (a concise narration text of about 15-25 words, easy to explain)

You MUST respond ONLY with a valid JSON array of objects. Do not include any markdown styling, conversational filler, or wrap it in ```json blocks.

Format pattern:
[
  {{"slide_number": 1, "search_query": "solar system overview", "narration": "Welcome! Today we will explore our solar system, a family of eight planets orbiting the Sun."}},
  ...
]"""

    client = genai.Client(api_key=current_key)

    model = model_name or "gemini-3.8-flash"

    response = client.models.generate_content(
        model=model,
        contents=prompt
    )

    cleaned_text = clean_json_response(response.text)

# Try parsing it to validate JSON; if it fails, let the caller handle the exception so it can fallback
    json.loads(cleaned_text)
    return cleaned_text


def generate_script_template(topic=None):
    """
    Returns a default script template for the adaptive learning video project.
    Generates dynamic placeholders if a topic is provided.
    """
    if not topic or topic.strip().lower() == "lifecycle of butterfly":
        return json.dumps([
            {"slide_number": 1, "search_query": "monarch butterfly egg", "narration": "It all starts with a tiny egg, laid by a female butterfly on a leaf, usually a milkweed plant."},
            {"slide_number": 2, "search_query": "caterpillar leaf eating", "narration": "Out of the egg hatches a larva, or caterpillar, which spends its time eating and growing rapidly."},
            {"slide_number": 3, "search_query": "chrysalis pupa hanging", "narration": "Once fully grown, the caterpillar forms a chrysalis, entering the pupa stage of quiet transformation."},
            {"slide_number": 4, "search_query": "monarch butterfly flying", "narration": "Finally, a beautiful adult butterfly emerges from the chrysalis, ready to fly and reproduce."}
        ], indent=2)
        
    topic_title = topic.strip().title()
    return json.dumps([
        {
            "slide_number": 1,
            "search_query": f"{topic_title} concept",
            "narration": f"Welcome! Today we are exploring the fascinating topic of {topic_title} and its fundamental principles."
        },
        {
            "slide_number": 2,
            "search_query": f"{topic_title} detail diagram",
            "narration": f"To understand {topic_title}, we must examine how its components interact and work together in nature or science."
        },
        {
            "slide_number": 3,
            "search_query": f"{topic_title} real world application",
            "narration": f"We can observe {topic_title} in action within various real-world scenarios and modern practical applications."
        },
        {
            "slide_number": 4,
            "search_query": f"{topic_title} conclusion summary",
            "narration": f"In conclusion, mastering {topic_title} provides us with critical insights into its broader impacts and systems."
        }
    ], indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python generate_script.py <topic> <level> <duration> <focus>")
        print("Example: python generate_script.py \"Water Cycle\" beginner \"1 minute\" \"steps involved\"")
    else:
        topic = sys.argv[1]
        level = sys.argv[2]
        duration = sys.argv[3]
        focus = sys.argv[4]
        
        try:
            script = generate_script(topic, level, duration, focus)
            print("\nGenerated Script:\n")
            print(script)
        except Exception as e:
            print(f"Error generating script: {e}")
            print("\nFallback Script:\n")
            print(generate_script_template())

