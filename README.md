# 자동 텍스트 요약 툴 (Streamlit)

간단한 문서 요약 웹앱입니다. 텍스트 입력 또는 TXT/PDF/DOCX 업로드를 지원하며, 추출 요약/생성 요약과 결과 다운로드(TXT/PDF)를 제공합니다. 선택적으로 키워드 표시와 번역 기능도 사용할 수 있습니다.

## 실행 방법

필수 요구사항:
- Python 3.10+
- (생성 요약/번역에 OpenAI 사용 시) 환경 변수 `OPENAI_API_KEY`

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 기능
- 텍스트 입력 또는 파일 업로드(TXT, PDF, DOCX)
- 요약 방식 선택: 추출 요약(가벼운 문장 추출) / 생성 요약(OpenAI 또는 Transformers)
- 요약 길이 옵션: 짧게 / 중간 / 길게
- 결과 통계(단어 수, 처리 시간)
- 결과 다운로드: TXT, PDF(reportlab 필요)
- (선택) 간단 키워드 표시, 번역(OpenAI)

## 배포 (Streamlit Cloud)

### 1. GitHub에 코드 업로드
```bash
git init
git add .
git commit -m "Initial commit: 텍스트 요약 툴"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

### 2. Streamlit Cloud에서 배포
1. [Streamlit Cloud](https://streamlit.io/cloud)에 접속하여 로그인
2. "New app" 버튼 클릭
3. GitHub 리포지토리 선택
4. **Main file path**: `app.py` 입력
5. **Python version**: 3.10 이상 선택
6. "Deploy!" 클릭

### 3. API 키 설정 (선택사항)
1. Streamlit Cloud 앱 페이지에서 "Settings" → "Secrets" 클릭
2. 다음 형식으로 추가:
```toml
OPENAI_API_KEY = "your-api-key-here"
```
3. 저장 후 앱이 자동으로 재배포됩니다

### 4. 배포 확인
- 배포 완료 후 제공되는 URL로 접속하여 앱이 정상 작동하는지 확인
- OpenAI API 키를 설정했다면 생성 요약 및 번역 기능이 활성화됩니다

## 참고
- Transformers 요약은 기본적으로 `facebook/bart-large-cnn`을 사용합니다.
- 긴 문서는 내부적으로 청크 단위로 나누어 요약 후 결합합니다.
- PDF 다운로드는 `reportlab`으로 생성합니다.








