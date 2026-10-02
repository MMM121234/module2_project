"""보고서 생성: 점검 결과 JSON → (가이드 검색 + GPT) → 보고서.

[처리 순서]  점검 결과(status)의 항목마다
    VULNERABLE(취약), REVIEW(수동 확인 필요)
                      → ① 해당 항목의 가이드 검색(RAG)  ② 가이드를 근거로 GPT 가 조치방법 작성
    SAFE(양호), NA(해당 없음), ERROR(점검 오류)
                      → 그대로 기록 (GPT 를 부르지 않음: 비용 절약, 조치할 내용이 없으므로)

[UI 팀이 쓰는 방법]  (프로젝트 최상위 폴더에서 실행)
    from ai_report.report import generate_report
    report = generate_report(점검결과_dict)   # 이 함수 하나가 전부. 결과는 dict(JSON)로 돌려준다.
    # 화면 구성은 UI 팀이 report["items"] 등을 보고 자유롭게 만든다.
"""

import json

from ai_report.rag import embed, get_client, load_db

CHAT_MODEL = "gpt-4o-mini"  # 보고서를 쓰는 GPT 모델 (바꾸려면 여기만 수정)
TOP_K = 3  # 항목당 GPT 에게 보여줄 가이드 조각 개수

# AI 가 조치 내용을 작성할 status 목록 (1팀 status: SAFE | VULNERABLE | REVIEW | NA | ERROR)
AI_TARGET_STATUS = ("VULNERABLE", "REVIEW")

NO_VALUE = "(수집된 값 없음)"  # current_value 가 null 일 때 질문/프롬프트에 대신 쓰는 문구

# GPT 에게 주는 역할/규칙. 보고서 품질을 고치고 싶으면 이 문장을 수정하면 된다.
SYSTEM_PROMPT = """\
당신은 KISA 주요정보통신기반시설 기술적 취약점 분석·평가 가이드에 정통한 리눅스 보안 컨설턴트입니다.
서버 점검 결과와 [가이드 발췌]가 주어지면, 관리자가 바로 조치할 수 있게 내용을 작성하세요.

규칙:
1. [가이드 발췌]에 있는 내용만 근거로 쓰세요. 근거가 없으면 추측하지 말고 "가이드에 근거 없음"이라고 쓰세요.
2. 설정 파일을 수정하는 조치는 먼저 백업하도록 안내하세요.
3. 서비스 중단 등 부작용이 있으면 caution 에 쓰세요.
4. 한국어로 간결하게 쓰세요.
5. commands 는 조치 스크립트에 그대로 들어가므로, 설명 문장이나 설정 줄만 단독으로 쓰지 말고
   bash 에서 바로 실행되는 명령어만 한 줄씩 쓰세요. (설정 파일 수정은 sed 등 명령어로 쓰고,
   수정 전 cp 로 백업하는 명령어를 먼저 넣으세요.)
6. 아래 키를 가진 JSON 객체 하나로만 답하세요.

{
  "risk": "이 설정이 왜 위험한지 2~3문장",
  "remediation_steps": ["조치 단계 1", "조치 단계 2"],
  "commands": ["bash 에서 그대로 실행 가능한 명령어"],
  "verification": "조치가 잘 적용됐는지 확인하는 방법",
  "caution": "주의사항 (없으면 빈 문자열)"
}
"""


def generate_report(scan: dict) -> dict:
    """점검 결과(dict)를 받아 보고서(dict)를 돌려준다."""
    client = get_client()
    db = load_db(client)  # 벡터DB 준비 (없으면 자동 생성)
    os_version = scan["target_info"].get("os_version", "Linux")

    items = []
    for result in scan["results"]:
        item = dict(result)  # 1팀이 준 항목 정보를 그대로 복사
        item["ai"] = None  # GPT 가 쓴 조치 내용 (AI 작성 대상이 아닌 항목은 None)
        item["guide_used"] = []  # 근거로 쓴 가이드 조각
        item["error"] = ""  # AI 작성에 실패했을 때 이유 (1팀 점검 오류는 status="ERROR" 로 구분)

        if result["status"] in AI_TARGET_STATUS:
            code = result["item_code"]
            print(f"[{code}] {result['item_name']} - AI 작성 중...")
            try:
                # (1) 검색: 현재 상태를 질문 삼아 비슷한 가이드 찾기
                current = result["current_value"] or NO_VALUE  # null 이면 "None" 이 아닌 안내 문구 사용
                question = f"{code} {result['item_name']} {current} {result['reason']}"
                query_vector = embed(client, [question])[0]
                guides = db.search(query_vector, code, TOP_K)
                item["guide_used"] = guides

                # (2) 생성: 찾은 가이드를 근거로 GPT 가 작성
                item["ai"] = ask_gpt(client, os_version, result, guides)
            except Exception as e:  # 한 항목이 실패해도 나머지 보고서는 계속 만든다
                item["error"] = str(e)
                print(f"[{code}] 실패: {e}")
        items.append(item)

    return {
        "target_info": scan["target_info"],
        "diagnosis_standard": scan.get("diagnosis_standard", {}),
        "summary": scan.get("summary", {}),
        "items": items,
        # 항목별 조치 명령어를 모은 복사용 bash 스크립트 (UI 에서 st.code 로 보여주면 복사 버튼이 생김)
        "remediation_script": make_script(scan["target_info"], items),
    }


def ask_gpt(client, os_version: str, result: dict, guides: list[dict]) -> dict:
    """항목 하나에 대해 GPT 에게 조치 내용을 물어보고 JSON(dict)으로 돌려받는다."""
    guide_text = "\n\n".join(f"({i}) [{g['section']}] {g['text']}" for i, g in enumerate(guides, 1))
    # 호스트명/IP 는 외부(OpenAI)로 보내지 않는다. OS 버전과 점검 결과만 보낸다.
    user_prompt = f"""\
[대상 OS] {os_version}
[점검 항목] {result['item_code']} {result['item_name']}
[판정] {result['status']}
[현재 설정값] {result['current_value'] or NO_VALUE}
[판정 사유] {result['reason']}

[가이드 발췌]
{guide_text or '(검색된 가이드 없음)'}

위 내용을 바탕으로 JSON 으로 답하세요."""

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,  # 낮을수록 답변이 일정함
        response_format={"type": "json_object"},  # JSON 으로만 답하게 강제
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def make_script(target_info: dict, items: list[dict]) -> str:
    """AI 가 만든 조치 명령어들을 모아 '복사해서 쓸 수 있는' bash 스크립트(문자열)로 만든다.

    이 프로그램이 서버에서 실행하는 것이 아니라, 사용자가 화면에서 복사해 가져다 쓰는 용도다.
    그래서 붙여넣기 해도 터미널이 닫히거나 입력을 기다리지 않도록 exit, read 같은 명령은 넣지 않고
    항목별 설명 주석 + 명령어만 담는다.
    """
    t = target_info
    lines = [
        "#!/bin/bash",
        "# ============================================================",
        "# AI 가 생성한 취약점 조치 스크립트 (자동 생성 - 반드시 검토 후 사용하세요)",
        f"# 대상: {t.get('target_host')} / {t.get('os_version')}",
        "# 운영 서버에 적용하기 전에 테스트 서버에서 먼저 확인하세요.",
        "# ============================================================",
        "",
    ]
    for it in items:
        ai = it["ai"]
        if not ai or not ai.get("commands"):
            continue  # 양호 항목, AI 실패 항목, 명령어가 없는 항목은 제외

        lines += [f"# ===== {it['item_code']} {it['item_name']} ====="]
        if ai.get("caution"):
            lines += [f"# 주의: {c}" for c in ai["caution"].splitlines()]
        lines += ai["commands"]
        lines.append("")
    return "\n".join(lines)
