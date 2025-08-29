#!/usr/bin/env python3
"""Smart gap filling script for updating historical data."""

import asyncio
import argparse
import json
from datetime import datetime
from src.data.smart_gap_filler import SmartGapFiller
from src.auth import get_auth_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def main(args):
    """Main execution function."""
    
    print("=" * 60)
    print("📊 Smart Gap Filling System")
    print("=" * 60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    if args.symbols:
        print(f"📌 Specific symbols: {', '.join(args.symbols)}")
    if args.max_gap:
        print(f"📏 Max gap: {args.max_gap} days")
    
    print("-" * 60)
    
    # Get authenticated client
    auth_service = get_auth_service()
    async with auth_service.get_authenticated_client() as client:
        if not client:
            print("❌ Failed to authenticate with Schwab API")
            return
        
        print("✅ Authentication successful")
        
        # Initialize SmartGapFiller
        filler = SmartGapFiller(client=client)
        
        # Step 1: Analyze gaps
        print("\n🔍 Analyzing gaps...")
        
        if args.dry_run:
            # Dry run - just show what would be done
            summary = await filler.get_gap_summary()
            
            print("\n📊 Gap Analysis Summary:")
            print(f"  Total symbols: {summary['total_symbols']}")
            print(f"  Up to date: {summary['up_to_date']}")
            print(f"  Small gaps (1-2 days): {summary['small_gaps']}")
            print(f"  Large gaps (2+ days): {summary['large_gaps']}")
            print(f"  Average gap: {summary['average_gap_days']} days")
            print(f"  Estimated time: {summary['estimated_time_seconds']:.0f} seconds")
            
            if summary['small_gaps'] + summary['large_gaps'] > 0:
                print("\n💡 Run without --dry-run to fill these gaps")
            
            return
        
        # Step 2: Process specific symbols or all gaps
        if args.symbols:
            # Process specific symbols
            print(f"\n⚡ Processing {len(args.symbols)} specific symbols...")
            results = await filler.fill_specific_symbols(
                symbols=args.symbols,
                days_back=args.days_back
            )
        else:
            # Process all gaps
            gap_data = await filler.analyze_gaps()
            categorized = await filler.categorize_symbols(gap_data)
            
            # Apply max_gap filter if specified
            if args.max_gap:
                filtered_small = [(s, d) for s, d in categorized['small_gap'] if d <= args.max_gap]
                filtered_large = [(s, d) for s, d in categorized['large_gap'] if d <= args.max_gap]
                
                print(f"\n📏 Filtered to gaps <= {args.max_gap} days:")
                print(f"  Small gaps: {len(filtered_small)}")
                print(f"  Large gaps: {len(filtered_large)}")
                
                categorized['small_gap'] = filtered_small
                categorized['large_gap'] = filtered_large
            
            # Display gap summary
            total_to_process = len(categorized['small_gap']) + len(categorized['large_gap'])
            
            if total_to_process == 0:
                print("\n✨ All symbols are up to date!")
                return
            
            print(f"\n📈 Found gaps to fill:")
            print(f"  Small gaps (1-2 days): {len(categorized['small_gap'])}")
            print(f"  Large gaps (2+ days): {len(categorized['large_gap'])}")
            print(f"  Total to process: {total_to_process}")
            
            # Estimate time
            estimated_time = total_to_process * 0.51
            print(f"\n⏱️  Estimated time: {estimated_time:.0f} seconds ({estimated_time/60:.1f} minutes)")
            
            # Start processing
            print(f"\n⚡ Starting data collection (Rate limit: 2 req/sec)")
            print("-" * 60)
            
            results = await filler.fill_gaps_sequential(categorized)
        
        # Step 3: Display results
        if results:
            print("\n" + "=" * 60)
            print("📊 RESULTS SUMMARY")
            print("=" * 60)
            
            # Calculate statistics
            total_candles = sum(r.get('candles_added', 0) for r in results)
            success_count = sum(1 for r in results if r.get('success', False))
            failed_count = len(results) - success_count
            
            print(f"✅ Successful: {success_count}/{len(results)} symbols")
            if failed_count > 0:
                print(f"❌ Failed: {failed_count} symbols")
                # Show failed symbols
                failed = [r['symbol'] for r in results if not r.get('success', False)]
                if failed:
                    print(f"   Failed symbols: {', '.join(failed[:10])}")
                    if len(failed) > 10:
                        print(f"   ... and {len(failed)-10} more")
            
            print(f"📊 Total candles: {total_candles:,}")
            print(f"⏱️  Total time: {(datetime.now() - datetime.fromisoformat(datetime.now().isoformat())).total_seconds():.1f}s")
            
            # Save results to file if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'summary': {
                            'total_symbols': len(results),
                            'successful': success_count,
                            'failed': failed_count,
                            'total_candles': total_candles
                        },
                        'results': results
                    }, f, indent=2)
                print(f"\n💾 Results saved to: {args.output}")
    
    print("\n✨ Gap filling completed!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smart gap filling for historical market data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze gaps without filling (dry run)
  python fill_latest_gaps.py --dry-run
  
  # Fill all gaps
  python fill_latest_gaps.py
  
  # Fill gaps for specific symbols
  python fill_latest_gaps.py --symbols AAPL MSFT GOOGL
  
  # Fill only gaps smaller than 7 days
  python fill_latest_gaps.py --max-gap 7
  
  # Save results to file
  python fill_latest_gaps.py --output results.json
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze gaps without filling them'
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Process only these symbols (e.g., AAPL MSFT)'
    )
    
    parser.add_argument(
        '--days-back',
        type=int,
        help='Override days to collect for specific symbols'
    )
    
    parser.add_argument(
        '--max-gap',
        type=int,
        help='Only fill gaps smaller than this many days'
    )
    
    parser.add_argument(
        '--output',
        help='Save results to JSON file'
    )
    
    args = parser.parse_args()
    
    # Run the async main function
    asyncio.run(main(args))