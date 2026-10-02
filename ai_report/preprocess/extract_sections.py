"""
[전처리 1단계] 가이드 PDF(쪽 범위로 자른 것) → 항목(U-XX)별 '편집용 txt'

흐름:
  guide_pdfs/*.pdf          (가이드 원문을 쪽 범위로 자른 PDF. 한 파일에 항목 여러 개가 들어 있어도 됨)
        │ 추출(pdfplumber) — 머리말/꼬리말은 좌표로 잘라내고, 항목 표는 칸 단위로 읽는다
        ▼
  01_raw/<PDF이름>.txt      (날것 — 쪽별 추출 결과 확인용)
        │ 항목(U-XX) 단위로 나누고 섹션 분리
        ▼
  02_sections/U-01.txt      (★ 여기서 눈으로 확인하고 손으로 고친다 ★)

02_sections/*.txt 를 확인·수정한 뒤 build_chunks.py 를 돌리면 guide_chunks.json 이 나온다.

[가이드 PDF 구조]  항목마다 아래 모양이다.
  ┌ 표 ─────────────────────────────────────────┐
  │ U-01 (상) │ UNIX > 1. 계정 관리 / 항목 이름   │
  │ 개요                                          │
  │ 점검 내용 │ ...      점검 목적 │ ...          │
  │ 보안 위협 │ ...      참고      │ ...          │
  │ 점검 대상 및 판단 기준                         │
  │ 대상 │ ...  판단 기준 │ 양호/취약  조치 방법 │ ... 조치 시 영향 │ ... │
  └─────────────────────────────────────────────┘
  점검 및 조치 사례   (표 밖, 여러 쪽에 걸침)
  l SOLARIS / l LINUX / l AIX / l HP-UX  ← OS별 Step 1) ... 명령어

  표를 그냥 extract_text 하면 왼쪽 칸 제목이 오른쪽 글 사이에 끼어 섞이므로,
  표는 줄(row)마다 '제목 칸'과 '내용 칸'을 따로 잘라 읽는다.

실행:  (ai_report/preprocess/ 폴더에서)
    python extract_sections.py
"""

import re
from pathlib import Path

import pdfplumber

# ---------------- 설정 ----------------
BASE = Path(__file__).parent
PDF_DIR = BASE / "guide_pdfs"      # 가이드 PDF 폴더 (쪽 범위로 잘라 넣는다)
RAW_DIR = BASE / "01_raw"          # 날것 txt
SEC_DIR = BASE / "02_sections"     # 섹션 분리 txt (편집 대상)

# 머리말/꼬리말 잘라낼 위치 (pt). 머리말 "2026 / 주요정보통신기반시설… / 01. Unix 서버"
# 또는 "| 한국인터넷진흥원 |" 은 y≈22~75, 쪽번호는 y≈788 에 있다.
BODY_TOP = 80
BODY_BOTTOM = 780

ITEM_CODE = re.compile(r"^U-(\d{2,3})")          # 항목 표 첫 칸: "U-01\n(상)"
OS_LINE = re.compile(r"^l\s+([A-Z][A-Z0-9\-, ]+)$")  # "l LINUX", "l SOLARIS, LINUX, AIX, HP-UX"
CASE_TITLE = "점검 및 조치 사례"

# 섹션 제목 줄 형식. 본문에 [SSH], [Telnet] 같은 줄이 있어서 '[...]' 는 쓰지 않는다.
SEC_MARK = "==== {} ===="

# 꼭 있어야 하는 섹션 (없으면 경고만 — 삭제하지 않음)
REQUIRED = ["판단기준", "조치방법"]


def norm(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "")


def clean(text: str) -> str:
    """공백만 정리한다. 명령어/설정값(알맹이)과 줄바꿈은 건드리지 않는다."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def cell_text(page, bbox) -> str:
    x0, top, x1, bottom = bbox
    if x1 - x0 < 1 or bottom - top < 1:
        return ""
    return (page.within_bbox((x0, top, x1, bottom)).extract_text() or "").strip()


def read_item_table(page, table) -> dict:
    """항목 표 하나 → {'code', 'level', 'category', 'title', 'fields': {제목: 내용}}"""
    x_right = table.bbox[2]
    rows = table.rows
    first = cell_text(page, rows[0].cells[0])  # "U-01\n(상)"
    code = f"U-{int(ITEM_CODE.match(first).group(1)):02d}"
    level = (re.search(r"\((.)\)", first) or [None, ""])[1]
    category = cell_text(page, rows[0].cells[1]) if len(rows[0].cells) > 1 and rows[0].cells[1] else ""
    title = cell_text(page, rows[1].cells[-1]) if len(rows) > 1 and rows[1].cells[-1] else ""

    fields: dict[str, str] = {}
    for row in rows[2:]:
        label_cell = row.cells[0]
        if not label_cell:
            continue
        # 제목 칸이 표 전체 폭이면 그룹 제목("개요", "점검 대상 및 판단 기준") → 건너뜀
        if label_cell[2] >= x_right - 1:
            continue
        label = cell_text(page, label_cell).replace("\n", " ")
        value = cell_text(page, (label_cell[2], row.bbox[1], x_right, row.bbox[3]))
        if label:
            fields[label] = clean(value)
    return {"code": code, "level": level, "category": category, "title": title, "fields": fields}


def table_as_text(page, table) -> str:
    """항목 표가 아닌 일반 표(권고값 표 등)는 '칸 | 칸' 줄로 바꾼다.
    가이드 표는 오른쪽 세로선이 없어 본문 줄의 마지막 칸이 인식되지 않으므로,
    첫 줄(제목 줄)의 칸 경계를 모든 줄에 적용해서 잘라 읽는다."""
    cols = [(c[0], c[2]) for c in table.rows[0].cells if c]
    cols[-1] = (cols[-1][0], table.bbox[2])
    out = []
    for row in table.rows:
        cells = [re.sub(r"\s*\n\s*", " ", cell_text(page, (x0, row.bbox[1], x1, row.bbox[3])))
                 for x0, x1 in cols]
        if any(cells):
            out.append(" | ".join(cells))
    return "\n".join(out)


def read_pdf(pdf_path: Path, raw_lines: list[str]) -> list[dict]:
    """PDF 하나 → 항목 목록. 각 항목에 'case' (점검 및 조치 사례 본문) 를 붙인다."""
    items: list[dict] = []
    orphan: list[str] = []  # 첫 항목 표보다 앞에 있는 글 (이전 PDF 에서 이어지는 내용 → 버림)

    def add_text(t: str):
        if not t.strip():
            return
        (items[-1]["case"] if items else orphan).append(t)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            body = page.crop((0, BODY_TOP, page.width, BODY_BOTTOM))
            raw_lines += [f"----- p.{page.page_number} -----", body.extract_text() or ""]

            cursor = BODY_TOP
            for table in sorted(body.find_tables(), key=lambda t: t.bbox[1]):
                add_text(cell_text(body, (0, cursor, page.width, table.bbox[1])))
                first = cell_text(body, table.rows[0].cells[0]) if table.rows[0].cells[0] else ""
                if ITEM_CODE.match(first):
                    item = read_item_table(body, table)
                    item["case"] = []
                    items.append(item)
                else:
                    add_text(table_as_text(body, table))
                cursor = table.bbox[3]
            add_text(cell_text(body, (0, cursor, page.width, BODY_BOTTOM)))

    if orphan:
        print(f"  [i] {pdf_path.name}: 첫 항목 앞 내용 {sum(len(t) for t in orphan)}자는 항목을 알 수 없어 버림")
    return items


def split_by_os(text: str) -> list[tuple[str, str]]:
    """'점검 및 조치 사례' 본문을 OS 줄(l LINUX 등) 기준으로 나눈다."""
    secs: list[tuple[str, list[str]]] = [("조치사례", [])]
    for line in text.splitlines():
        if norm(line) == norm(CASE_TITLE):
            continue
        m = OS_LINE.match(line.strip())
        if m:
            secs.append((f"조치사례({m.group(1).strip()})", []))
        else:
            secs[-1][1].append(line)
    return [(name, clean("\n".join(body))) for name, body in secs if clean("\n".join(body))]


def build_sections(item: dict) -> list[tuple[str, str]]:
    f = item["fields"]
    get = lambda *keys: next((f[k] for k in f if norm(k) in map(norm, keys)), "")

    def join(*pairs):
        return "\n".join(f"{k}: {v}" for k, v in pairs if v)

    head = f"{item['code']} {item['title']} (중요도: {item['level']}, {item['category']})"
    secs = [
        ("개요", head + "\n" + join(
            ("점검 내용", get("점검 내용")), ("점검 목적", get("점검 목적")),
            ("보안 위협", get("보안 위협")), ("참고", get("참고")))),
        ("판단기준", join(("대상", get("대상")), ("판단 기준", get("판단 기준")))),
        ("조치방법", join(("조치 방법", get("조치 방법")), ("조치 시 영향", get("조치 시 영향")))),
    ]
    # 표에 위에서 처리하지 않은 칸이 있으면 잃어버리지 않게 따로 남긴다
    known = {norm(k) for k in ("점검 내용", "점검 목적", "보안 위협", "참고", "대상", "판단 기준", "조치 방법", "조치 시 영향")}
    extra = [(k, v) for k, v in f.items() if norm(k) not in known]
    if extra:
        secs.append(("기타", join(*extra)))
    secs += split_by_os("\n".join(item["case"]))
    return [(n, b) for n, b in secs if b.strip()]


def main():
    RAW_DIR.mkdir(exist_ok=True)
    SEC_DIR.mkdir(exist_ok=True)

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[!] {PDF_DIR} 에 PDF 가 없습니다. 가이드 PDF 를 넣어주세요.")
        return

    seen: dict[str, str] = {}
    for pdf_path in pdfs:
        raw_lines: list[str] = []
        items = read_pdf(pdf_path, raw_lines)
        (RAW_DIR / f"{pdf_path.stem}.txt").write_text("\n".join(raw_lines), encoding="utf-8")
        print(f"{pdf_path.name}: 항목 {[it['code'] for it in items]}")

        for item in items:
            code = item["code"]
            if code in seen:
                print(f"  ⚠ {code} 가 {seen[code]} 에도 있음 → 나중 것으로 덮어씀")
            seen[code] = pdf_path.name

            secs = build_sections(item)
            lines = [f"# {code}  (이 줄은 건드리지 마세요)", ""]
            for name, body in secs:
                lines += [SEC_MARK.format(name), body, ""]
            (SEC_DIR / f"{code}.txt").write_text("\n".join(lines), encoding="utf-8")

            found = [n for n, _ in secs]
            missing = [r for r in REQUIRED if r not in found]
            flag = f"   ⚠ 누락:{missing}" if missing else ""
            print(f"  [{code}] {item['title']}  섹션 {found}{flag}")

    print("\n완료.")
    print(f"  1) {RAW_DIR}/*.txt 로 PDF 추출 상태를 확인")
    print(f"  2) {SEC_DIR}/*.txt 를 열어 섹션 경계·표·끊긴 명령어를 손으로 고침")
    print("  3) python build_chunks.py 실행")


if __name__ == "__main__":
    main()
