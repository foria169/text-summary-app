from __future__ import annotations

import os
from typing import Optional


def translate_text(text: str, target_lang_code: str = "en") -> str:
    """
    Translate text using OpenAI, if API key is available.
    target_lang_code examples: 'en', 'ko', 'ja', 'zh', 'es'
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

    from openai import OpenAI

    client = OpenAI()
    sys_prompt = (
        "You are a professional translator. Translate the user content faithfully into the target language."
    )
    content = f"Target language: {target_lang_code}\n\nText:\n{text}"
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": content},
        ],
        temperature=0.0,
    )
    return completion.choices[0].message.content.strip()








