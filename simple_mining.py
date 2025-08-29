#!/usr/bin/env python3
"""간단한 데이터 마이닝 테스트"""

import asyncio
import json
from datetime import datetime, timedelta
from schwab import auth, client
import os

async def simple_mining():
    """schwab-py 직접 사용하여 마이닝"""
    
    print("=" * 60)
    print("📊 Simple Historical Data Mining")
    print("=" * 60)
    
    # Schwab 인증 정보
    api_key = os.getenv('SCHWAB_APP_KEY', 'GX5bhoK6yptRyH2aTxEzddJjYTo52ONY')
    app_secret = os.getenv('SCHWAB_APP_SECRET', 'yivSO2RUuwxOpb1m')
    callback_url = 'https://127.0.0.1:8182/api/auth/callback'
    token_path = 'config/schwab_token.json'
    
    try:
        # schwab-py easy_client로 인증
        c = auth.easy_client(
            api_key,
            app_secret,
            callback_url,
            token_path,
            asyncio=False  # 동기 모드
        )
        
        print("✅ Schwab API 인증 성공")
        
        # 테스트 종목
        symbols = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA']
        
        print(f"📌 수집 대상: {symbols}")
        print("-" * 60)
        
        total_candles = 0
        
        for symbol in symbols:
            print(f"\n📊 {symbol} 수집 중...")
            
            # 60일 전 날짜 계산
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            
            # 1분봉 데이터 가져오기 (한번에!)
            response = c.get_price_history_every_minute(
                symbol=symbol,
                start_datetime=start_date,
                end_datetime=end_date,
                need_extended_hours_data=True
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'candles' in data:
                    candle_count = len(data['candles'])
                    total_candles += candle_count
                    print(f"  ✅ {candle_count:,}개 캔들 수집 완료")
                    
                    # 샘플 데이터 출력
                    if candle_count > 0:
                        first_candle = data['candles'][0]
                        last_candle = data['candles'][-1]
                        print(f"  📅 기간: {datetime.fromtimestamp(first_candle['datetime']/1000).strftime('%Y-%m-%d')} ~ {datetime.fromtimestamp(last_candle['datetime']/1000).strftime('%Y-%m-%d')}")
                else:
                    print(f"  ⚠️ 캔들 데이터 없음")
            else:
                print(f"  ❌ API 에러: {response.status_code}")
        
        print("\n" + "=" * 60)
        print("📊 수집 완료!")
        print(f"✅ 총 {total_candles:,}개 캔들 수집")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_mining())