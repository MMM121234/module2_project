"""실행 파일: 점검 결과 JSON 을 읽어 AI 보고서(JSON)를 만든다.

사용법 (프로젝트 최상위 폴더에서 실행)
    python -m ai_report.main                  # ai_report/data/result.json 사용
    python -m ai_report.main 내점검결과.json   # 다른 JSON 사용

결과: ai_report/outputs/report.json
"""

import json
import sys
from pathlib import Path

from ai_report.report import generate_report

BASE_DIR = Path(__file__).parent  # ai_report/ 폴더


def main():
    # 1) 1팀이 만든 점검 결과 JSON 읽기
    scan_file = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "result.json"
    scan = json.loads(scan_file.read_text(encoding="utf-8"))

    # 2) 보고서 생성 (가이드 검색 + GPT 작성)
    report = generate_report(scan)

    # 3) JSON 파일로 저장
    out_dir = BASE_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "report.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료! 결과: {out_file}")


if __name__ == "__main__":
    main()
