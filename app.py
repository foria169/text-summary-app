import os
import io
import time
from typing import Optional, Tuple

import streamlit as st

from summarizer import summarize_text, AbstractiveProvider
from utils.file_loader import extract_text_from_upload
from utils.downloader import build_txt_bytes, build_pdf_bytes
from utils.translator import translate_text


APP_TITLE = "자동 텍스트 요약 툴"
APP_SUBTITLE = "입력 또는 업로드한 문서를 추출/생성 방식으로 빠르게 요약하세요."


def _length_to_params(length_choice: str) -> Tuple[int, int]:
    if length_choice == "짧게":
        return 60, 120
    if length_choice == "길게":
        return 180, 360
    return 120, 200


def _inject_theme_toggle(is_dark: bool) -> None:
    if is_dark:
        # Dark mode styles
        st.markdown(
            """
            <style>
            :root {
              --app-bg: #0e1117;
              --app-fg: #e5e7eb;
              --app-card: #1b1f2a;
            }
            .stApp { background: var(--app-bg); color: var(--app-fg); }
            .stMarkdown, .stText, .stCaption, h1, h2, h3, h4 { color: var(--app-fg) !important; }
            .stAlert, .stButton, .stDownloadButton { color: var(--app-fg) }
            .stContainer { background: transparent; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Light mode - 다크 모드와 반대 색상 (밝은 배경, 어두운 텍스트)
        st.markdown(
            """
            <style>
            /* 기본 배경 및 텍스트 */
            :root {
                --light-bg: #ffffff;
                --light-fg: #1a1a1a;
                --light-card: #f8f9fa;
                --light-border: #e9ecef;
                --light-hover: #e9ecef;
            }
            
            /* 메인 배경 */
            .stApp,
            .main .block-container {
                background-color: var(--light-bg) !important;
                color: var(--light-fg) !important;
            }
            
            /* 텍스트 색상 */
            .stMarkdown,
            .stText,
            .stCaption,
            h1, h2, h3, h4, h5, h6,
            p, div, span, label {
                color: var(--light-fg) !important;
            }
            
            /* 사이드바 */
            .stSidebar,
            [data-testid="stSidebar"] {
                background-color: #f8f9fa !important;
                border-right: 1px solid var(--light-border);
            }
            
            /* 입력 필드 */
            .stTextInput>div>div>input,
            .stTextArea>div>div>textarea,
            .stSelectbox>div>div>div,
            .stNumberInput>div>div>input {
                background-color: #ffffff !important;
                color: #000000 !important;
                border: 1px solid #ced4da !important;
            }
            
            /* 버튼 */
            .stButton>button,
            .stDownloadButton>button {
                background-color: #f8f9fa !important;
                color: #212529 !important;
                border: 1px solid #ced4da !important;
            }
            
            /* 탭 */
            .stTabs [role='tab'] {
                color: #6c757d !important;
            }
            .stTabs [aria-selected='true'] {
                color: #0d6efd !important;
                border-bottom: 2px solid #0d6efd !important;
            }
            
            /* 카드 및 박스 */
            .stAlert,
            .stExpander {
                background-color: var(--light-card) !important;
                border: 1px solid var(--light-border) !important;
            }
            
            /* 호버 효과 */
            button:hover,
            [role='tab']:hover {
                background-color: var(--light-hover) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
def _has_openai_key() -> bool:
    try:
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return True
        # Support Streamlit secrets
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            os.environ["OPENAI_API_KEY"] = str(st.secrets["OPENAI_API_KEY"]) or ""
            return bool(os.getenv("OPENAI_API_KEY"))
        return False
    except Exception:
        return False



def _format_history_label(h: dict, index: int) -> str:
    snippet = " ".join((h.get("summary") or "").splitlines())[:30]
    return f"{index+1}. {h.get('mode','')}/{h.get('length','')} - {snippet}"


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="wide")

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    # Session state init
    if "history" not in st.session_state:
        st.session_state["history"] = []  # list of dicts
    if "input_text" not in st.session_state:
        st.session_state["input_text"] = ""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = True

    with st.sidebar:
        st.header("요약 옵션")
        st.toggle("다크 모드", key="dark_mode")
        # Default to 생성 요약 if API key exists
        default_index = 1 if _has_openai_key() else 0
        summary_mode = st.radio("요약 방식", ["추출 요약", "생성 요약"], index=default_index, horizontal=False)
        length_choice = st.selectbox("요약 길이", ["짧게", "중간", "길게"], index=1)

        abstractive_provider = st.selectbox(
            "생성 요약 엔진",
            ["OpenAI (gpt-4o-mini)", "Transformers (bart-large-cnn)"]
        )

        temperature = 0.2
        if summary_mode == "생성 요약" and abstractive_provider.startswith("OpenAI"):
            temperature = st.slider("생성 온도 (창의성)", 0.0, 1.0, 0.2, 0.05)

        quality = "표준"
        beams = 4
        ngram = 3
        len_penalty = 1.1
        if summary_mode == "생성 요약" and not abstractive_provider.startswith("OpenAI"):
            quality = st.selectbox("품질/속도", ["빠름", "표준", "고급"], index=1)
            if quality == "빠름":
                beams, ngram, len_penalty = 2, 3, 1.0
            elif quality == "표준":
                beams, ngram, len_penalty = 4, 3, 1.1
            else:  # 고급
                beams, ngram, len_penalty = 8, 4, 1.2

        enable_keywords = st.checkbox("키워드 추출 (간단)", value=False)
        enable_translation = st.checkbox("요약 결과 번역", value=False)
        target_lang = "영어 (en)"
        if enable_translation:
            target_lang = st.selectbox("번역 대상 언어", ["영어 (en)", "한국어 (ko)", "일본어 (ja)", "중국어 (zh)", "스페인어 (es)"])

        with st.expander("최근 요약"):
            history = st.session_state["history"]
            if not history:
                st.caption("최근 요약이 없습니다.")
            else:
                rev = list(reversed(history[-10:]))
                items = [_format_history_label(h, i) for i, h in enumerate(rev)]
                idx = st.selectbox("항목 선택", options=list(range(len(items))), format_func=lambda i: items[i]) if items else None
                if items and st.button("불러오기"):
                    chosen = rev[idx]
                    st.session_state["input_text"] = chosen["input"]
                    st.rerun()

    # Apply theme after reading sidebar state to reflect toggle immediately
    _inject_theme_toggle(st.session_state["dark_mode"])

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("텍스트 입력")
        input_text = st.text_area(
            "직접 입력",
            value=st.session_state.get("input_text", ""),
            placeholder="여기에 요약할 텍스트를 입력하거나, 오른쪽에서 파일을 업로드하세요.",
            height=260,
        )
        st.session_state["input_text"] = input_text
    with col_right:
        st.subheader("파일 업로드")
        uploaded = st.file_uploader("TXT, PDF, DOCX 지원", type=["txt", "pdf", "docx"], accept_multiple_files=False)
        if uploaded is not None:
            try:
                loaded_text = extract_text_from_upload(uploaded)
                if loaded_text:
                    if input_text:
                        input_text = input_text + "\n\n" + loaded_text
                    else:
                        input_text = loaded_text
                    st.session_state["input_text"] = input_text
            except Exception as e:
                st.error(f"파일 처리 중 오류가 발생했습니다: {e}")

    st.divider()
    run_clicked = st.button("요약하기", type="primary")

    if run_clicked:
        if not input_text or len(input_text.strip()) == 0:
            st.warning("요약할 텍스트를 입력하거나 파일을 업로드하세요.")
            return

        min_len, max_len = _length_to_params(length_choice)

        if summary_mode == "생성 요약":
            provider = AbstractiveProvider.OPENAI if abstractive_provider.startswith("OpenAI") else AbstractiveProvider.TRANSFORMERS
            if provider == AbstractiveProvider.OPENAI and not _has_openai_key():
                st.info("OPENAI_API_KEY가 없어 Transformers로 대체합니다.")
                provider = AbstractiveProvider.TRANSFORMERS
        else:
            provider = None

        with st.spinner("요약 중입니다. 잠시만 기다려주세요..."):
            start = time.perf_counter()
            try:
                summary = summarize_text(
                    text=input_text,
                    mode="abstractive" if summary_mode == "생성 요약" else "extractive",
                    min_length=min_len,
                    max_length=max_len,
                    provider=provider,
                    temperature=temperature,
                    openai_model="gpt-4o-mini",
                    num_beams=beams,
                    no_repeat_ngram_size=ngram,
                    length_penalty=len_penalty,
                )
            except Exception as e:
                st.error(f"요약 중 오류가 발생했습니다: {e}")
                return
            elapsed = time.perf_counter() - start

        if not summary:
            st.warning("요약 결과가 비어 있습니다.")
            return

        orig_words = len(input_text.split())
        sum_words = len(summary.split())

        st.subheader("요약 결과")
        st.caption(f"원문 {orig_words} 단어 → 요약 {sum_words} 단어 | 처리 시간 {elapsed:.2f}s")
        st.write("")
        st.code(summary, language="markdown")  # built-in copy button

        # Optional simple keywords (top-N words by frequency, excluding very short tokens)
        if enable_keywords:
            tokens = [t.strip('.,!?;:"()[]{}') for t in summary.split()]
            tokens = [t for t in tokens if len(t) > 2]
            freq = {}
            for t in tokens:
                freq[t.lower()] = freq.get(t.lower(), 0) + 1
            top_items = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:10]
            if top_items:
                st.markdown("**키워드**: " + ", ".join([k for k, _ in top_items]))

        translated: Optional[str] = None
        if enable_translation:
            with st.spinner("번역 중..."):
                try:
                    target_code = target_lang.split("(")[-1].strip(")")
                    if _has_openai_key():
                        translated = translate_text(summary, target_lang_code=target_code)
                    else:
                        st.info("OPENAI_API_KEY가 없어 번역을 건너뜁니다.")
                except Exception as e:
                    st.error(f"번역 중 오류가 발생했습니다: {e}")

        st.write("")
        st.subheader("다운로드")
        txt_bytes = build_txt_bytes(translated or summary)
        st.download_button("TXT 다운로드", data=txt_bytes, file_name="summary.txt", mime="text/plain")

        try:
            pdf_bytes = build_pdf_bytes(translated or summary)
            st.download_button("PDF 다운로드", data=pdf_bytes, file_name="summary.pdf", mime="application/pdf")
        except Exception as e:
            st.info("PDF 생성 라이브러리가 없어 TXT로만 제공됩니다. requirements를 설치해주세요.")

        # Save to history
        st.session_state["history"].append(
            {
                "input": input_text,
                "summary": summary,
                "translated": translated,
                "mode": summary_mode,
                "length": length_choice,
            }
        )


if __name__ == "__main__":
    main()




