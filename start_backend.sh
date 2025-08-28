#!/bin/bash

# Backend 시작 스크립트
echo "🚀 Starting Autotrading Backend Services..."

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 현재 디렉토리 확인
cd /Users/houkjang/Autotrading

# Docker 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Checking Docker services...${NC}"

# 기존 컨테이너 정리
echo -e "${YELLOW}🧹 Cleaning up existing containers...${NC}"
docker-compose down 2>/dev/null

# Docker Compose로 모든 서비스 시작
echo -e "${GREEN}🐳 Starting all services with Docker Compose...${NC}"
docker-compose up -d postgres redis backend celery-worker celery-beat

# 잠시 대기 (서비스 시작 시간)
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 5

# 서비스 상태 확인
echo -e "${GREEN}✅ Checking service status:${NC}"
docker-compose ps

# PostgreSQL 연결 확인
echo -e "${YELLOW}🔍 Checking PostgreSQL connection...${NC}"
docker exec autotrading-postgres pg_isready -U trading
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
    echo -e "${RED}❌ PostgreSQL is not ready${NC}"
fi

# Redis 연결 확인
echo -e "${YELLOW}🔍 Checking Redis connection...${NC}"
docker exec autotrading-redis redis-cli ping
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Redis is ready${NC}"
else
    echo -e "${RED}❌ Redis is not ready${NC}"
fi

# Backend API 헬스체크
echo -e "${YELLOW}🔍 Checking Backend API...${NC}"
sleep 3
curl -s http://localhost:8000/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backend API is ready${NC}"
else
    echo -e "${YELLOW}⚠️  Backend API is starting up...${NC}"
fi

echo -e "${GREEN}🎉 Backend services are running!${NC}"
echo ""
echo -e "${GREEN}📌 Service URLs:${NC}"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   PostgreSQL: localhost:5432"
echo "   Redis: localhost:6379"
echo ""
echo -e "${YELLOW}📝 Useful commands:${NC}"
echo "   View logs: docker-compose logs -f backend"
echo "   Stop all: docker-compose down"
echo "   Restart: docker-compose restart backend"
echo ""
echo -e "${GREEN}✨ Frontend is already running at http://localhost:3000${NC}"