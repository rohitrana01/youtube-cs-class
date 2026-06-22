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
2. All narration fields (intro.narration, segments[].narration, quiz.narration, summary.narration, outro.narration): Must be in natural, conversational spoken Hindi (Devanagari script, e.g., "नमस्ते दोस्तों! आज हम बात करेंगे..."). Explain concepts simply. Write technical names in Devanagari (कंप्यूटर, रैम, सीपीयू).
3. segments[].points (Slide Text): Write in bilingual Hinglish or English with Hindi meaning in brackets (e.g., "CPU: Central Processing Unit (कंप्यूटर का दिमाग)"). Keep it under 80 characters.
4. quiz & summary fields (except their narrations): Write them in natural Hindi (Devanagari script).
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
  "intro": {{
    "title": "[Intro Slide Title, e.g. Day {topic['day']}: {topic['title']}]",
    "narration": "[Write a ~50-word highly engaging introduction speech. Start with a strong hook/question. Conversational tone.]"
  }},
  "segments": [
    {{
      "title": "[Section heading]",
      "points": [
        "[Punchy bullet point 1]",
        "[Punchy bullet point 2]",
        "[Punchy bullet point 3]"
      ],
      "code": null,
      "image_prompt": "[A highly specific visual metaphor or conceptual diagram explaining this section. Force a realistic style, starting with 'An ultra-realistic photograph of...' or 'A realistic 3D digital render of...'. Avoid cartoonish styles. Describe the scene in detail. Do NOT request any text in the image.]",
      "narration": "[Write a ~150-word detailed narration explaining the points of this section in a conversational, easy-to-understand way. Do not write too fast or slow. Keep it highly engaging.]"
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
    "explanation": "[A brief 1-sentence explanation of why this option is correct]",
    "narration": "[Write a ~60-word narration script that introduces the quiz question, reads the options, tells the viewer to guess, and then reveals and explains the correct answer. Keep it engaging!]"
  }},
  "summary": {{
    "points": [
      "[Key takeaway 1]",
      "[Key takeaway 2]",
      "[Key takeaway 3]"
    ],
    "narration": "[Write a ~80-word narration summary wrapping up the key points of the lesson.]"
  }},
  "outro": {{
    "next_topic": "[Title of day {topic['day'] + 1} topic]",
    "narration": "[Write a ~40-word outro thanking the viewer, reminding them to subscribe/like, and teasing the next topic: {topic['day'] + 1}.]"
  }},
  "short": {{
    "title": "[Viral title under 70 characters with #shorts, e.g., 'This Computer Fact Will Blow Your Mind! 🤯 #shorts']",
    "description": "[A punchy 1-sentence description with viral hashtags, e.g., '#shorts #techfacts #computer']",
    "tags": ["shorts", "techfacts", "viral", "computer"],
    "narration": "[An extremely fast-paced, high-curiosity 40-50 word narration script that fits within 25 seconds. Start instantly with a mind-blowing hook. E.g., 'Wait, did you know that your computer RAM is actually just like a messy student desk?']",
    "image_prompt": "[A highly visual description of an image for a vertical 1080x1920 layout. Force a realistic style, starting with 'An ultra-realistic close-up photograph of...' or 'A realistic 3D digital render of...'. Avoid cartoonish styles. Do NOT request text.]"
  }}
}}

Rules:
- Include 3-5 segments.
- Keep each slide bullet point simple, punchy, and under 80 characters.
- Always set the `"code"` field to `null` since this is a non-coding computer course.
- Ensure all `image_prompt` fields use a realistic, premium photographic or digital render style (no cartoons).
- Enforce the YouTube Short to be 20-30 seconds with an immediate curiosity hook and a realistic style.
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
        intro_narration = (
            f"नमस्ते दोस्तों! कंप्यूटर कोर्स के डे {topic['day']} में आपका स्वागत है! "
            f"आज हम {topic['title']} के बारे में जानेंगे।"
        )
        points1 = [
            f"Welcome to {topic['title']} (स्वागत है)",
            f"Part of {topic['module']} (महत्वपूर्ण मॉड्यूल)",
            f"Day {topic['day']} (दसवां दिन)",
            "Let's learn together (सीखना शुरू करें)"
        ]
        seg1_narration = f"यह {topic['module']} का एक बहुत ही महत्वपूर्ण हिस्सा है। चलिए इसे बिल्कुल आसान भाषा में समझते हैं।"
        points2 = [
            "Core Concepts (मुख्य बातें)",
            "Real-world Examples (उदाहरण)",
            "Why it matters (क्यों जरूरी है)",
            "Practice regularly (नियमित अभ्यास)"
        ]
        seg2_narration = "कंप्यूटर के इस भाग को अच्छी तरह समझना बहुत आवश्यक है, ताकि हम इसे दैनिक जीवन में सही ढंग से उपयोग कर सकें।"
        quiz = {
            "question": "क्या कंप्यूटर केवल निर्देशों (instructions) का पालन करता है?",
            "options": [
                "A) हाँ, हमेशा",
                "B) नहीं, कभी नहीं",
                "C) कभी-कभी",
                "D) पता नहीं"
            ],
            "correct_answer": "A",
            "explanation": "कंप्यूटर एक मशीन है और यह केवल यूजर द्वारा दिए गए निर्देशों का ही पालन करता है।",
            "narration": "अब वक्त है एक छोटे से क्विज़ का। सवाल है: क्या कंप्यूटर केवल निर्देशों का पालन करता है? कमेंट्स में अपना जवाब दें! सही जवाब है ए, हाँ हमेशा।"
        }
        summary_points = [
            f"हमने {topic['title']} की मूल बातें सीखीं।",
            "कंप्यूटर को आसान उदाहरणों से समझा।",
            "सीखते रहिए और प्रैक्टिस करते रहिए!"
        ]
        summary_narration = f"तो आज हमने {topic['title']} के बारे में विस्तार से सीखा और समझा कि यह कैसे उपयोगी है।"
        outro_narration = f"वीडियो पसंद आया तो लाइक और सब्सक्राइब करें! अगले वीडियो में हम अगले टॉपिक पर चर्चा करेंगे। धन्यवाद!"
        short = {
            "title": f"क्या आपको पता है कंप्यूटर कैसे काम करता है? 🤯 #shorts",
            "description": "सीखें कंप्यूटर की ये अद्भुत जानकारी। #shorts #techfacts #computerknowledge",
            "tags": ["shorts", "techfacts", "computer"],
            "narration": f"क्या आप जानते हैं कि कंप्यूटर का दिमाग यानी सीपीयू एक सेकंड में लाखों कैलकुलेशन कर सकता है? यह आपकी पलक झपकने से भी तेज है!",
            "image_prompt": "An ultra-realistic close-up photograph of a modern motherboard with golden circuits glowing as data travels through it."
        }
    else:
        title = f"Day {topic['day']}: {topic['title']} | CS Course"
        desc = f"Today we learn about {topic['title']}. Part of our 100-day CS course."
        intro_narration = (
            f"Welcome to Day {topic['day']} of our Computer Science course! "
            f"Today we're learning about {topic['title']}."
        )
        points1 = [
            f"Welcome to {topic['title']}",
            f"Part of our {topic['module']} module",
            f"Difficulty level: {topic['level']}",
            "Let's explore the key ideas"
        ]
        seg1_narration = "Let's dive in and explore the key concepts together. This is an important topic to understand."
        points2 = [
            "Understanding the fundamentals",
            "Real-world applications",
            "Why this matters in CS",
            "Common use cases"
        ]
        seg2_narration = "Now let's look at the core principles and how they are applied in everyday technology."
        quiz = {
            "question": "Which component is known as the brain of the computer?",
            "options": [
                "A) RAM",
                "B) CPU",
                "C) Storage",
                "D) GPU"
            ],
            "correct_answer": "B",
            "explanation": "The CPU (Central Processing Unit) processes all instructions and acts as the brain.",
            "narration": "Time for a quick pop quiz! Which component is known as the brain of the computer? The answer is B, the CPU!"
        }
        summary_points = [
            f"We covered the basics of {topic['title']}",
            "Understanding theory helps practical coding",
            "Practice makes perfect — try it yourself!"
        ]
        summary_narration = "To summarize, we went over the main aspects of this topic and why it is crucial."
        outro_narration = "Thanks for watching! Don't forget to subscribe for daily CS lessons, and see you tomorrow!"
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
        "intro": {
            "title": f"Day {topic['day']}: {topic['title']}",
            "narration": intro_narration
        },
        "segments": [
            {
                "title": f"Introduction to {topic['title']}",
                "points": points1,
                "code": None,
                "image_prompt": "An ultra-realistic photograph of a modern computer workstation with dual monitors",
                "narration": seg1_narration
            },
            {
                "title": "Core Concepts",
                "points": points2,
                "code": None,
                "image_prompt": "A realistic 3D digital render of a glowing circuit board with data lines",
                "narration": seg2_narration
            }
        ],
        "quiz": quiz,
        "summary": {
            "points": summary_points,
            "narration": summary_narration
        },
        "outro": {
            "next_topic": "Next topic in the series",
            "narration": outro_narration
        },
        "short": short
    }

