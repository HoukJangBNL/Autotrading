---
type: "always_apply"
---

🧠 SYSTEM PROMPT (엔지니어링 팀 공통)

“다음 요구사항을 만족하는 Autotrading 플랫폼을 구현한다.

아키텍처: Backend(항시 가동) + Frontend(하이레벨 제어/모니터링). 백엔드는 3가지 모드(DataMining, Backtesting, Trading)로 동작하며 동일 프로세스 내 모듈 또는 분리된 워커/서비스로 구동해도 됨. 모드는 FE에서 전환/시작/중지/상태조회.

데이터 소스/거래소: 실거래/페이퍼 모드 교체 가능한 어댑터 패턴(ExchangeAdapter). 1분봉 기준. 타임존/휴장일 처리.

DB: PostgreSQL(+TimescaleDB 권장). 테이블은 Symbols, MinuteBars, Trades, Positions, Orders, Strategies, Backtests, OptimRuns, Weights, Jobs, Signals, Config.

큐/스케줄러: Redis 기반 큐(예: RQ/Celery) 또는 내장 asyncio task. 주기적 잡과 실시간 이벤트 분리. 로깅/메트릭 필수.

테스트: 단위/통합 테스트와 리그레션 픽스처. 시뮬레이션 시드 고정. 백테스트 재현성 보장.

확장성: 전략은 플러그인(엔트리포인트/폴더 스캔)으로 핫로드/언로드. 파라미터 스키마(JSONSchema)로 검증.

관측성: Prometheus 지표/헬스체크, 구조화 로그(JSON), 이벤트 트레이스. 에러는 Sentry 등 훅.

보안: API 키 암호화 저장(.env/OS keyring). RBAC(운용/관찰 권한 분리).”