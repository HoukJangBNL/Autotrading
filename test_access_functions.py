#!/usr/bin/env python
"""
client_from_access_functions 사용 예제
"""

import json
from pathlib import Path
from schwab import auth
import asyncio

# 토큰 파일 경로
TOKEN_FILE = Path("config/schwab_token.json")

def token_read_func():
    """토큰을 읽는 함수"""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

def token_write_func(token):
    """토큰을 저장하는 함수"""
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token, f, indent=2)
    print(f"Token saved to {TOKEN_FILE}")

async def main():
    # API 정보
    API_KEY = "GX5bhoK6yptRyH2aTxEzddJjYTo52ONY"
    APP_SECRET = "yivSO2RUuwxOpb1m"
    
    # client_from_access_functions 사용
    client = auth.client_from_access_functions(
        api_key=API_KEY,
        app_secret=APP_SECRET,
        token_read_func=token_read_func,
        token_write_func=token_write_func,
        asyncio=True  # 비동기 클라이언트
    )
    
    # 테스트: 계정 번호 가져오기
    try:
        resp = await client.get_account_numbers()
        resp.raise_for_status()
        accounts = resp.json()
        print(f"Successfully connected! Found {len(accounts)} account(s)")
        for acc in accounts:
            print(f"  - Account: {acc['accountNumber']}, Hash: {acc['hashValue']}")
    except Exception as e:
        print(f"Error: {e}")
    
if __name__ == "__main__":
    asyncio.run(main())