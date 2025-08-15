# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an auto-trading system designed for algorithmic trading. The system includes broker integration, data analysis, trading strategies, and order execution capabilities.

## Core Architecture

### Module Structure
- **broker/**: Broker API integration layer
  - `broker_api.py`: Main broker interface implementation
  
- **data/**: Data fetching and analysis components
  - `data_fetcher.py`: Real-time and historical data retrieval
  - `data_analyzer.py`: Technical analysis and indicators
  - `credentials.py`: API credentials management (NEVER commit actual credentials)
  
- **strategy/**: Trading strategy implementations
  - `strategy.py`: Base strategy class/interface
  - `gap_filling_trading.py`: Gap filling strategy implementation
  - `squeeze_trading.py`: Squeeze momentum strategy implementation
  
- **trader/**: Trade execution and management
  - `trader.py`: Main trading engine coordinating strategies and execution
  
- **utils/**: Shared utilities
  - `base_class.py`: Common base classes
  - `logger_manager.py`: Centralized logging configuration
  - `logger_mixin.py`: Logging mixin for consistent logging across classes
  - `order.py`: Order data structures and management

## Development Commands

### Running the System
```bash
# Main entry point
python main.py

# Run with specific configuration
python main.py --config config.json
```

### Testing
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_<module>.py

# Run with coverage
python -m pytest --cov=. --cov-report=html
```

### Code Quality
```bash
# Linting
python -m pylint broker/ data/ strategy/ trader/ utils/

# Type checking
python -m mypy .

# Format code
python -m black .
```

## Key Considerations

1. **Broker Integration**: The broker API is the critical interface for order execution. Always validate connection status and handle API rate limits.

2. **Data Pipeline**: Data fetching and analysis must be reliable and handle market hours, holidays, and data gaps appropriately.

3. **Strategy Safety**: Trading strategies should include:
   - Position size limits
   - Risk management rules
   - Stop-loss and take-profit logic
   - Market condition checks

4. **Error Handling**: Financial systems require robust error handling:
   - Network failures
   - API errors
   - Data inconsistencies
   - Order rejections

5. **Logging**: Use the logger_mixin for consistent logging across all components. Log all trades, errors, and important state changes.

## Security Notes

- Store API credentials in environment variables or secure credential stores
- Never log sensitive information (API keys, account numbers)
- Implement rate limiting to avoid API bans
- Use secure connections (HTTPS/SSL) for all broker communications

## Common Development Patterns

- Inherit from base classes in `utils/base_class.py` for consistent behavior
- Use the logger mixin for all classes that need logging
- Implement strategies by extending the base strategy class
- Handle market hours and trading calendar in data fetching logic

## Project Configuration and Development Guidelines

### Imports (lightweight context)
- See @README.md for overview, @package.json for scripts, @docs/ARCHITECTURE.md
- Individual preferences can be imported by each dev: @~/.claude/my-project.md

### Stack & Versions
- Runtime: Node 20.x / Python 3.11
- Frontend: Next.js 14 / Tailwind 3
- Backend: FastAPI + SQLAlchemy
- DB: Postgres 15; Migrations via Alembic

### Project Structure (top-level)
- apps/web, apps/api, packages/ui, packages/config, infra
- src/legacy: historical/fragile — 읽기 전용

### Commands (do not guess; use exactly)
- Setup: npm ci && npm run build
- Test (web): npm run test:web
- Test (api): pytest -q
- Lint/Format: npm run lint && npm run format:check
- Run one-shot checks only; dev/watch/server는 실행 금지 → 명령만 에코

### Code Style & Conventions
- TS: strictNullChecks on, 2-space indent, ES Modules only
- Python: type hints mandatory; black/isort
- Naming: no abbreviations; descriptive identifiers
- Error handling: bubble up; no blanket try/except

### Quality Gates
- 모든 변경엔 테스트 추가/수정. 커버리지 ↓ 금지.
- 성능 민감 경로(apps/api/services/*): O(N)→O(N log N) 악화 금지.

### Security Rules
- 절대 수정 금지: infra/**, deploy/**, scripts/rotate-keys.sh
- 비밀/크리덴셜 파일 접근 금지(설정에서 강제 차단됨)

### PR & Commit
- Small PRs only (<300 changed lines). 하나의 의도만.
- PR 템플릿 필수 항목: Motivation, Approach, Risks, Tests, Rollback

### Glossary (domain-specific)
- "Module": data-processing pipeline under src/modules/*
- "Tenant": org-level workspace; never equals "account"