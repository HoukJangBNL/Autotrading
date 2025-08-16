# Schwab API "We are unable to complete your request" Error Fix Guide
# Schwab API "요청을 완료할 수 없습니다" 오류 해결 가이드

## Error Description / 오류 설명

When you see: **"We are unable to complete your request. Please contact customer support for further assistance."**

이 오류가 표시될 때: **"We are unable to complete your request. Please contact customer support for further assistance."**

This error occurs during Schwab OAuth login and is usually due to app configuration issues.

이 오류는 Schwab OAuth 로그인 중에 발생하며 주로 앱 설정 문제로 인해 발생합니다.

## Most Common Cause: App Status / 가장 흔한 원인: 앱 상태

### ❗ CRITICAL: Check Your App Status / 중요: 앱 상태 확인

1. Go to https://developer.schwab.com/
2. Log in and check your app status
3. **Your app MUST show: "Ready for use"**
4. **NOT**: "Approved - Pending" ❌
5. **NOT**: "Pending" ❌
6. **ONLY**: "Ready for use" ✅

1. https://developer.schwab.com/ 접속
2. 로그인 후 앱 상태 확인
3. **앱 상태가 반드시: "Ready for use"**
4. **아님**: "Approved - Pending" ❌
5. **아님**: "Pending" ❌
6. **오직**: "Ready for use" ✅

### Why This Happens / 이런 일이 발생하는 이유

- Even if you see "Approved", your app might still be "Approved - Pending"
- Full approval can take 2-5 business days
- You must wait until status changes to "Ready for use"

- "Approved"가 표시되어도 실제로는 "Approved - Pending" 상태일 수 있음
- 완전한 승인까지 2-5 영업일 소요
- 상태가 "Ready for use"로 변경될 때까지 기다려야 함

## Step-by-Step Fix / 단계별 해결 방법

### Step 1: Run Troubleshooter / 1단계: 문제 해결 도구 실행

```bash
cd /Users/houkjang/Autotrading
source venv/bin/activate
python scripts/troubleshoot_schwab_auth.py
```

This will check your configuration and identify issues.
이것은 설정을 확인하고 문제를 식별합니다.

### Step 2: Check App in Schwab Portal / 2단계: Schwab 포털에서 앱 확인

1. Go to: https://developer.schwab.com/
2. Click "My Apps"
3. Find your app and check:
   - **Status**: Must be "Ready for use"
   - **App Key**: Copy exactly (no spaces)
   - **Callback URL**: Copy exactly

1. 접속: https://developer.schwab.com/
2. "My Apps" 클릭
3. 앱을 찾아서 확인:
   - **Status**: "Ready for use"여야 함
   - **App Key**: 정확히 복사 (공백 없이)
   - **Callback URL**: 정확히 복사

### Step 3: Update .env File / 3단계: .env 파일 업데이트

Edit `/Users/houkjang/Autotrading/.env`:

```bash
SCHWAB_API_KEY=<paste_exact_app_key_here>
SCHWAB_APP_SECRET=<paste_exact_app_secret_here>
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
```

**CRITICAL POINTS / 중요 사항:**
- No spaces before or after values / 값 앞뒤에 공백 없음
- No trailing slash on callback URL / 콜백 URL 끝에 슬래시 없음
- Must be HTTPS (not HTTP) / HTTPS여야 함 (HTTP 아님)

### Step 4: Verify Callback URL / 4단계: 콜백 URL 확인

In Schwab Developer Portal:
1. Your callback URL should be: `https://127.0.0.1:8182`
2. If you have multiple URLs, each must be on a separate line
3. Click "Add Another" for each URL
4. Do NOT put multiple URLs in one field

Schwab 개발자 포털에서:
1. 콜백 URL은: `https://127.0.0.1:8182`
2. 여러 URL이 있는 경우 각각 별도 줄에 입력
3. 각 URL마다 "Add Another" 클릭
4. 한 필드에 여러 URL 입력하지 말 것

### Step 5: If Still Not Working / 5단계: 여전히 작동하지 않는 경우

#### Option A: Wait / 옵션 A: 기다리기
- If status shows "Approved - Pending", wait 2-5 days
- Check daily for status change to "Ready for use"

- 상태가 "Approved - Pending"인 경우 2-5일 대기
- 매일 "Ready for use"로 변경되었는지 확인

#### Option B: Recreate App / 옵션 B: 앱 재생성
1. Delete current app in portal
2. Create new app with same settings
3. Wait for approval

1. 포털에서 현재 앱 삭제
2. 동일한 설정으로 새 앱 생성
3. 승인 대기

#### Option C: Contact Support / 옵션 C: 지원팀 연락
Email: traderapi@schwab.com

Include:
- Your app name
- Error message
- Output from troubleshoot script

포함 사항:
- 앱 이름
- 오류 메시지
- 문제 해결 스크립트 출력

## Alternative Solutions / 대체 해결책

### If 127.0.0.1 is blocked / 127.0.0.1이 차단된 경우

Some users report Schwab blocking 127.0.0.1. Try:
1. Use `localhost` instead: `https://localhost:8182`
2. Update both .env and Schwab portal

일부 사용자는 Schwab이 127.0.0.1을 차단한다고 보고. 시도:
1. 대신 `localhost` 사용: `https://localhost:8182`
2. .env와 Schwab 포털 모두 업데이트

### Test with Simple Script / 간단한 스크립트로 테스트

```bash
python scripts/test_oauth_simple.py
```

This bypasses our wrapper and tests schwab-py directly.
이것은 우리의 래퍼를 우회하고 schwab-py를 직접 테스트합니다.

## Common Mistakes / 흔한 실수

1. ❌ Thinking "Approved - Pending" means ready
2. ❌ Extra spaces in API key or secret
3. ❌ Trailing slash on callback URL
4. ❌ Using HTTP instead of HTTPS
5. ❌ Wrong port number (should be 8182)
6. ❌ Multiple URLs in one callback field

1. ❌ "Approved - Pending"가 준비됨을 의미한다고 생각
2. ❌ API 키나 시크릿에 추가 공백
3. ❌ 콜백 URL 끝에 슬래시
4. ❌ HTTPS 대신 HTTP 사용
5. ❌ 잘못된 포트 번호 (8182여야 함)
6. ❌ 하나의 콜백 필드에 여러 URL

## Quick Checklist / 빠른 체크리스트

- [ ] App status is "Ready for use" / 앱 상태가 "Ready for use"
- [ ] API key has no spaces / API 키에 공백 없음
- [ ] App secret has no spaces / 앱 시크릿에 공백 없음  
- [ ] Callback URL is exactly `https://127.0.0.1:8182` / 콜백 URL이 정확히 `https://127.0.0.1:8182`
- [ ] No trailing slash on callback URL / 콜백 URL 끝에 슬래시 없음
- [ ] .env matches Schwab portal exactly / .env가 Schwab 포털과 정확히 일치

## Still Having Issues? / 여전히 문제가 있나요?

1. Run: `python scripts/troubleshoot_schwab_auth.py`
2. Save the output
3. Email traderapi@schwab.com with:
   - App name
   - Error screenshot
   - Troubleshoot output

1. 실행: `python scripts/troubleshoot_schwab_auth.py`
2. 출력 저장
3. traderapi@schwab.com에 이메일:
   - 앱 이름
   - 오류 스크린샷
   - 문제 해결 출력