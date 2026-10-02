# module2_project
생성형 AI 기반의 주요정보통신기반시설 취약점 진단 및 맞춤형 보고서 자동화 플랫폼

**KISA 주요정보통신가이드 기반 리눅스 OS 서버 점검 보고서 AI 자동화**

## 팀별 작업 폴더

| 팀 | 역할 | 작업 폴더 |
|---|---|---|
| 1팀 | OS 점검 스크립트 → 점검 결과 JSON·Excel 생성 | `scanner/` |
| 2팀 | 환경구성 및 Streamlit UI | `ui/` (최상위에 `app.py`) |
| 3팀 | AI 가이드 및 RAG (KISA 가이드 검색 + GPT 보고서) | `ai_report/` |

- **자기 팀 폴더만 수정**하고, 다른 팀 폴더는 건드리지 않습니다.
- 폴더 이름과 위치는 팀 협의 후 바꿔도 됩니다. (3팀 코드는 `ai_report/` 안의 `import` 경로만 같이 바꾸면 됩니다.)
- 공용 파일: `requirements.txt`(패키지 목록), `.env`(API 키), `.gitignore`

```
.
├─ scanner/            1팀
├─ ui/                 2팀
├─ ai_report/          3팀
│  ├─ main.py             터미널 실행용 (JSON → 보고서 파일 저장)
│  ├─ report.py           항목마다 가이드 검색 + GPT 호출, 보고서/스크립트 생성
│  ├─ rag.py              벡터DB (가이드를 벡터로 저장하고 비슷한 것 찾기)
│  └─ data/
│     ├─ guide_chunks.json   전처리한 KISA 가이드
│     └─ scan_result.json    점검 결과 JSON 샘플
├─ requirements.txt
├─ .env                API 키 (Git에 올리지 않음, 팀에서 직접 공유)
└─ .gitignore
```

## 전체 흐름

```
[1팀] 점검 실행 → scan_result.json
          ↓
[2팀] Streamlit 이 JSON 을 읽어 generate_report(dict) 호출
          ↓
[3팀] 취약 항목마다 가이드 검색(RAG) → GPT 가 조치방법 작성 → 보고서(dict)
          ↓
[2팀] 화면에 표시
```

## 팀 간 약속 (인터페이스)

**1팀 → 3팀: 점검 결과 JSON**
- 최상위: `target_info`, `diagnosis_standard`, `summary`, `results`
- `results` 의 각 항목 필수 키: `item_code`, `item_name`, `status`, `current_value`, `reason`
- `item_code` 는 `U-01` 형식, `status` 가 `SAFE` 가 아니면 모두 AI 조치 작성 대상
- 샘플: `ai_report/data/scan_result.json`

**3팀 → 2팀: 함수 1개** (프로젝트 최상위 폴더에서 실행). 결과는 JSON(dict) 하나이며, 화면 구성은 2팀이 자유롭게 합니다.

```python
import streamlit as st
from ai_report.report import generate_report

with st.spinner("AI 보고서 작성 중..."):                # 취약 항목 수만큼 GPT 호출 → 시간이 걸림
    report = generate_report(점검결과_dict)

for item in report["items"]:                            # 항목별 화면 구성 예시
    if item["ai"]:
        st.write(item["ai"]["risk"])
st.code(report["remediation_script"], language="bash")  # 조치 스크립트 (코드 박스 복사 버튼 제공)
```

`report` (dict) 구조:
```
target_info, diagnosis_standard, summary      ← 1팀 JSON 그대로
items[]: item_code, category, item_name, status, current_value, reason   ← 1팀 항목 그대로
         ai: {risk, remediation_steps[], commands[], verification, caution}  (양호 항목은 null)
         guide_used[]: 근거로 쓴 가이드 원문
         error: 실패 사유 (정상이면 "")
remediation_script: 항목별 조치 명령어를 모은 bash 스크립트 텍스트 (복사해서 사용)
```

## 3팀 실행 방법

```bash
pip install -r requirements.txt
```

프로젝트 **최상위 폴더**에 `.env` 파일을 만들고 공유받은 키를 넣습니다.
```
OPENAI_API_KEY=공유받은키
```

```bash
python -m ai_report.main                  # 결과: ai_report/outputs/report.json
python -m ai_report.main 다른파일.json     # 다른 점검 결과로 실행
```

- 벡터DB(`ai_report/data/vector_db.json`)는 처음 실행할 때 자동 생성되고, `guide_chunks.json`을 수정하면 다음 실행 때 자동으로 다시 만들어집니다.
- 보고서 작성 모델: `ai_report/report.py` 상단 `CHAT_MODEL`
- 임베딩 모델: `ai_report/rag.py` 상단 `EMBED_MODEL`

## 가이드 전처리 형식 (`ai_report/data/guide_chunks.json`)

```json
[
  { "item_code": "U-01", "section": "조치방법", "text": "가이드 내용..." }
]
```

현재 파일은 **AI 가 작성한 초안**입니다(`source` 필드 참고). KISA 원문 기반 전처리 결과가 준비되면 교체하세요.

## 조치 스크립트

`report["remediation_script"]` 는 AI 가 만든 조치 명령어를 모아 bash 스크립트 **텍스트**로 담은 값입니다.
프로그램이 서버에서 실행하는 것이 아니라 사용자가 복사해서 쓰는 용도이며, 반드시 검토 후 테스트 서버에서 먼저 사용하세요.
