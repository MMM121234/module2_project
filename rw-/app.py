import json
import os
import time

import streamlit as st

# ---------------------------------------------------------------
# 0. 페이지 기본 설정 (반드시 맨 위에서 한 번만 호출)
# ---------------------------------------------------------------
st.set_page_config(page_title="간편 리눅스 보안 점검", page_icon="🛡️", layout="wide")

DASHBOARD_PAGE = "pages/1_dash.py"   # 다음 화면 (나중에 만들 파일)
SAMPLE_FILE = "data/sample_result.json"   # 가짜 점검 결과

# 고정 점검 환경 (화면에 보여주기만 함)
OS_NAME = "Rocky Linux 9"
GUIDE = "KISA 주요정보통신기반시설 가이드 2026"


# ---------------------------------------------------------------
# 1. 점검 실행 함수 (지금은 껍데기)
#    → 나중에 이 함수 안만 SSH 실행 코드로 바꾸면 됨
# ---------------------------------------------------------------
def run_scan(host, port):
    time.sleep(2)  # 실행하는 척
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------
# 2. 디자인(CSS)
#    st.container(key="이름") 으로 만든 상자에는 .st-key-이름 클래스가 붙음
#    → 그 이름으로 상자별 디자인을 지정
# ---------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');

    /* ---------- 전체 ---------- */
    .stApp { background:#16181D; }
    .stApp, .stApp p, .stApp label, .stApp input, .stApp button {
        font-family:'IBM Plex Sans KR', sans-serif;
    }
    /* 아이콘 글꼴은 건드리지 않기 (안 그러면 아이콘이 글자로 깨짐) */
    .stApp [data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded' !important; }
    header[data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1280px; padding-top:1.5rem; }
    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, .stApp span { color:#F3F4F1; }

    /* ---------- 상단 바 ---------- */
    .topbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:56px; }
    .brand { display:flex; align-items:center; gap:12px; color:#F3F4F1; font-weight:600; font-size:16px; }
    .brand-logo { width:32px; height:32px; border-radius:6px; background:#1E3FAE; color:#fff;
                  display:flex; align-items:center; justify-content:center;
                  font-family:'IBM Plex Mono', monospace; font-size:13px; font-weight:500; }
    .ver { font-family:'IBM Plex Mono', monospace; font-size:12px; color:#B9BCC4; }

    /* ---------- 왼쪽 소개 ---------- */
    .cmd   { font-family:'IBM Plex Mono', monospace; font-size:13px; color:#9DB3F5; }
    .hero  { color:#F3F4F1; font-size:clamp(28px, 3vw, 44px); font-weight:700; line-height:1.2;
             letter-spacing:-1px; margin:24px 0; word-break:keep-all; }
    .sub   { color:#B9BCC4; font-size:17px; line-height:1.6; max-width:540px; word-break:keep-all; }
    .stats { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:32px 0; max-width:560px; }
    .stat  { border:1px solid #33363E; border-radius:10px; padding:16px; }
    .stat b    { display:block; font-family:'IBM Plex Mono', monospace; font-size:26px; font-weight:500; color:#F3F4F1; }
    .stat span { font-size:13px; color:#B9BCC4; }
    .step  { color:#B9BCC4; font-size:14px; margin:10px 0; }
    .step b{ font-family:'IBM Plex Mono', monospace; color:#F3F4F1; font-weight:400; margin-right:14px; }

    /* ---------- 오른쪽 카드 (밝은 상자) ---------- */
    .st-key-start_card { background:#F3F4F1; border-radius:16px; padding:32px; }
    .st-key-start_card h3, .st-key-start_card p,
    .st-key-start_card label, .st-key-start_card span { color:#16181D; }
    .st-key-start_card [data-testid="stCaptionContainer"] p { color:#4A4E57; }
    /* 입력칸·선택칸 위 이름표만 굵게 */
    .st-key-start_card [data-testid="stTextInput"] [data-testid="stWidgetLabel"] p,
    .st-key-start_card [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p { font-weight:600; font-size:13px; }

    /* 입력칸 · 선택칸: 흰 배경 + 회색 테두리 */
    .st-key-start_card [data-testid="stTextInputRootElement"],
    .st-key-start_card [data-testid="stSelectbox"] [role="group"] {
        background:#FFFFFF; border:1px solid #B9BCC4; border-radius:8px; min-height:44px;
    }
    .st-key-start_card [data-testid="stSelectbox"] button { background:transparent; color:#16181D; }
    .st-key-start_card input { background:#FFFFFF; color:#16181D; }
    .st-key-start_card input::placeholder { color:#8A8E96; font-family:'IBM Plex Mono', monospace; }

    /* 고정 점검 환경 정보 상자 */
    .info { background:#FFFFFF; border:1px solid #DCDED8; border-radius:8px; padding:6px 16px; margin-bottom:8px; }
    .info-row { display:flex; gap:16px; align-items:center; padding:10px 0; font-size:14px; color:#16181D; }
    .info-row + .info-row { border-top:1px solid #ECEDEA; }
    .info-row.top { align-items:flex-start; }
    .info-row .k { width:72px; flex-shrink:0; font-size:13px; font-weight:600; color:#4A4E57; }
    .srv { display:flex; gap:12px; padding:2px 0; color:#16181D; }
    .srv .mono, .mono { font-family:'IBM Plex Mono', monospace; font-size:13px; color:#1A3794; font-weight:500; }

    /* 점검 범위: 한 줄씩 흰 상자 */
    [class*="st-key-scope_"] { background:#FFFFFF; border:1px solid #DCDED8; border-radius:8px;
                               padding:8px 14px; }
    .code { font-family:'IBM Plex Mono', monospace; font-size:12px; color:#4A4E57;
            text-align:right; white-space:nowrap; position:relative; top:-5px; }

    /* 체크박스: 체크된 상자를 파란색으로 */
    .st-key-start_card [data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type {
        background-color:#1E3FAE; border-color:#1E3FAE;
    }
    .st-key-start_card [data-testid="stCheckbox"] p { font-weight:400; font-size:15px; }

    /* 오른쪽 위 Deploy 메뉴 숨기기 */
    [data-testid="stToolbar"] { display:none; }

    /* 파란색 큰 버튼 */
    .st-key-start_card [data-testid="stBaseButton-primary"] {
        background:#1E3FAE; border:none; border-radius:10px; min-height:52px;
    }
    .st-key-start_card [data-testid="stBaseButton-primary"]:hover { background:#142C7A; }
    .st-key-start_card [data-testid="stBaseButton-primary"] p { color:#FFFFFF; font-weight:700; font-size:16px; }

    /* 카드 하단: 최근 점검 */
    .recent { display:flex; justify-content:space-between; align-items:center; gap:12px;
              border-top:1px solid #DCDED8; padding-top:16px; font-size:13px; color:#4A4E57; }
    .st-key-start_card .recent a { color:#1E3FAE; font-weight:600; text-decoration:underline; }

    /* ---------- 하단 ---------- */
    .footer { display:flex; justify-content:space-between; gap:12px; color:#8A8E96; font-size:12px;
              border-top:1px solid #2A2D35; padding-top:20px; margin-top:64px; }
    .footer .mono { font-family:'IBM Plex Mono', monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# 3. 상단 바
# ---------------------------------------------------------------
st.markdown(
    """
    <div class="topbar">
      <div class="brand"><div class="brand-logo">rw-</div>간편 리눅스 보안 점검</div>
      <div class="ver">v1.0 · KISA 2026 Linux</div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, _, right = st.columns([1.15, 0.1, 1])

# ---------------------------------------------------------------
# 4. 왼쪽: 소개
# ---------------------------------------------------------------
with left:
    st.markdown(
        """
        <div class="cmd">$ sudo ./check.sh --guide kisa-2026 --target rocky-svr</div>
        <div class="hero">리눅스 서버 취약점,<br>점검부터 조치 보고서까지<br>한 번에.</div>
        <div class="sub">KISA 주요정보통신기반시설 가이드 기준으로 Linux 서버를 점검하고,
        엑셀 증빙 보고서와 AI 조치 보고서를 함께 만들어 드립니다.</div>
        <div class="stats">
          <div class="stat"><b>17</b><span>점검 항목</span></div>
          <div class="stat"><b>4</b><span>점검 영역</span></div>
          <div class="stat"><b>2</b><span>보고서 (엑셀 · AI)</span></div>
        </div>
        <div class="step"><b>01</b>점검 스크립트가 서버 설정을 수집하고 기준과 비교해요</div>
        <div class="step"><b>02</b>조치 스크립트와 대상별 보고서를 자동으로 만들어요</div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------
# 5. 오른쪽: 새 점검 시작 카드
# ---------------------------------------------------------------
with right:
    with st.container(key="start_card"):
        st.subheader("새 점검 시작")
        st.caption("점검할 서버와 범위를 선택하세요.")

        # 대상 서버 / 포트 (입력)
        c1, c2 = st.columns([2, 1])
        host = c1.text_input("대상 서버", placeholder="[서버 주소]")
        port = c2.text_input("SSH 포트", placeholder="[포트]")

        # 점검 환경
        st.markdown(
            f"""
            <div class="info">
              <div class="info-row"><span class="k">운영체제</span><span>{OS_NAME}</span></div>
              <div class="info-row"><span class="k">점검 기준</span><span>{GUIDE}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 점검 범위 (한 줄씩 흰 상자)
        st.markdown('<p style="font-weight:600;font-size:13px;margin:8px 0 4px">점검 범위</p>',
                    unsafe_allow_html=True)
        scope_items = [
            ("계정 관리", "계정 관리", "U-01 ~ U-06"),
            ("파일 및 디렉토리 관리", "파일 및 디렉터리 관리", "U-14 ~ U-18"),
            ("서비스 관리", "서비스 관리", "U-35 · 38 · 45 · 46"),
            ("로그 관리", "로그 관리", "U-65 · 67"),
        ]
        scope = {}
        for i, (key, label, code) in enumerate(scope_items):
            with st.container(key=f"scope_{i}"):
                a, b = st.columns([1, 1], vertical_alignment="center")
                scope[key] = a.checkbox(label, value=True, key=f"chk_{i}")
                b.markdown(f'<div class="code">{code}</div>', unsafe_allow_html=True)

        start = st.button("점검 시작 →", type="primary", use_container_width=True)

        # 점검 진행 표시 (버튼을 눌렀을 때만)
        if start:
            with st.status("서버 점검 중...", expanded=True) as status:
                st.write("① 서버 접속 중...")
                st.write("② 점검 스크립트 실행 중...")
                data = run_scan(host, port)
                st.write("③ 결과 정리 중...")
                status.update(label="점검 완료!", state="complete")

            # 선택한 범위의 항목만 남기기
            chosen = [k for k, on in scope.items() if on]
            data["results"] = [r for r in data["results"]
                               if any(k in r.get("category", "") for k in chosen)]

            # 다른 페이지에서 쓸 수 있게 저장
            st.session_state["data"] = data

            if os.path.exists(DASHBOARD_PAGE):
                st.switch_page(DASHBOARD_PAGE)
            else:
                st.success(f"점검 완료! 항목 {len(data['results'])}개 (대시보드 페이지는 아직 없어요)")

        st.markdown(
            """
            <div class="recent">
              <span>최근 점검 · 2026-10-02 09:00 · 취약 10 / 17</span>
              <a>결과 다시 보기</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------
# 6. 하단
# ---------------------------------------------------------------
st.markdown(
    """
    <div class="footer">
      <span>Team rw- · SK쉴더스 AI 활용 사이버보안 과정 모듈 프로젝트</span>
    </div>
    """,
    unsafe_allow_html=True,
)