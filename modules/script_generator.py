"""
modules/script_generator.py
Calls the Anthropic Claude API to generate a structured script
for each topic — narration text + slide content + YouTube metadata.
"""
import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL


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
          "code": str | null     # Optional code snippet
        }
      ],
      "summary_points": [str],   # 3-5 key takeaways
      "next_topic": str          # Title of the next video
    }
    """
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            print("[script_generator] GEMINI_API_KEY is not set. Using fallback script.")
            return _fallback_script(topic)
    else:
        if not ANTHROPIC_API_KEY:
            print("[script_generator] ANTHROPIC_API_KEY is not set. Using fallback script.")
            return _fallback_script(topic)

    prompt = f"""You are creating a 5-minute educational YouTube video script about: "{topic['title']}"

Module: {topic['module']}
Level: {topic['level']}
Day: {topic['day']} of a 100-day Computer Science course

IMPORTANT: Return ONLY valid JSON — no markdown, no code fences, no explanation.

The JSON must match this exact structure:
{{
  "video_title": "Day {topic['day']}: {topic['title']} | CS Course",
  "video_description": "In today's 5-minute lesson we cover {topic['title']}. Part of our free 100-day CS course from basics to advanced.\\n\\nTopics covered:\\n- [list 3-4 bullet points]\\n\\n#LearnCS #ComputerScience #Coding",
  "tags": ["computer science", "programming", "tutorial", "education", "{topic['module'].lower()}"],
  "narration": "[Write a ~700-word engaging narration script. Conversational tone. Start with a hook. Explain the topic clearly with real-world analogies. End with a summary and teaser for next video.]",
  "segments": [
    {{
      "title": "[Section heading]",
      "duration_seconds": 60,
      "points": [
        "[Short, punchy bullet point 1]",
        "[Short, punchy bullet point 2]",
        "[Short, punchy bullet point 3]"
      ],
      "code": null
    }},
    {{
      "title": "[Another section]",
      "duration_seconds": 60,
      "points": ["...", "...", "..."],
      "code": "[Optional: 4-6 line code example relevant to the topic, or null if not applicable]"
    }}
  ],
  "summary_points": [
    "[Key takeaway 1 — concise]",
    "[Key takeaway 2 — concise]",
    "[Key takeaway 3 — concise]"
  ],
  "next_topic": "[Title of day {topic['day'] + 1} topic]"
}}

Rules:
- Include 3-5 segments totalling ~270 seconds of content (the rest is intro/outro)
- Each segment has 3-4 bullet points
- Add a code block to at least one segment if it's a programming topic
- Keep bullet points under 80 characters each
- Make the narration engaging and suitable for a voice-over
- Return ONLY the JSON object, nothing else"""

    if LLM_PROVIDER == "gemini":
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
    else:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
        except Exception as e:
            print(f"[script_generator] Anthropic API error: {e}")
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
    """Minimal fallback if Claude's response can't be parsed."""
    return {
        "video_title": f"Day {topic['day']}: {topic['title']} | CS Course",
        "video_description": f"Today we learn about {topic['title']}. Part of our 100-day CS course.",
        "tags": ["computer science", "programming", "tutorial"],
        "narration": (
            f"Welcome to Day {topic['day']} of our Computer Science course! "
            f"Today we're learning about {topic['title']}. "
            f"This is an important topic in {topic['module']}. "
            "Let's dive in and explore the key concepts together. "
            "By the end of this video, you'll have a solid understanding of the fundamentals. "
            "Thanks for watching, and don't forget to subscribe for daily CS lessons!"
        ),
        "segments": [
            {
                "title": f"Introduction to {topic['title']}",
                "duration_seconds": 120,
                "points": [
                    f"Welcome to {topic['title']}",
                    f"Part of our {topic['module']} module",
                    f"Difficulty level: {topic['level']}",
                    "Let's explore the key ideas"
                ],
                "code": None
            },
            {
                "title": "Core Concepts",
                "duration_seconds": 120,
                "points": [
                    "Understanding the fundamentals",
                    "Real-world applications",
                    "Why this matters in CS",
                    "Common use cases"
                ],
                "code": None
            }
        ],
        "summary_points": [
            f"We covered the basics of {topic['title']}",
            "Understanding theory helps practical coding",
            "Practice makes perfect — try it yourself!"
        ],
        "next_topic": "Next topic in the series"
    }
