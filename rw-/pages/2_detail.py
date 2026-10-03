import html
import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="항목 상세", page_icon="🛡️", layout="wide")

DASHBOARD_PAGE = "pages/1_dash.py"

# report.json 위치 후보 (위에서부터 먼저 발견되는 파일 사용)
HERE = Path(__file__).resolve().parent
REPORT_CANDIDATES = [
    Path("data/report.json"),
    Path("report.json"),
    HERE.parent / "data" / "report.json",
    HERE.parent / "report.json",
    HERE / "report.json",
]


# ---------------------------------------------------------------
# 0. report.json 읽기
# ---------------------------------------------------------------
@st.cache_data
def load_report(path_str):
    with open(path_str, encoding="utf-8") as f:
        return json.load(f)


report_path = next((p for p in REPORT_CANDIDATES if p.exists()), None)
if report_path is None:
    st.error("report.json 파일을 찾을 수 없어요. 아래 위치 중 한 곳에 넣어주세요.")
    st.code("\n".join(str(p) for p in REPORT_CANDIDATES))
    st.stop()

report = load_report(str(report_path))
info = report.get("target_info", {})
items = report.get("items", [])

if not items:
    st.warning("report.json에 점검 항목(items)이 없어요.")
    st.stop()


def esc(v):
    """값을 HTML에 넣기 전에 꼭 거치는 함수 (XSS 방지)"""
    return html.escape(str(v if v is not None else "-"))


def esc_br(v):
    """이스케이프 + 줄바꿈을 <br>로 (마크다운이 빈 줄에서 HTML을 끊지 않도록 한 줄로 만듦)"""
    return esc(v).replace("\r", "").replace("\n", "<br>")


def clean_cat(c):
    """'1. 계정 관리' → '계정 관리'"""
    return re.sub(r"^\d+\.\s*", "", c or "")


# ---------------------------------------------------------------
# 1. 어떤 항목을 보여줄지 결정
#    우선순위: 주소의 ?code=U-01 → session_state["selected_code"] → 첫 번째 취약 항목 → 첫 항목
# ---------------------------------------------------------------
code = st.query_params.get("code") or st.session_state.get("selected_code")
item = next((r for r in items if r.get("item_code") == code), None)
if item is None:
    item = next((r for r in items if r.get("status") == "VULNERABLE"), items[0])

status = item.get("status")
ai = item.get("ai") or {}
guides = item.get("guide_used") or []

STATUS = {
    "VULNERABLE": ("취약", "#FBE9DF", "#8A3109"),
    "SAFE": ("양호", "#E3E9FB", "#1A3794"),
    "REVIEW": ("수동 확인", "#FBF0D2", "#6B4E06"),
    "NA": ("해당 없음", "#ECEDEA", "#4A4E57"),
    "ERROR": ("점검 오류", "#ECEDEA", "#4A4E57"),
}
s_label, s_bg, s_fg = STATUS.get(status, (status, "#ECEDEA", "#4A4E57"))


# ---------------------------------------------------------------
# 2. report.json → 화면용 값 정리
# ---------------------------------------------------------------
def guide_section(name_part):
    """guide_used 중 section 이름에 name_part가 들어간 첫 번째 text"""
    for g in guides:
        if name_part in (g.get("section") or ""):
            return g.get("text") or ""
    return ""


overview = guide_section("개요")

# 위험도: KISA 개요 첫 줄의 '(중요도: 상, ...)' 에서 추출
m = re.search(r"중요도:\s*([상중하])", overview)
severity = m.group(1) if m else None

# 제목 아래 설명: KISA 개요의 '점검 내용' 한 줄 (없으면 판정 사유)
m = re.search(r"점검 내용:\s*(.+)", overview)
desc = m.group(1).strip() if m else (item.get("reason") or "-")

# 양호 기준: KISA '판단기준' 항목에서 '양호 : ...' 부분 추출 (없으면 줄 숨김)
criteria = ""
m = re.search(r"양호\s*:\s*(.+?)(?:\n※|\n취약|$)", guide_section("판단기준"), re.S)
if m:
    criteria = re.sub(r"\s+", " ", m.group(1)).strip()

current = item.get("current_value") or "-"

if status == "VULNERABLE":
    verdict = "기준과 다르므로 <b>취약</b> (스크립트 자동 판정)"
elif status == "SAFE":
    verdict = "기준과 같으므로 <b>양호</b> (스크립트 자동 판정)"
elif status == "REVIEW":
    verdict = "<b>수동 확인</b> 필요 (AI 1차 분석 참고)"
else:
    verdict = f"<b>{esc(s_label)}</b>"
cur_color = "#9A3A0B" if status == "VULNERABLE" else "#1A3794"

# KISA 가이드 근거: 다른 OS(AIX · HP-UX · SOLARIS) 전용 조치사례는 제외
OTHER_OS = ("AIX", "HP-UX", "SOLARIS")
shown = [g for g in guides
         if not (any(o in (g.get("section") or "") for o in OTHER_OS) and "LINUX" not in (g.get("section") or ""))]
if shown:
    parts = []
    for i, g in enumerate(shown):
        parts.append(f'<details{" open" if i == 0 else ""}><summary>{esc(g.get("section"))}</summary>'
                     f'<div class="gtxt">{esc_br(g.get("text"))}</div></details>')
    guide_html = f'<div class="guide">{"".join(parts)}</div>'
    kisa_source = "출처: " + (shown[0].get("source") or "KISA 주요정보통신기반시설 기술적 취약점 분석·평가 상세가이드(2026)")
else:
    guide_html = '<div class="guide"><div class="gtxt" style="padding:10px 0">이 항목은 검색된 KISA 가이드 근거가 없어요.</div></div>'
    kisa_source = "출처: -"

# AI 조치 스크립트: 단계 설명을 주석으로, 그 아래에 명령어, 마지막에 확인 방법
script_lines = []
for i, step in enumerate(ai.get("remediation_steps") or [], 1):
    script_lines.append(f"# {i}. {step}")
if script_lines:
    script_lines.append("")
script_lines += ai.get("commands") or []
if ai.get("verification"):
    script_lines += ["", f"# 적용 확인: {ai['verification']}"]
script = "\n".join(script_lines) if ai.get("commands") else ""

if script:
    ln_html = []
    for ln in script.split("\n"):
        cls = "ln c" if ln.lstrip().startswith("#") else "ln"
        ln_html.append(f'<div class="{cls}">{esc(ln) if ln else "&nbsp;"}</div>')
    script_html = "".join(ln_html)
else:
    script_html = '<div class="ln c"># 이 항목은 AI 조치 스크립트가 없어요. (AI 분석 대상이 아니에요)</div>'

caution = ai.get("caution") or ""

# 보고 대상별 요약: 엔지니어 = 조치 단계, 경영진 = 위험 설명
sum_eng = " ".join(ai.get("remediation_steps") or []) or "-"
sum_exec = ai.get("risk") or "-"

# ---------------------------------------------------------------
# 3. 디자인(CSS)
# ---------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
    .stApp { background:#F3F4F1; }
    .stApp, .stApp p, .stApp label, .stApp button { font-family:'IBM Plex Sans KR', sans-serif; color:#16181D; }
    .stApp [data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded' !important; }
    header[data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none; }
    .block-container { max-width:1280px; padding-top:0; padding-bottom:64px; }
    .mono { font-family:'IBM Plex Mono', monospace; }

    /* 상단 바 (화면 전체 너비) */
    .topbar { background:#16181D; margin:-16px calc(50% - 50vw) 0; padding:0 calc(50vw - 50% + 1rem); }
    .topbar-in { height:64px; display:flex; align-items:center; justify-content:space-between; gap:24px; }
    .brand { display:flex; align-items:center; gap:12px; color:#F3F4F1; font-weight:600; font-size:16px; }
    .logo { width:32px; height:32px; border-radius:6px; background:#1E3FAE; color:#fff; display:flex;
            align-items:center; justify-content:center; font-family:'IBM Plex Mono', monospace; font-size:13px; }
    .nav { display:flex; gap:4px; }
    .nav span { color:#B9BCC4; padding:10px 14px; border-radius:6px; font-size:14px; }
    .nav span.on { color:#fff; background:#2A2D35; }
    .srvinfo { font-family:'IBM Plex Mono', monospace; font-size:12px; color:#B9BCC4; }

    /* 돌아가기 링크 */
    .st-key-back { margin-top:28px; }
    .st-key-back button { background:transparent; border:none; padding:0; min-height:0; box-shadow:none; }
    .st-key-back button p { color:#1E3FAE; font-size:14px; font-weight:400; }
    .st-key-back button:hover p { text-decoration:underline; }

    /* 제목 카드 */
    .head { background:#fff; border:1px solid #DCDED8; border-radius:12px; padding:26px 30px 28px;
            display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-top:8px; }
    .head .meta { display:flex; align-items:center; gap:10px; font-size:13px; color:#4A4E57; }
    .badge-code { background:#16181D; color:#fff; font-family:'IBM Plex Mono', monospace; font-size:14px;
                  font-weight:500; padding:6px 10px; border-radius:6px; }
    .head .t { font-size:30px; font-weight:700; letter-spacing:-0.5px; margin:18px 0 12px; color:#16181D; }
    .head .d { font-size:15px; color:#4A4E57; }
    .pill-lg { display:inline-block; padding:12px 18px; border-radius:999px; font-size:15px; font-weight:700;
               white-space:nowrap; margin-top:10px; }

    /* 카드 공통 */
    .card { background:#fff; border:1px solid #DCDED8; border-radius:12px; padding:26px 28px;
            min-height:232px; box-sizing:border-box; }
    .card .ch { margin:0 0 20px; font-size:18px; font-weight:600; display:flex; justify-content:space-between;
                align-items:center; gap:12px; color:#16181D; }
    .tag { font-size:12px; font-weight:400; color:#4A4E57; background:#E8EAE4; padding:5px 10px; border-radius:6px; }
    .kv { display:flex; gap:20px; align-items:baseline; padding:7px 0; font-size:14px; color:#16181D; }
    .kv .k { width:84px; flex-shrink:0; color:#6A6E76; font-size:14px; }
    .kv .v { font-family:'IBM Plex Mono', monospace; font-size:13px; word-break:break-all; }
    .kv .v.plain { font-family:'IBM Plex Sans KR', sans-serif; font-size:14px; word-break:keep-all; }

    /* KISA 가이드 근거 (점선 상자 · 섹션별 펼치기) */
    .guide { border:1px dashed #C9CCC4; border-radius:6px; padding:4px 16px; max-height:300px; overflow-y:auto; }
    .guide details + details { border-top:1px solid #ECEDEA; }
    .guide summary { cursor:pointer; font-size:13px; font-weight:600; color:#16181D; padding:10px 0; }
    .gtxt { font-size:13px; line-height:1.65; color:#4A4E57; padding-bottom:12px; }
    .src { font-size:12px; color:#6A6E76; margin-top:16px; }

    /* AI 조치 스크립트 카드 */
    .st-key-script_card { background:#fff; border:1px solid #DCDED8; border-radius:12px; overflow:hidden;
                          gap:0; margin-top:8px; }
    .st-key-script_head { padding:18px 28px; }
    .st-key-script_head iframe { border:0; display:block; }
    .script-title { display:flex; align-items:center; gap:10px; font-size:18px; font-weight:600; color:#16181D; }
    .ai-tag { font-size:12px; font-weight:600; color:#1A3794; background:#E3E9FB; padding:4px 8px; border-radius:4px; }
    .code { background:#16181D; padding:24px 28px; }
    .code .ln { font-family:'IBM Plex Mono', monospace; font-size:13px; line-height:1.7; color:#F3F4F1;
                white-space:pre-wrap; word-break:break-all; }
    .code .ln.c { color:#8A8E96; }
    .note { padding:14px 28px; font-size:12.5px; color:#4A4E57; border-top:1px solid #DCDED8; }

    /* 보고 대상별 요약 */
    .sec-title { font-size:18px; font-weight:600; margin:32px 0 14px; color:#16181D; }
    .sum { background:#fff; border:1px solid #DCDED8; border-radius:12px; padding:22px 26px; min-height:116px;
           box-sizing:border-box; }
    .sum .who { font-size:13px; font-weight:700; color:#1A3794; margin-bottom:10px; }
    .sum .txt { font-size:14px; line-height:1.7; color:#16181D; word-break:keep-all; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 4. 상단 바
# ---------------------------------------------------------------
st.markdown(
    f"""
    <div class="topbar"><div class="topbar-in">
      <div class="brand"><div class="logo">rw-</div>간편 리눅스 보안 점검</div>
      <div class="nav"><span>대시보드</span><span class="on">항목 상세</span></div>
      <div class="srvinfo">{esc(info.get("target_host", "-"))} · {esc(info.get("os_version", "-"))}</div>
    </div></div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 5. 돌아가기 + 제목 카드
# ---------------------------------------------------------------
with st.container(key="back"):
    if st.button("← 전체 결과로 돌아가기", type="tertiary"):
        st.switch_page(DASHBOARD_PAGE)

meta_txt = clean_cat(item.get("category")) + (f" · 위험도 {severity}" if severity else "")
st.markdown(
    f"""<div class="head"><div>
      <div class="meta"><span class="badge-code">{esc(item.get("item_code"))}</span><span>{esc(meta_txt)}</span></div>
      <div class="t">{esc(item.get("item_name"))}</div>
      <div class="d">{esc(desc)}</div>
    </div>
    <span class="pill-lg" style="background:{s_bg};color:{s_fg}">{esc(s_label)}</span></div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 6. 판정 근거 / KISA 가이드 근거
# ---------------------------------------------------------------
st.write("")
criteria_row = (f'<div class="kv"><span class="k">양호 기준</span>'
                f'<span class="v plain" style="color:#1A3794">{esc(criteria)}</span></div>') if criteria else ""

c1, c2 = st.columns(2)
c1.markdown(
    f"""
      <div class="card"><div class="ch">판정 근거</div>
      <div class="kv"><span class="k">점검 대상</span><span class="v">{esc(info.get("target_host"))} ({esc(info.get("ip_address"))})</span></div>
      <div class="kv"><span class="k">점검 시각</span><span class="v">{esc(info.get("scan_time"))}</span></div>
      <div class="kv"><span class="k">현재 값</span><span class="v" style="color:{cur_color}">{esc(current)}</span></div>
      {criteria_row}
      <div class="kv"><span class="k">판정</span><span class="v">{verdict}</span></div></div>
      """,
    unsafe_allow_html=True,
)
c2.markdown(
    f"""<div class="card"><div class="ch">KISA 가이드 근거<span class="tag">RAG 검색 결과</span></div>
      {guide_html}
      <div class="src">{esc(kisa_source)}</div></div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 7. AI 조치 스크립트 (복사 버튼 포함)
# ---------------------------------------------------------------
copy_js_text = json.dumps(script).replace("</", "<\\/")
copy_button = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@600&display=swap');
  html, body {{ margin:0; background:transparent; }}
  body {{ display:flex; justify-content:flex-end; align-items:center; height:44px; }}
  button {{ font-family:'IBM Plex Sans KR', sans-serif; font-weight:600; font-size:14px; color:#16181D;
            background:#fff; border:1px solid #16181D; border-radius:8px; padding:0 20px; height:42px; cursor:pointer; }}
  button:hover {{ background:#F3F4F1; }}
</style>
<button id="b">복사</button>
<script>
  const text = {copy_js_text};
  const b = document.getElementById("b");
  b.onclick = async () => {{
    try {{ await navigator.clipboard.writeText(text); }}
    catch (e) {{
      const t = document.createElement("textarea"); t.value = text;
      document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
    }}
    b.textContent = "복사됨";
    setTimeout(() => b.textContent = "복사", 1500);
  }};
</script>
"""

with st.container(key="script_card"):
    with st.container(key="script_head"):
        h1, h2 = st.columns([4, 1], vertical_alignment="center")
        h1.markdown('<div class="script-title">AI 조치 스크립트'
                    '<span class="ai-tag">AI 생성 · 적용 전 검토</span></div>',
                    unsafe_allow_html=True)
        if script:
            with h2:
                components.html(copy_button, height=44)
    st.markdown(f'<div class="code">{script_html}</div>', unsafe_allow_html=True)
    if caution:
        st.markdown(f'<div class="note">{esc(caution)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------
# 8. 보고 대상별 요약
# ---------------------------------------------------------------
st.markdown('<div class="sec-title">보고 대상별 요약</div>', unsafe_allow_html=True)
r1, r2 = st.columns(2)
r1.markdown(f'<div class="sum"><div class="who">실무 엔지니어용</div><div class="txt">{esc(sum_eng)}</div></div>',
            unsafe_allow_html=True)
r2.markdown(f'<div class="sum"><div class="who">경영진 · CISO용</div><div class="txt">{esc(sum_exec)}</div></div>',
            unsafe_allow_html=True)