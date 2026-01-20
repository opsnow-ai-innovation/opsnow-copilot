#!/bin/bash
# FAQ, Guide 문서 임베딩 배치 실행 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "OpsNow Copilot - 문서 임베딩 배치"
echo "========================================"
echo "Project Root: $PROJECT_ROOT"
echo ""

# Python 환경 확인
if ! command -v python &> /dev/null; then
    echo "ERROR: Python이 설치되어 있지 않습니다."
    exit 1
fi

# 필요한 디렉토리 생성
mkdir -p src/data/origin/io_faq
mkdir -p src/data/origin/io_menu
mkdir -p src/data/output

echo "데이터 디렉토리 확인:"
echo "  - FAQ: src/data/origin/io_faq/"
echo "  - Menu: src/data/origin/io_menu/"
echo "  - Output: src/data/output/"
echo ""

# 배치 실행
echo "배치 프로세서 실행 중..."
python -m src.processors.guide_batch_processor

echo ""
echo "완료!"
