import os
from openai import OpenAI

lm = OpenAI(
    base_url=os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"),
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio")
)
MODEL = os.getenv("MODEL", "local-model")


def _write(prompt: str, temperature: float = 0.7) -> str:
    resp = lm.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return resp.choices[0].message.content


def write_linkedin_post(topic: str, context: str = "") -> str:
    return _write(f"""Write a LinkedIn post about: {topic}
Context/source: {context}

Rules:
- Strong hook first line — no "excited to share" or "happy to announce"
- 150-200 words, short paragraphs (1-2 lines each)
- Tone: builder, thought leadership, insightful
- Relevant to local AI, SLMs, open-source, privacy where applicable
- 3-5 relevant hashtags at end
- End with a question or call to action
Output only the post text, nothing else.""")


def write_substack_note(topic: str, context: str = "") -> str:
    """Short Substack note — blurb/teaser format (100-150 words)"""
    return _write(f"""Write a short Substack note about: {topic}
Context/source: {context}

Rules:
- 100-150 words max
- Conversational, builder tone
- Hook in the first sentence
- Share one sharp insight or observation
- End with one line teasing deeper content or inviting a reply
- No hashtags
- Audience: AI builders, data scientists, open-source devs
Output only the note text, nothing else.""")


def write_substack_post(topic: str, context: str = "") -> str:
    """Full long-form Substack newsletter post (500-700 words)"""
    return _write(f"""Write a full Substack newsletter post about: {topic}
Context/source: {context}

Structure:
- Headline (punchy, curiosity-driven)
- Opening hook paragraph (2-3 sentences, why this matters now)
- Section 1: The problem or background (3-4 sentences)
- Section 2: The insight or solution (4-5 sentences, your unique take)
- Section 3: Practical takeaway or what to do (3-4 sentences)
- Closing: Personal note + one question to readers

Rules:
- 500-700 words
- Conversational but expert tone
- Audience: AI builders, data scientists, open-source devs
- Tie back to local AI, SLMs, privacy-first principles where relevant
- No hashtags
- Use subheadings for each section
Output only the post content, nothing else.""", temperature=0.75)


def write_short_note(topic: str, context: str = "") -> str:
    """Quick 5-7 bullet summary note — good for Notion logging"""
    return _write(f"""Summarize into a short note (5-7 bullet points):
Topic: {topic}
Content: {context}
Output only the bullets, nothing else.""", temperature=0.3)