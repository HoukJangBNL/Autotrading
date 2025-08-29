#!/usr/bin/env python3
"""Simple gap filling test script."""

import asyncio
import json
import os
from datetime import datetime, timedelta
from schwab import auth
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from src.models.market_data import MiningStatus
import pytz

# EST timezone
EST = pytz.timezone('US/Eastern')

def analyze_gaps():
    """Analyze gaps in database."""
    # Database connection
    db_url = os.getenv("DATABASE_URL", "postgresql://houkjang@localhost/autotrading")
    engine = create_engine(db_url)
    
    current_time = datetime.now(pytz.UTC)
    gap_data = {}
    
    with Session(engine) as session:
        # Get latest timestamp for each active symbol
        result = session.execute(
            select(
                MiningStatus.symbol,
                MiningStatus.last_date,
                MiningStatus.is_active
            ).where(MiningStatus.is_active == True)
        ).all()
        
        print(f"\n📊 총 {len(result)}개 종목 분석")
        print("-" * 60)
        
        for symbol, last_date, is_active in result:
            if last_date:
                # Calculate gap in days
                gap = current_time - last_date
                gap_days = gap.days
                
                if gap_days > 0:
                    gap_data[symbol] = (symbol, last_date, gap_days)
                    
                    # Show first few for debugging
                    if len(gap_data) <= 5:
                        print(f"  {symbol}: 마지막 데이터 {last_date.strftime('%Y-%m-%d %H:%M')} ({gap_days}일 전)")
            else:
                # No data at all
                gap_data[symbol] = (symbol, None, 60)
                if len(gap_data) <= 5:
                    print(f"  {symbol}: 데이터 없음 (60일 수집 필요)")
    
    # Categorize
    categorized = {
        'no_gap': [],
        'small_gap': [],  # 1-2 days
        'large_gap': []   # 2+ days
    }
    
    for symbol, (_, last_date, gap_days) in gap_data.items():
        if gap_days < 1:
            categorized['no_gap'].append((symbol, gap_days))
        elif gap_days <= 2:
            categorized['small_gap'].append((symbol, gap_days))
        else:
            categorized['large_gap'].append((symbol, gap_days))
    
    print(f"\n📈 갭 분석 결과:")
    print(f"  ✅ 최신 상태: {len(categorized['no_gap'])}개")
    print(f"  ⚠️  1-2일 갭: {len(categorized['small_gap'])}개")
    print(f"  ❌ 2일+ 갭: {len(categorized['large_gap'])}개")
    
    # Show examples
    if categorized['small_gap']:
        print(f"\n1-2일 갭 종목 예시:")
        for symbol, days in categorized['small_gap'][:3]:
            print(f"  - {symbol}: {days}일")
    
    if categorized['large_gap']:
        print(f"\n2일+ 갭 종목 예시:")
        for symbol, days in categorized['large_gap'][:3]:
            print(f"  - {symbol}: {days}일")
    
    # Time estimate
    total_to_process = len(categorized['small_gap']) + len(categorized['large_gap'])
    if total_to_process > 0:
        estimated_time = total_to_process * 0.51
        print(f"\n⏱️  예상 소요 시간: {estimated_time:.0f}초 ({estimated_time/60:.1f}분)")
    
    return categorized

async def simple_fill_test():
    """Simple test of gap filling with first few symbols."""
    
    print("=" * 60)
    print("📊 Smart Gap Filling Test")
    print("=" * 60)
    
    # First analyze gaps
    categorized = analyze_gaps()
    
    # Get authenticated client
    api_key = os.getenv('SCHWAB_APP_KEY', 'GX5bhoK6yptRyH2aTxEzddJjYTo52ONY')
    app_secret = os.getenv('SCHWAB_APP_SECRET', 'yivSO2RUuwxOpb1m')
    callback_url = 'https://127.0.0.1:8182/api/auth/callback'
    token_path = 'config/schwab_token.json'
    
    # Test with first 3 symbols from small_gap
    test_symbols = categorized['small_gap'][:3] if categorized['small_gap'] else []
    
    if not test_symbols:
        print("\n✨ 모든 종목이 최신 상태입니다!")
        return
    
    print(f"\n🧪 테스트: {len(test_symbols)}개 종목 수집")
    print("-" * 60)
    
    try:
        # Use synchronous client for simplicity
        c = auth.easy_client(
            api_key,
            app_secret,
            callback_url,
            token_path,
            asyncio=False
        )
        
        print("✅ Schwab API 인증 성공")
        
        total_candles = 0
        
        for i, (symbol, gap_days) in enumerate(test_symbols, 1):
            print(f"\n[{i}/{len(test_symbols)}] {symbol} 처리 중...")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=gap_days + 1)
            
            try:
                # Get 1-minute data
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
                    else:
                        print(f"  ⚠️ 캔들 데이터 없음")
                else:
                    print(f"  ❌ API 에러: {response.status_code}")
                    
                # Rate limit compliance
                if i < len(test_symbols):
                    await asyncio.sleep(0.51)
                    
            except Exception as e:
                print(f"  ❌ 에러: {str(e)}")
        
        print(f"\n" + "=" * 60)
        print(f"📊 테스트 완료!")
        print(f"✅ 총 {total_candles:,}개 캔들 수집")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # First just analyze
    print("\n🔍 먼저 갭 분석만 실행...")
    analyze_gaps()
    
    # Ask if want to test
    response = input("\n💡 테스트로 처음 3개 종목을 수집할까요? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(simple_fill_test())