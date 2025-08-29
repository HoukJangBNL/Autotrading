#!/usr/bin/env python3
"""Test smart gap filling API calls with rate limiting."""

import asyncio
import time
from datetime import datetime, timedelta
from schwab import auth
import os

async def test_rate_limit():
    """Test API calls with rate limiting."""
    
    print("=" * 60)
    print("📊 Smart Gap Filling API Test")
    print("=" * 60)
    
    # Schwab authentication
    api_key = os.getenv('SCHWAB_APP_KEY', 'GX5bhoK6yptRyH2aTxEzddJjYTo52ONY')
    app_secret = os.getenv('SCHWAB_APP_SECRET', 'yivSO2RUuwxOpb1m')
    callback_url = 'https://127.0.0.1:8182/api/auth/callback'
    token_path = 'config/schwab_token.json'
    
    try:
        # Use synchronous client
        c = auth.easy_client(
            api_key,
            app_secret,
            callback_url,
            token_path,
            asyncio=False
        )
        
        print("✅ Schwab API 인증 성공")
        
        # Test symbols with simulated gaps
        test_data = [
            ('AAPL', 1),   # 1 day gap
            ('MSFT', 2),   # 2 day gap  
            ('GOOGL', 3),  # 3 day gap
            ('NVDA', 1),   # 1 day gap
            ('TSLA', 5),   # 5 day gap
        ]
        
        print(f"\n⚡ Rate Limit 테스트: 2 requests/second (0.51초 간격)")
        print("-" * 60)
        
        total_candles = 0
        start_time = time.time()
        
        for i, (symbol, gap_days) in enumerate(test_data, 1):
            symbol_start = time.time()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=gap_days)
            
            print(f"\n[{i}/{len(test_data)}] {symbol} ({gap_days}일 갭)")
            print(f"  📅 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            
            try:
                # Get 1-minute data
                response = c.get_price_history_every_minute(
                    symbol=symbol,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    need_extended_hours_data=True
                )
                
                api_time = time.time() - symbol_start
                
                if response.status_code == 200:
                    data = response.json()
                    if 'candles' in data:
                        candle_count = len(data['candles'])
                        total_candles += candle_count
                        print(f"  ✅ {candle_count:,}개 캔들 수집 (API: {api_time:.2f}초)")
                    else:
                        print(f"  ⚠️ 캔들 데이터 없음")
                else:
                    print(f"  ❌ API 에러: {response.status_code}")
                
                # Rate limit compliance (0.51초 간격)
                if i < len(test_data):
                    print(f"  ⏱️ Rate limit delay: 0.51초...")
                    await asyncio.sleep(0.51)
                    
            except Exception as e:
                print(f"  ❌ 에러: {str(e)}")
        
        # Summary
        total_time = time.time() - start_time
        avg_time = total_time / len(test_data)
        
        print(f"\n" + "=" * 60)
        print(f"📊 테스트 결과")
        print(f"=" * 60)
        print(f"✅ 처리 종목: {len(test_data)}개")
        print(f"📊 총 캔들: {total_candles:,}개")
        print(f"⏱️ 총 시간: {total_time:.1f}초")
        print(f"⚡ 평균 시간/종목: {avg_time:.2f}초")
        print(f"🎯 Rate: {len(test_data)/total_time:.2f} requests/second")
        
        # Projection for 48 symbols
        projected_time = avg_time * 48
        print(f"\n📈 48개 종목 예상 시간: {projected_time:.0f}초 ({projected_time/60:.1f}분)")
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rate_limit())