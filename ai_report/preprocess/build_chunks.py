"""
[전처리 2단계] 확인·수정한 02_sections/*.txt → guide_chunks.json

02_sections 의 txt 를 눈으로 확인·수정한 뒤 실행한다.
각 txt 의 '==== 섹션 ====' 블록 하나가 guide_chunks.json 의 조각(chunk) 하나가 된다.
(본문에 [SSH], [Telnet] 같은 줄이 있어서 섹션 제목은 '[...]' 가 아니라 '==== ... ====' 로 표시한다.)
출력 위치는 rag.py 가 읽는 ai_report/data/guide_chunks.json 과 정확히 일치한다.

실행:  (ai_report/preprocess/ 폴더에서)
    python build_chunks.py
"""

import json
import re
from pathlib import Path

# ---------------- 설정 ----------------
BASE = Path(__file__).parent
SEC_DIR = BASE / "02_sections"
OUT = BASE.parent / "data" / "guide_chunks.json"  # = ai_report/data/guide_chunks.json

SOURCE = "KISA 주요정보통신기반시설 기술적 취약점 분석·평가 상세가이드(2026)"
DROP_SECTIONS = {"전체"}  # 아직 수동 분리 안 한 임시 섹션은 JSON 에서 제외
MIN_LEN = 15              # 이보다 짧은 본문은 경고 (깨짐 의심)


def parse(txt: str) -> tuple[str, list[tuple[str, str]]]:
    """txt 하나를 (항목코드, [(섹션, 본문), ...]) 로 파싱."""
    code_m = re.match(r"\s*#\s*(U-\d{2,3})", txt)  # 첫 줄의 '# U-01'
    code = code_m.group(1) if code_m else "UNKNOWN"
    # '==== name ====' 을 구분자로 쪼개면 [앞부분, name1, body1, name2, body2, ...]
    parts = re.split(r"^={3,}\s*(.+?)\s*={3,}\s*$", txt, flags=re.M)[1:]
    secs = [(parts[i].strip(), parts[i + 1].strip()) for i in range(0, len(parts) - 1, 2)]
    return code, secs


def main():
    if not SEC_DIR.exists():
        print(f"[!] {SEC_DIR} 가 없습니다. 먼저 extract_sections.py 를 실행하세요.")
        return

    chunks, warns = [], []
    for path in sorted(SEC_DIR.glob("*.txt")):
        code, secs = parse(path.read_text(encoding="utf-8"))
        if code == "UNKNOWN":
            warns.append(f"{path.name}: 항목코드(# U-XX) 줄이 없음")
        if not secs:
            warns.append(f"{code}: 섹션(==== ... ====)을 못 찾음")
        for name, body in secs:
            if name in DROP_SECTIONS:
                warns.append(f"{code}: '{name}' 섹션은 아직 수동 분리 전 → 제외됨")
                continue
            if len(body) < MIN_LEN:
                warns.append(f"{code}/{name}: 본문이 너무 짧음({len(body)}자) — 깨짐 의심")
            chunks.append({"item_code": code, "section": name, "text": body, "source": SOURCE})

    # (item_code, section) 중복 점검
    seen: dict[tuple[str, str], int] = {}
    for c in chunks:
        k = (c["item_code"], c["section"])
        seen[k] = seen.get(k, 0) + 1
    for (ic, sec), n in seen.items():
        if n > 1:
            warns.append(f"{ic}/{sec}: 같은 섹션 {n}개 (의도한 분할이면 무시)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    codes = sorted({c["item_code"] for c in chunks})
    print(f"조각 {len(chunks)}개 → {OUT}")
    print(f"항목 {len(codes)}개: {codes}")

    # 필수 섹션 누락 점검 (항목별로 판단기준·조치방법이 있는지)
    for ic in codes:
        secs_of = {c["section"] for c in chunks if c["item_code"] == ic}
        for need in ("판단기준", "조치방법"):
            if need not in secs_of:
                warns.append(f"{ic}: '{need}' 섹션 없음 → 조치 품질 저하 가능")

    if warns:
        print("\n확인 필요:")
        for w in warns:
            print(" -", w)
    else:
        print("\n경고 없음. 바로 rag.py 에서 사용 가능합니다.")


if __name__ == "__main__":
    main()