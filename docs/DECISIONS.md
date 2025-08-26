# 기술 결정 사항

## 2024-11-14: 백엔드 아키텍처 구조

### 결정: 도메인 기반 모듈 구조
- **선택**: api/, services/, tasks/, strategies/ 분리
- **이유**: 
  - 명확한 책임 분리
  - 확장성과 유지보수성
  - 각 레이어별 독립적 테스트 가능
- **대안**: 기능별 분리 (trading/, data/, auth/)
- **근거**: 도메인 기반 구조가 더 확장 가능하고 테스트하기 쉬움

### 결정: FastAPI 선택
- **이유**:
  - 네이티브 async/await 지원
  - 자동 API 문서화 (OpenAPI)
  - WebSocket 내장 지원
  - Pydantic과의 완벽한 통합
- **대안**: Flask, Django
- **근거**: 비동기 처리와 실시간 기능에 최적화

### 결정: 전략 패턴 구현
- **선택**: 추상 기본 클래스 (ABC) 사용
- **이유**:
  - 일관된 인터페이스 보장
  - 전략별 독립적 구현
  - 런타임 전략 교체 가능
- **구현**:
  - BaseStrategy 추상 클래스
  - Signal 클래스로 표준화된 출력
  - 파라미터 기반 설정

## 2024-11-14: 데이터 모델 설계

### 결정: TimescaleDB 선택
- **이유**: 
  - PostgreSQL 호환성
  - 시계열 데이터 최적화
  - 자동 파티셔닝과 압축
  - SQL 쿼리 지원
- **대안**: InfluxDB, ClickHouse, MongoDB
- **근거**: 기존 PostgreSQL 인프라 활용 가능, SQL 친숙성

### 결정: 1분봉 데이터 구조
- **선택**: ticker_id + timestamp 복합 키
- **이유**:
  - 효율적인 시계열 쿼리
  - 중복 방지
  - 인덱싱 최적화
- **스키마**:
  ```sql
  CREATE TABLE candles (
      ticker_id INTEGER,
      timestamp TIMESTAMPTZ,
      open NUMERIC(10,4),
      high NUMERIC(10,4),
      low NUMERIC(10,4),
      close NUMERIC(10,4),
      volume BIGINT,
      PRIMARY KEY (ticker_id, timestamp)
  );
  ```

## 2024-11-14: 비동기 처리 전략

### 결정: Celery + Redis
- **선택**: Celery 작업 큐, Redis 브로커
- **이유**:
  - 성숙한 에코시스템
  - 다양한 작업 패턴 지원
  - 모니터링 도구 (Flower)
  - 스케줄링 기능 (Beat)
- **대안**: RQ, Dramatiq, AWS SQS
- **근거**: 커뮤니티 지원, 문서화, 확장성

### 결정: WebSocket 실시간 통신
- **선택**: FastAPI WebSocket + ConnectionManager
- **이유**:
  - 양방향 실시간 통신
  - 낮은 지연시간
  - 구독 패턴 구현 용이
- **구현**:
  - 심볼별 구독 관리
  - 자동 재연결 처리
  - 연결 상태 모니터링

## 2024-11-14: 보안 및 인증

### 결정: 기존 Auth 모듈 재사용
- **이유**:
  - 검증된 OAuth2 구현
  - Schwab API와의 통합 완료
  - 토큰 관리 로직 구축됨
- **통합 방법**:
  - get_authenticated_client() 활용
  - API 엔드포인트에 인증 미들웨어 추가

## 2024-11-14: FastAPI 서버 구현

### 결정: 에러 처리 전략
- **선택**: 5단계 예외 핸들러 체인
  1. AuthenticationError (401)
  2. HTTPException (사용자 정의)
  3. RequestValidationError (422)
  4. StarletteHTTPException (프레임워크)
  5. Exception (500 - 모든 미처리 예외)
- **이유**: 
  - 예외 타입별 적절한 응답
  - 구조화된 에러 메시지
  - 클라이언트 디버깅 지원
- **응답 포맷**:
  ```json
  {
    "detail": "에러 메시지",
    "type": "에러 타입"
  }
  ```

### 결정: 인증 아키텍처
- **선택**: OAuth2PasswordBearer + 의존성 주입
- **구현**:
  - `get_current_user`: 토큰 검증 및 사용자 정보 반환
  - `require_auth`: 보호된 엔드포인트용 의존성
- **이유**:
  - FastAPI 네이티브 패턴
  - OpenAPI 자동 문서화
  - 테스트 용이성
- **대안**: JWT 직접 구현, API Key 인증
- **근거**: Schwab OAuth2와의 통합 용이성

### 결정: 미들웨어 스택
- **순서**:
  1. CORS (Cross-Origin 요청 처리)
  2. 요청 로깅 (모든 요청 기록)
  3. 인증 검증
  4. 라우팅
- **이유**: 보안 검사 전 로깅으로 모든 시도 기록
- **추가 헤더**:
  - `X-Process-Time`: 요청 처리 시간
  - `X-API-Version`: API 버전

### 결정: 서비스 초기화 전략
- **선택**: Lifespan Context Manager
- **이유**:
  - 깔끔한 시작/종료 로직
  - 비동기 초기화 지원
  - 예외 처리 중앙화
- **순서**:
  1. 데이터베이스 연결
  2. Auth 서비스 초기화
  3. 비즈니스 서비스 초기화

## 2024-11-14: Phase 1.3 - Celery 태스크 큐 아키텍처

### 결정: 큐 분리 전략
- **선택**: 목적별 큐 분리 (default, data_mining, backtesting)
- **이유**:
  - 작업 유형별 우선순위 관리
  - 리소스 격리 및 성능 최적화
  - 워커 스케일링 유연성
- **구현**:
  - data_mining 큐: 우선순위 5, I/O 집약적
  - backtesting 큐: 우선순위 3, CPU 집약적
  - default 큐: 일반 작업용

### 결정: 태스크 재시도 및 시간 제한
- **재시도 전략**: 
  - 최대 3회 재시도
  - 지수 백오프 (60초 기본 지연)
  - bind=True로 self.retry() 활용
- **시간 제한**:
  - 일반 태스크: 1시간 (3600초)
  - 최적화 태스크: 2시간 (7200초)
  - Soft limit: Hard limit의 90%
- **이유**: API 제한 및 네트워크 오류 대응, 무한 실행 방지

### 결정: 진행 상황 추적 메커니즘
- **선택**: Celery update_state 활용
- **구현**:
  ```python
  self.update_state(
      state='PROGRESS',
      meta={'current': n, 'total': total, 'status': 'msg'}
  )
  ```
- **이유**: 실시간 진행률 표시, 장시간 작업 모니터링

### 결정: 병렬 처리 패턴
- **선택**: Celery group/chord 활용
- **구현**:
  - group: 독립적인 태스크 병렬 실행
  - chord: 병렬 실행 후 결과 집계
  - chain: 순차적 태스크 연결
- **이유**: 대량 데이터 처리 효율성, 시간 단축

### 결정: Beat 스케줄 설정
- **일일 작업**: 
  - check-data-gaps: 매일 오전 5시 ET
  - 주식 시장 개장 전 데이터 준비
- **주간 작업**:
  - weekly-backtesting: 일요일 오전 6시 ET
  - 주말 동안 전략 성능 검증
- **이유**: 시장 시간 외 처리로 API 부하 최소화

## 향후 결정 사항

### Phase 2에서 결정 예정
- 데이터 수집 병렬화 전략
- 캐싱 레이어 구현 (Redis)
- 데이터 압축 정책
- TimescaleDB 파티셔닝 전략

### Phase 3에서 결정 예정
- 백테스팅 엔진 최적화
- 전략 파라미터 최적화 방법
- 성능 메트릭 계산 방식
- 베이지안 최적화 구현

### Phase 4에서 결정 예정
- 실시간 스트리밍 프로토콜
- 주문 실행 우선순위
- 리스크 관리 규칙
- WebSocket 재연결 전략