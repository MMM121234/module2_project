import html
import json
import re

import streamlit as st

st.set_page_config(page_title="점검 결과 대시보드", page_icon="🛡️", layout="wide")

# ---------------------------------------------------------------
# 0. 화면에 보여줄 샘플 데이터 읽기
#    ※ 껍데기 버전: 버튼은 페이지 이동만 하고, 다른 기능은 없음
# ---------------------------------------------------------------
with open("data/sample_result.json", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]

# 항목별 중요도 (KISA 가이드 기준, 팀 회의에서 정한 17개)
SEVERITY = {
    "U-01": "상", "U-02": "상", "U-03": "상", "U-04": "상", "U-05": "상", "U-06": "상",
    "U-14": "상", "U-15": "상", "U-16": "상", "U-17": "상", "U-18": "상",
    "U-35": "상", "U-38": "상", "U-45": "상", "U-46": "상",
    "U-65": "중", "U-67": "중",
}
for r in results:
    r["severity"] = SEVERITY.get(r.get("item_code"), r.get("severity", "-"))
info = data.get("target_info", {})


def esc(v):
    """JSON 값을 HTML에 넣기 전에 꼭 거치는 함수 (XSS 방지)"""
    return html.escape(str(v if v is not None else "-"))


def clean_cat(c):
    """'1. 계정 관리' → '계정 관리'"""
    return re.sub(r"^\d+\.\s*", "", c or "")


# 결과값별 표시 이름과 색
STATUS = {
    "VULNERABLE": ("취약", "#FBE9DF", "#8A3109", "#B4430A"),
    "SAFE": ("양호", "#E3E9FB", "#1A3794", "#1E3FAE"),
    "REVIEW": ("수동 확인", "#FBF0D2", "#6B4E06", "#D9A21B"),
    "NA": ("해당 없음", "#ECEDEA", "#4A4E57", "#9A9DA4"),
    "ERROR": ("점검 오류", "#ECEDEA", "#4A4E57", "#9A9DA4"),
}


def pill(status):
    label, bg, fg, _ = STATUS.get(status, (status, "#ECEDEA", "#4A4E57", "#9A9DA4"))
    extra = "outline:1px dashed #8A8E96;" if status == "ERROR" else ""
    return (f'<span class="pill" style="background:{bg};color:{fg};{extra}">'
            f"{esc(label)}</span>")


# ---------------------------------------------------------------
# 1. 숫자 계산
# ---------------------------------------------------------------
def count(s):
    return sum(1 for r in results if r.get("status") == s)


n_v, n_s, n_r, n_na, n_err = (count(s) for s in ["VULNERABLE", "SAFE", "REVIEW", "NA", "ERROR"])
rate = n_s / (n_s + n_v) * 100 if (n_s + n_v) else 0

na_err_desc = " · ".join(
    [f"{r['item_code']} 미설치" for r in results if r.get("status") == "NA"]
    + [f"{r['item_code']} 점검 오류" for r in results if r.get("status") == "ERROR"]
) or "-"

# ---------------------------------------------------------------
# 2. 디자인(CSS)
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
    .block-container { max-width:1280px; padding-top:0; }
    .topbar { margin-top:-16px !important; }
    .mono { font-family:'IBM Plex Mono', monospace; }

    /* 상단 바 (화면 전체 너비) */
    .topbar { background:#16181D; margin:0 calc(50% - 50vw); padding:0 calc(50vw - 50% + 1rem); }
    .topbar-in { height:64px; display:flex; align-items:center; justify-content:space-between; gap:24px; }
    .brand { display:flex; align-items:center; gap:12px; color:#F3F4F1; font-weight:600; font-size:16px; }
    .logo { width:32px; height:32px; border-radius:6px; background:#1E3FAE; color:#fff; display:flex;
            align-items:center; justify-content:center; font-family:'IBM Plex Mono', monospace; font-size:13px; }
    .nav { display:flex; gap:4px; }
    .nav span { color:#B9BCC4; padding:10px 14px; border-radius:6px; font-size:14px; }
    .nav span.on { color:#fff; background:#2A2D35; }
    .srvinfo { font-family:'IBM Plex Mono', monospace; font-size:12px; color:#B9BCC4; }

    /* 처리 흐름 */
    .flow { background:#fff; border-bottom:1px solid #DCDED8; margin:0 calc(50% - 50vw);
            padding:14px calc(50vw - 50% + 1rem); display:flex; gap:10px; align-items:center;
            flex-wrap:wrap; font-size:13px; color:#4A4E57; }
    .flow b { color:#16181D; }
    .flow span.s { padding:4px 10px; border-radius:999px; background:#E8EAE4; }
    .flow span.s.on { background:#16181D; color:#fff; }
    .flow span.a { color:#8A8E96; }

    /* 제목 영역 */
    .scan { font-family:'IBM Plex Mono', monospace; font-size:12px; color:#6A6E76; margin-top:40px; }
    .title { font-size:34px; font-weight:700; letter-spacing:-0.5px; margin:6px 0; color:#16181D; }
    .desc { color:#4A4E57; }

    /* 숫자 카드 */
    .kpis { display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:16px; margin:24px 0; }
    .kpi { background:#fff; border:1px solid #DCDED8; border-radius:12px; padding:22px 24px; }
    .kpi.dark { background:#16181D; border-color:#16181D; }
    .kpi .l { font-size:13px; color:#4A4E57; display:flex; align-items:center; gap:8px; }
    .kpi .n { font-family:'IBM Plex Mono', monospace; font-size:40px; font-weight:500; line-height:1.2; margin:6px 0; }
    .kpi .d { font-size:12px; color:#6A6E76; }
    .kpi.dark .l, .kpi.dark .d { color:#B9BCC4; } .kpi.dark .n { color:#F3F4F1; }
    .sq { width:10px; height:10px; border-radius:2px; display:inline-block; }

    /* 카드 공통 */
    .card { background:#fff; border:1px solid #DCDED8; border-radius:12px; padding:24px; min-height:440px; box-sizing:border-box; }
    .card .ch { margin:0 0 20px; font-size:18px; font-weight:600; display:flex; justify-content:space-between;
                align-items:baseline; gap:12px; color:#16181D; }
    .legend { display:flex; gap:12px; font-size:12px; color:#4A4E57; font-weight:400; }
    .legend span { display:flex; align-items:center; gap:5px; }
    .catrow { margin-bottom:18px; }
    .catrow .top { display:flex; justify-content:space-between; font-size:14px; margin-bottom:8px; }
    .catrow .top .mono { font-size:13px; color:#4A4E57; }
    .bar { display:flex; height:14px; border-radius:4px; overflow:hidden; background:#E8EAE4; gap:2px; }
    .rev { border:1px solid #E3E5DF; border-radius:8px; padding:14px 16px; margin-bottom:12px; }
    .rev .top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    .rev .r { font-size:13px; color:#4A4E57; margin-top:6px; }
    .pill { display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }

    /* 결과 표 */
    .tbl { background:#fff; border:1px solid #DCDED8; border-radius:12px; overflow:hidden; margin-top:4px; }
    .tbl table { width:100%; border-collapse:collapse; font-size:14px; border:none; margin:0; }
    .tbl th, .tbl td { border:none !important; white-space:normal; }
    .tbl th { white-space:nowrap; }
    .tbl td.name { min-width:240px; }
    .tbl th { background:#F3F4F1; text-align:left; font-size:12px; font-weight:600; color:#4A4E57; padding:12px 16px; }
    .tbl td { padding:14px 16px; border-top:1px solid #E8EAE4 !important; vertical-align:middle; }
    .tbl td.code { font-family:'IBM Plex Mono', monospace; font-weight:500; }
    .tbl td.cat { color:#4A4E57; font-size:13px; }
    .tbl td.name { font-weight:500; }
    /* 카테고리 사이 틈 */
    .tbl tr.gap td { height:10px; padding:0; background:#F3F4F1; }

    /* 필터 버튼: 동그란 모양, 선택된 것은 검정 */
    [data-testid="stButtonGroup"] button { border-radius:999px !important; margin-left:6px; background:#fff; }
    [data-testid="stButtonGroup"] button[aria-checked="true"] { background:#16181D !important; border-color:#16181D !important; }
    [data-testid="stButtonGroup"] button[aria-checked="true"] p { color:#FFFFFF !important; }
    [data-testid="stButtonGroup"] [role="radiogroup"] { justify-content:flex-end; width:100%; }

    /* 버튼 */
    [data-testid="stBaseButton-primary"] { background:#1E3FAE; border-color:#1E3FAE; min-height:44px; }
    [data-testid="stBaseButton-primary"]:hover { background:#142C7A; border-color:#142C7A; }
    [data-testid="stBaseButton-primary"] p { color:#fff; font-weight:600; }
    [data-testid="stBaseButton-secondary"] { border-color:#16181D; min-height:44px; background:#fff; }
    [data-testid="stBaseButton-secondary"] p { font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 3. 상단 바 + 처리 흐름
# ---------------------------------------------------------------
st.markdown(
    f"""
    <div class="topbar"><div class="topbar-in">
      <div class="brand"><div class="logo">rw-</div>간편 리눅스 보안 점검</div>
      <div class="srvinfo">{esc(info.get("target_host", "-"))} · {esc(info.get("os_version", "-"))}</div>
    </div></div>
    <div class="flow">
      <b>처리 흐름</b>
      <span class="s">① 점검 스크립트 실행</span><span class="a">→</span>
      <span class="s">② JSON 수집</span><span class="a">→</span>
      <span class="s">③ KISA 가이드 매칭</span><span class="a">→</span>
      <span class="s">④ AI 분석</span><span class="a">→</span>
      <span class="s on">⑤ 시각화 · 보고서</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 4. 제목 + 버튼
# ---------------------------------------------------------------
t1, t2 = st.columns([2.4, 1.6], vertical_alignment="bottom")
with t1:
    st.markdown(
        f"""
        <div class="scan">SCAN · {esc(info.get("scan_time", "-"))} · KISA 주요정보통신기반시설 가이드 (2026, Linux)</div>
        <div class="title">점검 결과 요약</div>
        <div class="desc">{len(results)}개 항목 중 {n_v}개 항목이 취약으로 판정되었습니다.
        """,
        unsafe_allow_html=True,
    )

with t2:
    b1, b2 = st.columns(2)
    b1.button("엑셀 보고서 다운로드", use_container_width=True)                 # 모양만 (기능 없음)
    b2.button("AI 보고서 보기", type="primary", use_container_width=True)       # 모양만 (기능 없음)

# ---------------------------------------------------------------
# 5. 숫자 카드 5개
# ---------------------------------------------------------------
st.markdown(
    f"""
    <div class="kpis">
      <div class="kpi dark"><div class="l">준수율</div><div class="n">{rate:.1f}%</div><div class="d">양호 ÷ (양호 + 취약)</div></div>
      <div class="kpi"><div class="l"><span class="sq" style="background:#B4430A"></span>취약</div>
        <div class="n" style="color:#9A3A0B">{n_v}</div><div class="d">즉시 조치 대상</div></div>
      <div class="kpi"><div class="l"><span class="sq" style="background:#1E3FAE"></span>양호</div>
        <div class="n" style="color:#1E3FAE">{n_s}</div><div class="d">기준 충족</div></div>
      <div class="kpi"><div class="l"><span class="sq" style="background:#D9A21B"></span>수동 확인</div>
        <div class="n">{n_r}</div><div class="d">담당자 확인 필요</div></div>
      <div class="kpi"><div class="l"><span class="sq" style="background:#9A9DA4"></span>해당 없음 · 오류</div>
        <div class="n">{n_na} · {n_err}</div><div class="d">{esc(na_err_desc)}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 6. 카테고리별 결과 
# ---------------------------------------------------------------
cats = {}
for r in results:
    c = clean_cat(r.get("category"))
    cats.setdefault(c, {"VULNERABLE": 0, "SAFE": 0, "REVIEW": 0, "OTHER": 0})
    s = r.get("status")
    cats[c][s if s in ("VULNERABLE", "SAFE", "REVIEW") else "OTHER"] += 1

cat_html = ""
for c, k in cats.items():
    total = sum(k.values())
    segs = ""
    for key, color in [("VULNERABLE", "#B4430A"), ("SAFE", "#1E3FAE"), ("REVIEW", "#D9A21B"), ("OTHER", "#9A9DA4")]:
        if k[key]:
            segs += f'<div style="flex-grow:{k[key]};background:{color}"></div>'
    cat_html += (f'<div class="catrow"><div class="top"><span>{esc(c)}</span>'
                 f'<span class="mono">취약 {k["VULNERABLE"]} / {total}</span></div>'
                 f'<div class="bar">{segs}</div></div>')

rev_html = ""
for r in results:
    if r.get("status") != "REVIEW":
        continue
    v = r.get("ai_verdict")
    badge = pill(v).replace(">" + esc(STATUS[v][0]) + "<", ">AI · " + esc(STATUS[v][0]) + "<") if v in STATUS \
        else '<span class="pill" style="background:#ECEDEA;color:#4A4E57">담당자 확인 필요</span>'
    rev_html += (f'<div class="rev"><div class="top"><div><span class="mono" style="font-weight:500">'
                 f'{esc(r.get("item_code"))}</span>&nbsp;&nbsp;<b style="font-weight:500">{esc(r.get("item_name"))}</b></div>'
                 f'{badge}</div><div class="r">{esc(r.get("ai_reason") or r.get("current_value"))}</div></div>')
if not rev_html:
    rev_html = '<div class="r">수동 확인 항목이 없어요.</div>'

g1, g2 = st.columns(2)
g1.markdown(
    f"""<div class="card"><div class="ch">카테고리별 결과
      <span class="legend"><span><i class="sq" style="background:#B4430A"></i>취약</span>
      <span><i class="sq" style="background:#1E3FAE"></i>양호</span>
      <span><i class="sq" style="background:#D9A21B"></i>수동</span>
      <span><i class="sq" style="background:#9A9DA4"></i>기타</span></span></div>{cat_html}</div>""",
    unsafe_allow_html=True,
)
g2.markdown(
    f"""<div class="card"><div class="ch">수동 확인 항목
      <span class="legend">담당자 검토 필요</span></div>{rev_html}</div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 7. 전체 점검 결과 표 (필터 버튼: 화면 안에서만 동작)
# ---------------------------------------------------------------
st.write("")
h1, h2 = st.columns([2, 1.3], vertical_alignment="center")
h1.markdown(f'<div style="font-size:18px;font-weight:600;margin-top:16px">전체 점검 결과 '
            f'<span class="mono" style="color:#6A6E76;font-weight:400;font-size:14px">{len(results)}</span></div>',
            unsafe_allow_html=True)
pick = h2.segmented_control("필터", ["전체", "취약", "수동 확인", "양호"], default="전체",
                            label_visibility="collapsed")
filter_map = {"취약": "VULNERABLE", "수동 확인": "REVIEW", "양호": "SAFE"}

# 선택한 필터에 맞는 항목만 남기기
shown = [r for r in results if pick not in filter_map or r.get("status") == filter_map[pick]]

rows = ""
prev_cat = None
for r in shown:
    # 카테고리가 바뀌는 곳에 빈 줄(틈) 넣기
    cat = r.get("category")
    if prev_cat is not None and cat != prev_cat:
        rows += '<tr class="gap"><td colspan="4"></td></tr>'
    prev_cat = cat

    rows += (f'<tr><td class="code">{esc(r.get("item_code"))}</td>'
             f'<td class="name">{esc(r.get("item_name"))}</td>'
             f'<td>{esc(r.get("severity", "-"))}</td>'
             f'<td>{pill(r.get("status"))}</td></tr>')

st.markdown(
    f"""<div class="tbl"><table>
      <tr><th style="width:100px">코드</th><th>항목</th>
          <th style="width:100px">중요도</th><th style="width:140px">결과</th></tr>
      {rows}</table></div>""",
    unsafe_allow_html=True,
)

st.write("")
if st.button("← 다시 점검하기"):
    st.switch_page("app.py")