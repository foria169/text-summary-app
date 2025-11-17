from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import os


class AbstractiveProvider(Enum):
    OPENAI = "openai"
    TRANSFORMERS = "transformers"


_transformer_pipe = None


def _get_transformer_pipeline():
    global _transformer_pipe
    if _transformer_pipe is None:
        from transformers import pipeline
        # Prefer BART large, but gracefully fall back to a lighter model and CPU-only
        try:
            _transformer_pipe = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                tokenizer="facebook/bart-large-cnn",
                device=-1,  # CPU
            )
        except Exception:
            _transformer_pipe = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-12-6",
                tokenizer="sshleifer/distilbart-cnn-12-6",
                device=-1,  # CPU
            )
    return _transformer_pipe


def _chunk_text(text: str, max_words: int = 450, overlap_words: int = 50) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    step = max(1, max_words - overlap_words)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _deduplicate_sentences(text: str) -> str:
    import re
    # Split on sentence boundaries, drop exact duplicates while preserving order
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    seen = set()
    ordered: List[str] = []
    for s in sentences:
        norm = s.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(norm)
    return " ".join(ordered)


def _summarize_abstractive_transformers(
    text: str,
    min_length: int,
    max_length: int,
    num_beams: int = 4,
    no_repeat_ngram_size: int = 3,
    length_penalty: float = 1.1,
    model_name: str = "facebook/bart-large-cnn",
) -> str:
    pipe = _get_transformer_pipeline()
    chunks = _chunk_text(text, max_words=450, overlap_words=60)
    outputs: List[str] = []
    for c in chunks:
        # Adapt lengths to the chunk size to avoid decoder index errors
        c_words = len(c.split())
        local_max = max(20, min(max_length, int(c_words * 0.6)))
        local_min = max(5, min(min_length, max(local_max - 40, 5)))
        if local_min >= local_max:
            local_min = max(5, local_max - 5)
        try:
            res = pipe(
                c,
                min_length=local_min,
                max_length=local_max,
                num_beams=num_beams,
                no_repeat_ngram_size=no_repeat_ngram_size,
                length_penalty=length_penalty,
            )[0]["summary_text"]
            outputs.append(res.strip())
        except Exception:
            # Fallback: take first sentences as a safe extractive substitute
            from re import split as re_split
            safe = re_split(r"(?<=[.!?\n])\s+", c)
            outputs.append(" ".join(safe[:2]).strip())
    combined = "\n\n".join(outputs)
    # Second-pass refinement to improve coherence
    if len(outputs) > 1:
        try:
            refined = pipe(
                combined,
                min_length=min_length,
                max_length=max_length,
                num_beams=max(4, num_beams),
                no_repeat_ngram_size=no_repeat_ngram_size,
                length_penalty=length_penalty,
            )[0]["summary_text"].strip()
            combined = refined
        except Exception:
            pass
    return _deduplicate_sentences(combined)


def _summarize_abstractive_openai(text: str, min_length: int, max_length: int, temperature: float = 0.2, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

    client = OpenAI()
    sys_prompt = (
        "당신은 전문 요약가입니다. 주어진 한국어 또는 영어 텍스트를 간결하고 정확하게 요약하세요. "
        f"요약 길이는 대략 {min_length}-{max_length} 단어 범위를 목표로 하세요."
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": text},
        ],
        temperature=temperature,
    )
    return completion.choices[0].message.content.strip()


def _summarize_extractive(text: str, min_length: int, max_length: int) -> str:
    # Very lightweight frequency-based extraction (no external deps)
    import re

    # Split sentences
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
    if not sentences:
        return ""

    # Tokenize and compute word frequencies
    words = re.findall(r"\w+", text.lower())
    freq = {}
    for w in words:
        if len(w) <= 2:
            continue
        freq[w] = freq.get(w, 0) + 1

    # Score sentences by sum of word frequencies (normalized by length)
    sentence_scores = []
    for s in sentences:
        sw = re.findall(r"\w+", s.lower())
        if not sw:
            continue
        score = sum(freq.get(w, 0) for w in sw) / (len(sw) ** 0.8)
        sentence_scores.append((score, s))

    # Select top sentences until reaching approx max_length words
    sentence_scores.sort(key=lambda x: x[0], reverse=True)
    selected: List[str] = []
    total_words = 0
    for _, s in sentence_scores:
        w = len(s.split())
        if total_words + w <= max_length or total_words == 0:
            selected.append(s)
            total_words += w
        if total_words >= max_length:
            break

    # If we selected nothing, fallback to the first sentence(s)
    if not selected:
        selected = sentences[:3]

    result = " ".join(selected)
    return _deduplicate_sentences(result)


def summarize_text(
    text: str,
    mode: str,
    min_length: int,
    max_length: int,
    provider: Optional[AbstractiveProvider] = None,
    temperature: float = 0.2,
    openai_model: str = "gpt-4o-mini",
    num_beams: int = 4,
    no_repeat_ngram_size: int = 3,
    length_penalty: float = 1.1,
) -> str:
    text = text.strip()
    if not text:
        return ""

    if mode == "extractive":
        return _summarize_extractive(text, min_length=min_length, max_length=max_length)

    if mode == "abstractive":
        if provider == AbstractiveProvider.OPENAI:
            return _deduplicate_sentences(
                _summarize_abstractive_openai(
                    text,
                    min_length=min_length,
                    max_length=max_length,
                    temperature=temperature,
                    model=openai_model,
                )
            )
        return _summarize_abstractive_transformers(
            text,
            min_length=min_length,
            max_length=max_length,
            num_beams=num_beams,
            no_repeat_ngram_size=no_repeat_ngram_size,
            length_penalty=length_penalty,
        )

    raise ValueError(f"Unknown mode: {mode}")





