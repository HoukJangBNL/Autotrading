# Phase 3 Real-time Streaming 종합 테스트 계획

## 테스트 목표
Phase 3 실시간 스트리밍 기능의 모든 컴포넌트를 체계적으로 검증

## 테스트 환경
- **OS**: macOS Darwin 24.6.0
- **Python**: 3.9 (Anaconda)
- **Redis**: 6.x with password authentication
- **PostgreSQL**: TimescaleDB enabled
- **API Server**: FastAPI with uvicorn

## 테스트 전략

### 1단계: 기본 인프라 검증
- [ ] Redis 연결 및 인증
- [ ] PostgreSQL 연결
- [ ] API 서버 헬스체크
- [ ] WebSocket 엔드포인트 접근성

### 2단계: 개별 컴포넌트 테스트
- [ ] StreamingClient 초기화
- [ ] StreamProcessor 초기화
- [ ] WebSocket ConnectionManager
- [ ] Redis Pub/Sub 메시징

### 3단계: 통합 데이터 플로우
- [ ] 모의 데이터 생성 → Redis → WebSocket
- [ ] 실시간 캔들 집계 검증
- [ ] 다중 클라이언트 지원
- [ ] 에러 복구 시나리오

### 4단계: 성능 및 안정성
- [ ] 메시지 처리 속도
- [ ] 메모리 사용량
- [ ] 동시 연결 제한
- [ ] 재연결 로직

## 테스트 시나리오

### 시나리오 1: Happy Path
1. API 서버 시작
2. WebSocket 클라이언트 연결
3. 심볼 구독
4. 모의 데이터 스트리밍 시작
5. 실시간 데이터 수신 확인
6. 캔들 집계 정확성 검증

### 시나리오 2: Error Recovery
1. Redis 연결 끊김 시뮬레이션
2. WebSocket 재연결
3. 데이터 무결성 확인

### 시나리오 3: 부하 테스트
1. 다중 심볼 동시 스트리밍
2. 다중 클라이언트 연결
3. 리소스 사용량 모니터링

## 성공 기준
- 모든 컴포넌트 정상 초기화
- 데이터 플로우 무중단 동작
- 1초 이내 레이턴시
- 에러 발생 시 자동 복구
- 메모리 누수 없음

## 테스트 도구
1. `test_streaming_integration.py` - 전체 통합 테스트
2. `test_websocket_simple.py` - WebSocket 대화형 테스트
3. `test_streaming_mock.py` - 모의 데이터 생성 테스트
4. `quick_test.py` - 빠른 연결 테스트