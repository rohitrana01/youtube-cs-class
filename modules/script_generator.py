"""
modules/script_generator.py
Calls the Anthropic Claude API to generate a structured script
for each topic — narration text + slide content + YouTube metadata.
"""
import json
import re
from config import GEMINI_API_KEY, GEMINI_MODEL, LANGUAGE


def generate_script(topic: dict) -> dict:
    """
    Given a topic dict from curriculum.json, return structured script data:
    {
      "video_title": str,
      "video_description": str,
      "tags": [str],
      "narration": str,         # Full ~700-word narration for TTS
      "segments": [
        {
          "title": str,
          "duration_seconds": int,
          "points": [str],       # Bullet points for slides
          "code": str | null,    # Optional code snippet
          "image_prompt": str    # Visual prompt for AI image generator
        }
      ],
      "quiz": {
        "question": str,
        "options": [str],       # Exactly 4 options: ["A) ...", "B) ...", "C) ...", "D) ..."]
        "correct_answer": str,  # "A", "B", "C", or "D"
        "explanation": str
      },
      "summary_points": [str],   # 3-5 key takeaways
      "next_topic": str,         # Title of the next video
      "short": {                 # Daily vertical Shorts data
        "title": str,            # Viral title with #shorts
        "description": str,      # Viral description with hashtags
        "tags": [str],
        "narration": str,        # Fast-paced ~45-word narration under 25s
        "image_prompt": str      # Engaging visual (specifying cartoon or real style)
      }
    }
    """
    if not GEMINI_API_KEY:
        print("[script_generator] GEMINI_API_KEY is not set. Using fallback script.")
        return _fallback_script(topic)

    lang_instruction = ""
    if LANGUAGE == "hi":
        lang_instruction = """
IMPORTANT LANGUAGE RULES FOR HINDI (hi):
1. video_title & video_description: Write in clean, highly appealing Hindi (using Devanagari script). Keep technical terms as they are, but in Devanagari.
2. narration: Must be in natural, conversational spoken Hindi (Devanagari script, e.g., "नमस्ते दोस्तों! आज हम बात करेंगे..."). Explain concepts simply. Write technical names in Devanagari (कंप्यूटर, रैम, सीपीयू).
3. segments[].points (Slide Text): Write in bilingual Hinglish or English with Hindi meaning in brackets (e.g., "CPU: Central Processing Unit (कंप्यूटर का दिमाग)"). Keep it under 80 characters.
4. quiz & summary_points: Write them in natural Hindi (Devanagari script).
5. short: Write the "narration" and "title" in highly viral spoken Hindi (written in Devanagari) to hook normal people instantly. Keep technical terms in Devanagari.
"""
    else:
        lang_instruction = """
IMPORTANT LANGUAGE RULES FOR ENGLISH (en):
1. All fields (including the "short" fields) must be in standard, clear, highly engaging English.
"""

    prompt = f"""You are creating a 5-minute educational YouTube video script AND a 20-second vertical YouTube Short about: "{topic['title']}"

Module: {topic['module']}
Level: {topic['level']}
Day: {topic['day']} of a 100-day Computer Course

{lang_instruction}

IMPORTANT: Return ONLY valid JSON — no markdown, no code fences, no explanation.

The JSON must match this exact structure:
{{
  "video_title": "[Day {topic['day']}: Topic Title | Course Name]",
  "video_description": "[Video description covering the topic, with hashtags, target audience, etc.]",
  "tags": ["computer science", "programming", "tutorial", "education", "{topic['module'].lower()}"],
  "narration": "[Write a ~700-word highly engaging narration script. Conversational tone. Start with a strong hook/question. Explain everything step-by-step. Introduce the pop quiz before the summary points. Tease the next video at the very end.]",
  "segments": [
    {{
      "title": "[Section heading]",
      "duration_seconds": 60,
      "points": [
        "[Punchy bullet point 1]",
        "[Punchy bullet point 2]",
        "[Punchy bullet point 3]"
      ],
      "code": null,
      "image_prompt": "[A highly specific visual metaphor or conceptual diagram explaining this section. Describe the scene in detail. For example, for RAM, describe 'A student's study desk representing RAM, cluttered with open notebooks, with a filing cabinet in the background representing permanent storage'. Do NOT request any text in the image.]"
    }},
    {{
      "title": "[Section heading]",
      "duration_seconds": 60,
      "points": ["...", "...", "..."],
      "code": null,
      "image_prompt": "[A highly specific visual metaphor or conceptual diagram explaining this section. Describe the scene in detail. Do NOT request any text in the image.]"
    }}
  ],
  "quiz": {{
    "question": "[A simple, interactive multiple-choice question testing the core concept of today's lesson]",
    "options": [
      "A) [Option A]",
      "B) [Option B]",
      "C) [Option C]",
      "D) [Option D]"
    ],
    "correct_answer": "[A, B, C, or D]",
    "explanation": "[A brief 1-sentence explanation of why this option is correct]"
  }},
  "summary_points": [
    "[Key takeaway 1]",
    "[Key takeaway 2]",
    "[Key takeaway 3]"
  ],
  "next_topic": "[Title of day {topic['day'] + 1} topic]",
  "short": {{
    "title": "[Viral title under 70 characters with #shorts, e.g., 'This Computer Fact Will Blow Your Mind! 🤯 #shorts']",
    "description": "[A punchy 1-sentence description with viral hashtags, e.g., '#shorts #techfacts #computer']",
    "tags": ["shorts", "techfacts", "viral", "computer"],
    "narration": "[An extremely fast-paced, high-curiosity 40-50 word narration script that fits within 25 seconds. Start instantly with a mind-blowing hook. E.g., 'Wait, did you know that your computer RAM is actually just like a messy student desk?']",
    "image_prompt": "[A highly visual description of an image for a vertical 1080x1920 layout. Force a distinct style, either 'A vibrant 3D digital cartoon illustration of...' or 'An ultra-realistic close-up photograph of...', whichever style creates the best visual hook for the fact. Do NOT request text.]"
  }}
}}

Rules:
- Include 3-5 segments.
- Keep each slide bullet point simple, punchy, and under 80 characters.
- Always set the `"code"` field to `null` since this is a non-coding computer course.
- Ensure the `image_prompt` is a detailed visual description or metaphor representing the concept of that segment, without text in the image.
- Enforce the YouTube Short to be 20-30 seconds with an immediate curiosity hook and either cartoon or realistic style.
- Return ONLY the raw JSON object."""

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        raw = response.text.strip()
    except Exception as e:
        print(f"[script_generator] Gemini API error: {e}")
        return _fallback_script(topic)

    # Strip accidental markdown fences
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[script_generator] JSON parse error: {e}")
        print(f"[script_generator] Raw response (first 500 chars): {raw[:500]}")
        # Return a minimal fallback so the pipeline doesn't crash
        data = _fallback_script(topic)

    return data


def _fallback_script(topic: dict) -> dict:
    """Minimal fallback if Gemini's response can't be parsed."""
    is_hi = LANGUAGE == "hi"
    
    if is_hi:
        title = f"Day {topic['day']}: {topic['title']} | कंप्यूटर कोर्स"
        desc = f"आज हम सीखेंगे: {topic['title']}। यह हमारे 100-दिन के कंप्यूटर कोर्स का हिस्सा है।"
        narration = (
            f"हेलो दोस्तों, कंप्यूटर कोर्स के डे {topic['day']} में आपका स्वागत है! "
            f"आज हम {topic['title']} के बारे में बात करेंगे। "
            f"यह {topic['module']} का एक बहुत ही महत्वपूर्ण हिस्सा है। "
            "चलिए इसे बिल्कुल आसान भाषा में समझते हैं। "
            "वीडियो के आखिर में हम एक छोटा सा क्विज़ भी खेलेंगे। "
            "तो अंत तक बने रहिए और चैनल को सब्सक्राइब करना न भूलें!"
        )
        points1 = [
            f"Welcome to {topic['title']} (स्वागत है)",
            f"Part of {topic['module']} (महत्वपूर्ण मॉड्यूल)",
            f"Day {topic['day']} (दसवां दिन)",
            "Let's learn together (सीखना शुरू करें)"
        ]
        points2 = [
            "Core Concepts (मुख्य बातें)",
            "Real-world Examples (उदाहरण)",
            "Why it matters (क्यों जरूरी है)",
            "Practice regularly (नियमित अभ्यास)"
        ]
        quiz = {
            "question": "क्या कंप्यूटर केवल निर्देशों (instructions) का पालन करता है?",
            "options": [
                "A) हाँ, हमेशा",
                "B) नहीं, कभी नहीं",
                "C) कभी-कभी",
                "D) पता नहीं"
            ],
            "correct_answer": "A",
            "explanation": "कंप्यूटर एक मशीन है और यह केवल यूजर द्वारा दिए गए निर्देशों का ही पालन करता है।"
        }
        summary_points = [
            f"हमने {topic['title']} की मूल बातें सीखीं।",
            "कंप्यूटर को आसान उदाहरणों से समझा।",
            "सीखते रहिए और प्रैक्टिस करते रहिए!"
        ]
        short = {
            "title": f"क्या आपको पता है कंप्यूटर कैसे काम करता है? 🤯 #shorts",
            "description": "सीखें कंप्यूटर की ये अद्भुत जानकारी। #shorts #techfacts #computerknowledge",
            "tags": ["shorts", "techfacts", "computer"],
            "narration": f"क्या आप जानते हैं कि कंप्यूटर का दिमाग यानी सीपीयू एक सेकंड में लाखों कैलकुलेशन कर सकता है? यह आपकी पलक झपकने से भी तेज है!",
            "image_prompt": "A vibrant 3D digital cartoon illustration of a cute glowing computer CPU chip running super fast with happy electric sparks."
        }
    else:
        title = f"Day {topic['day']}: {topic['title']} | CS Course"
        desc = f"Today we learn about {topic['title']}. Part of our 100-day CS course."
        narration = (
            f"Welcome to Day {topic['day']} of our Computer Science course! "
            f"Today we're learning about {topic['title']}. "
            f"This is an important topic in {topic['module']}. "
            "Let's dive in and explore the key concepts together. "
            "We'll also have a quick pop quiz at the end, so stick around. "
            "Don't forget to subscribe for daily CS lessons!"
        )
        points1 = [
            f"Welcome to {topic['title']}",
            f"Part of our {topic['module']} module",
            f"Difficulty level: {topic['level']}",
            "Let's explore the key ideas"
        ]
        points2 = [
            "Understanding the fundamentals",
            "Real-world applications",
            "Why this matters in CS",
            "Common use cases"
        ]
        quiz = {
            "question": "Which component is known as the brain of the computer?",
            "options": [
                "A) RAM",
                "B) CPU",
                "C) Storage",
                "D) GPU"
            ],
            "correct_answer": "B",
            "explanation": "The CPU (Central Processing Unit) processes all instructions and acts as the brain."
        }
        summary_points = [
            f"We covered the basics of {topic['title']}",
            "Understanding theory helps practical coding",
            "Practice makes perfect — try it yourself!"
        ]
        short = {
            "title": f"The CPU processes faster than you think! 🤯 #shorts",
            "description": "Interesting computer fact about CPU processing speed. #shorts #techfacts",
            "tags": ["shorts", "techfacts", "computer"],
            "narration": "Did you know that your computer's CPU can process billions of calculations in a single second? That's faster than the speed of human thought!",
            "image_prompt": "An ultra-realistic close-up photograph of a modern motherboard with golden circuits glowing as data travels through it."
        }

    return {
        "video_title": title,
        "video_description": desc,
        "tags": ["computer science", "programming", "tutorial", "hindi" if is_hi else "english"],
        "narration": narration,
        "segments": [
            {
                "title": f"Introduction to {topic['title']}",
                "duration_seconds": 120,
                "points": points1,
                "code": None,
                "image_prompt": "A modern computer workstation with dual monitors"
            },
            {
                "title": "Core Concepts",
                "duration_seconds": 120,
                "points": points2,
                "code": None,
                "image_prompt": "A glowing circuit board with data lines"
            }
        ],
        "quiz": quiz,
        "summary_points": summary_points,
        "next_topic": "Next topic in the series",
        "short": short
    }

