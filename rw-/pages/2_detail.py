import html
import json
import re

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="항목 상세", page_icon="🛡️", layout="wide")

DASHBOARD_PAGE = "pages/1_dash.py"

# ---------------------------------------------------------------
# 0. 시작 화면에서 저장한 데이터 꺼내기
# ---------------------------------------------------------------
with open("./data/sample_result.json", "r", encoding="utf-8") as f:
    data = json.load(f)
# data = st.session_state.get("data")
# if data is None:
#     st.warning("먼저 시작 화면에서 점검을 실행해주세요.")
#     if st.button("← 시작 화면으로"):
#         st.switch_page("app.py")
#     st.stop()

results = data["results"]
info = data.get("target_info", {})

if not results:
    st.warning("표시할 점검 항목이 없어요.")
    if st.button("← 시작 화면으로"):
        st.switch_page("app.py")
    st.stop()


def esc(v):
    """JSON 값을 HTML에 넣기 전에 꼭 거치는 함수 (XSS 방지)"""
    return html.escape(str(v if v is not None else "-"))


def clean_cat(c):
    """'1. 계정 관리' → '계정 관리'"""
    return re.sub(r"^\d+\.\s*", "", c or "")


def pick(r, *keys, default=None):
    """JSON에서 여러 후보 키 중 값이 있는 첫 번째를 꺼냄 (키 이름이 달라도 동작)"""
    for k in keys:
        if r.get(k):
            return r[k]
    return default


# ---------------------------------------------------------------
# 1. 어떤 항목을 보여줄지 결정
#    우선순위: 주소의 ?code=U-01 → session_state["selected_code"] → 첫 번째 취약 항목 → 첫 항목
# ---------------------------------------------------------------
code = st.query_params.get("code") or st.session_state.get("selected_code")
item = next((r for r in results if r.get("item_code") == code), None)
if item is None:
    item = next((r for r in results if r.get("status") == "VULNERABLE"), results[0])

status = item.get("status")

STATUS = {
    "VULNERABLE": ("취약", "#FBE9DF", "#8A3109"),
    "SAFE": ("양호", "#E3E9FB", "#1A3794"),
    "REVIEW": ("수동 확인", "#FBF0D2", "#6B4E06"),
    "NA": ("해당 없음", "#ECEDEA", "#4A4E57"),
    "ERROR": ("점검 오류", "#ECEDEA", "#4A4E57"),
}
s_label, s_bg, s_fg = STATUS.get(status, (status, "#ECEDEA", "#4A4E57"))

# ---------------------------------------------------------------
# 2. 항목 데이터 정리 (JSON에 없으면 빈 칸 대신 안내 문구)
# ---------------------------------------------------------------
code_txt = item.get("item_code", "-")
check_file = pick(item, "check_file", "target_file", "file", default="-")
check_cmd = pick(item, "check_command", "command", "cmd", default="-")
expected = pick(item, "expected_value", "expected", "good_criteria", default="-")
current = pick(item, "current_value", default="-")

if status == "VULNERABLE":
    verdict = "기준과 다르므로 <b>취약</b> (스크립트 자동 판정)"
elif status == "SAFE":
    verdict = "기준과 같으므로 <b>양호</b> (스크립트 자동 판정)"
else:
    verdict = f"<b>{esc(s_label)}</b> · {esc(item.get('reason') or '-')}"

cur_color = "#9A3A0B" if status == "VULNERABLE" else "#1A3794"

kisa_text = pick(item, "kisa_guide", "kisa_text", "rag_result", "guide_text")
kisa_html = (esc(kisa_text).replace("\n", "<br>") if kisa_text
             else f"[KISA 가이드 {esc(code_txt)} 항목의 점검 내용 · 판단 기준 · 조치 방법 원문이 이곳에 표시됩니다]")
kisa_source = pick(item, "kisa_source", "rag_source",
                   default=f"출처: 주요정보통신기반시설 기술적 취약점 분석·평가 가이드 (2026) · Unix 서버 · {code_txt}")

script = pick(item, "remediation_script", "fix_script", "ai_script", "script", default="")
caution = pick(item, "caution", "script_caution", "ai_caution", default="")
sum_eng = pick(item, "summary_engineer", "engineer_summary", "summary_eng", default="-")
sum_exec = pick(item, "summary_exec", "executive_summary", "summary_ciso", default="-")

# 조치 스크립트 → 줄 단위 HTML ('#'으로 시작하면 회색 주석)
if script:
    lines = []
    for ln in str(script).split("\n"):
        cls = "ln c" if ln.lstrip().startswith("#") else "ln"
        lines.append(f'<div class="{cls}">{esc(ln) if ln else "&nbsp;"}</div>')
    script_html = "".join(lines)
else:
    script_html = '<div class="ln c"># 아직 생성된 조치 스크립트가 없어요.</div>'

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
    .kv .v.plain { font-family:'IBM Plex Sans KR', sans-serif; font-size:14px; }
    .ph { border:1px dashed #C9CCC4; border-radius:6px; padding:14px 16px; font-size:14px; color:#4A4E57;
          line-height:1.6; }
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

st.markdown(
    f"""<div class="head"><div>
      <div class="meta"><span class="badge-code">{esc(code_txt)}</span>
        <span>{esc(clean_cat(item.get("category")))} · 위험도 {esc(item.get("severity", "-"))}</span></div>
      <div class="t">{esc(item.get("item_name"))}</div>
      <div class="d">{esc(pick(item, "description", "item_desc", "reason", default="-"))}</div>
    </div>
    <span class="pill-lg" style="background:{s_bg};color:{s_fg}">{esc(s_label)}</span></div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 6. 판정 근거 / KISA 가이드 근거
# ---------------------------------------------------------------
st.write("")
c1, c2 = st.columns(2)
c1.markdown(
    f"""<div class="card"><div class="ch">판정 근거</div>
      <div class="kv"><span class="k">점검 파일</span><span class="v">{esc(check_file)}</span></div>
      <div class="kv"><span class="k">점검 명령</span><span class="v">{esc(check_cmd)}</span></div>
      <div class="kv"><span class="k">양호 기준</span><span class="v" style="color:#1A3794">{esc(expected)}</span></div>
      <div class="kv"><span class="k">현재 값</span><span class="v" style="color:{cur_color}">{esc(current)}</span></div>
      <div class="kv"><span class="k">판정</span><span class="v plain">{verdict}</span></div></div>""",
    unsafe_allow_html=True,
)
c2.markdown(
    f"""<div class="card"><div class="ch">KISA 가이드 근거<span class="tag">RAG 검색 결과</span></div>
      <div class="ph">{kisa_html}</div>
      <div class="src">{esc(kisa_source)}</div></div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 7. AI 조치 스크립트 (복사 버튼 포함)
# ---------------------------------------------------------------
copy_js_text = json.dumps(str(script)).replace("</", "<\\/")
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