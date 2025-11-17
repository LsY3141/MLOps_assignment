#!/bin/bash

# 캠퍼스메이트 빠른 시작 스크립트
# EC2에서 처음 실행할 때 사용

set -e  # 오류 발생 시 중단

echo "=========================================="
echo "🚀 캠퍼스메이트 빠른 시작"
echo "=========================================="
echo ""

# 현재 디렉토리 확인
if [ ! -f "README.md" ]; then
    echo "❌ 프로젝트 루트 디렉토리에서 실행해주세요"
    exit 1
fi

# 1. 시스템 패키지 업데이트
echo "1️⃣  시스템 패키지 업데이트 중..."
sudo yum update -y || sudo apt update -y

# 2. Python 확인
echo ""
echo "2️⃣  Python 버전 확인..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ $PYTHON_VERSION"
else
    echo "❌ Python이 설치되어 있지 않습니다"
    echo "설치 명령어: sudo yum install python3.11 -y"
    exit 1
fi

# 3. Node.js 확인
echo ""
echo "3️⃣  Node.js 버전 확인..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js $NODE_VERSION"
else
    echo "❌ Node.js가 설치되어 있지 않습니다"
    echo "설치를 진행하시겠습니까? (y/n)"
    read -r answer
    if [ "$answer" == "y" ]; then
        curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
        sudo yum install -y nodejs
    else
        exit 1
    fi
fi

# 4. 백엔드 설정
echo ""
echo "4️⃣  백엔드 설정 중..."
cd backend

# 가상환경 생성
if [ ! -d "venv" ]; then
    echo "   가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
echo "   패키지 설치 중... (1-2분 소요)"
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

echo "✅ 백엔드 패키지 설치 완료"

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env 파일이 없습니다."
    echo "   기본 .env 파일을 생성하시겠습니까? (y/n)"
    read -r answer
    if [ "$answer" == "y" ]; then
        cat > .env << 'EOF'
# AWS 설정
AWS_REGION=us-west-1

# PostgreSQL 데이터베이스 설정
DATABASE_URL=postgresql://postgres:12345678aA@database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com:5432/postgres
DB_HOST=database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=12345678aA

# S3 설정
S3_BUCKET_NAME=ysu-ml-a-13-s3
S3_REGION=us-west-1

# 기본 설정
DEFAULT_SCHOOL_ID=1
EOF
        echo "✅ .env 파일 생성 완료"
    fi
fi

# 데이터베이스 초기화
echo ""
echo "5️⃣  데이터베이스 초기화 중..."
if python init_db.py; then
    echo "✅ 데이터베이스 초기화 완료"
else
    echo "⚠️  데이터베이스 초기화 실패 (이미 초기화되었을 수 있습니다)"
fi

cd ..

# 6. 프론트엔드 설정
echo ""
echo "6️⃣  프론트엔드 설정 중..."
cd frontend

# .env 파일 생성
if [ ! -f ".env" ]; then
    echo "REACT_APP_API_URL=http://localhost:8000" > .env
    echo "✅ 프론트엔드 .env 파일 생성"
fi

# 패키지 설치
echo "   패키지 설치 중... (2-5분 소요)"
npm install > /dev/null 2>&1

echo "✅ 프론트엔드 패키지 설치 완료"

cd ..

# 완료
echo ""
echo "=========================================="
echo "🎉 설치 완료!"
echo "=========================================="
echo ""
echo "다음 명령어로 서버를 시작하세요:"
echo ""
echo "1️⃣  백엔드 실행:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "2️⃣  프론트엔드 실행 (새 터미널):"
echo "   cd frontend"
echo "   npm start"
echo ""
echo "3️⃣  접속:"
echo "   백엔드: http://YOUR_EC2_IP:8000/docs"
echo "   프론트엔드: http://YOUR_EC2_IP:3000"
echo ""
echo "⚠️  보안 그룹에서 포트 8000, 3000을 열어주세요!"
echo ""
