#!/usr/bin/env python3
"""빠른 데이터 마이닝 시작 스크립트"""

import asyncio
import json
from datetime import datetime
from src.data.historical_data_collector_v2 import EnhancedHistoricalDataCollector as HistoricalDataCollector
from src.auth import get_auth_service
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def start_mining():
    """데이터 마이닝 시작"""
    
    print("=" * 60)
    print("📊 Historical Data Mining 시작")
    print("=" * 60)
    
    # 종목 리스트 로드
    with open('config/core_tickers.json', 'r') as f:
        config = json.load(f)
    
    # 테스트용으로 처음 10개 종목만
    symbols = config['core_tickers'][:10]  # 처음 10개로 시작
    
    print(f"✅ 수집 대상: {len(symbols)}개 종목")
    print(f"📌 종목: {', '.join(symbols)}")
    print("-" * 60)
    
    # 인증
    auth_service = get_auth_service()
    async with auth_service.get_authenticated_client() as client:
        if not client:
            print("❌ 인증 실패! 토큰을 확인하세요.")
            return
        
        print("✅ Schwab API 인증 성공")
        
        # 데이터 수집기 초기화
        collector = HistoricalDataCollector(client=client)
        
        # 각 종목 수집
        total_candles = 0
        success_count = 0
        start_time = datetime.now()
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] {symbol} 수집 중...")
            
            try:
                # 60일치 데이터 수집 (한번에!)
                result = await collector.collect_historical_data(
                    symbol=symbol,
                    days_back=60,
                    operation="initial"
                )
                
                if result['success']:
                    print(f"  ✅ {result['candles_added']:,}개 캔들 수집 완료 ({result['duration']:.1f}초)")
                    total_candles += result['candles_added']
                    success_count += 1
                else:
                    print(f"  ❌ 실패: {result['error']}")
                    
            except Exception as e:
                print(f"  ❌ 에러: {str(e)}")
        
        # 결과 요약
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("📊 마이닝 완료!")
        print("=" * 60)
        print(f"✅ 성공: {success_count}/{len(symbols)} 종목")
        print(f"📈 총 캔들: {total_candles:,}개")
        print(f"⏱️  소요 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
        print(f"⚡ 평균: {elapsed/len(symbols):.1f}초/종목")
        
        # 전체 예상 시간
        total_symbols = len(config['core_tickers'])
        estimated_total = (elapsed / len(symbols)) * total_symbols
        print(f"\n📍 전체 {total_symbols}개 종목 예상 시간: {estimated_total/60:.0f}분")

if __name__ == "__main__":
    asyncio.run(start_mining())