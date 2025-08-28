# Schwab OAuth 설정 가이드

## 🔴 중요: 401 Unauthorized 에러 해결

### 1. Schwab Developer Portal 설정 확인

Schwab Developer Portal (https://developer.schwab.com)에서 다음 사항을 확인하세요:

#### App 설정
1. **App Status**: "Ready for use"인지 확인
2. **App Key**: `.env` 파일의 `SCHWAB_API_KEY`와 일치
3. **App Secret**: `.env` 파일의 `SCHWAB_APP_SECRET`와 일치

#### Callback URL 설정
**정확한 Callback URL** (한 글자도 틀리면 안됨):
```
https://127.0.0.1:8182/api/auth/callback
```

주의사항:
- `https` (not http)
- `127.0.0.1` (not localhost)
- Port `8182`
- Path `/api/auth/callback`

### 2. 현재 설정 (.env 파일)
```bash
SCHWAB_API_KEY=GX5bhoK6yptRyH2aTxEzddJjYTo52ONY
SCHWAB_APP_SECRET=yivSO2RUuwxOpb1m
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182/api/auth/callback
```

### 3. 401 에러 발생 원인

**가능한 원인들:**
1. ❌ **App Secret이 잘못됨** - Developer Portal에서 다시 확인
2. ❌ **Callback URL 불일치** - 한 글자라도 다르면 실패
3. ❌ **App이 활성화되지 않음** - Portal에서 App 상태 확인
4. ❌ **PKCE 검증 실패** - code_verifier가 올바르지 않음

### 4. 디버깅 단계

1. **Schwab Developer Portal 확인**
   - App Details 페이지로 이동
   - App Secret 다시 생성 (Regenerate Secret)
   - 새 Secret을 `.env` 파일에 업데이트

2. **Callback URL 확인**
   - Developer Portal의 "Callback URL" 필드 확인
   - 정확히 `https://127.0.0.1:8182/api/auth/callback` 입력

3. **테스트**
   ```bash
   # 1. 서버 재시작
   # 2. 브라우저에서 테스트
   https://localhost:3000/oauth-test.html
   ```

### 5. Schwab API 응답 분석

401 에러 응답 본문을 확인하면 정확한 에러 원인을 알 수 있습니다:
- `invalid_client`: API Key/Secret 문제
- `invalid_grant`: Authorization code 문제
- `invalid_request`: 요청 파라미터 문제

### 6. 해결 순서

1. **Developer Portal에서 App Secret 재생성**
2. **새 Secret을 `.env` 파일에 업데이트**
3. **Callback URL 정확히 확인**
4. **서버 재시작**
5. **새로운 브라우저 시크릿 창에서 테스트**

### 7. 추가 확인 사항

- Schwab 계정이 개발자 액세스 권한이 있는지 확인
- App이 "Trading API" 권한을 가지고 있는지 확인
- Rate limiting에 걸리지 않았는지 확인 (너무 많은 시도)