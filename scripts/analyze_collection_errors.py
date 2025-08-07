#!/usr/bin/env python3
"""
Collection Error Analysis Script

Analyzes collection logs to identify patterns, problematic symbols,
and provides insights for improving data collection reliability.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, CollectionLog
from shared.utils.error_analysis import ErrorAnalyzer
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CollectionErrorAnalyzer:
    """Analyze collection errors and provide insights."""
    
    def __init__(self):
        self.session = None
        
    async def analyze_recent_errors(self, days: int = 7) -> Dict:
        """Analyze collection errors from the last N days."""
        logger.info(f"🔍 Analyzing collection errors from the last {days} days...")
        
        # Initialize database
        await init_db()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with AsyncSessionLocal() as session:
            # Get failed collection logs with symbols
            result = await session.execute(
                select(CollectionLog, Symbol)
                .join(Symbol, CollectionLog.symbol_id == Symbol.id)
                .where(
                    and_(
                        CollectionLog.status == "failed",
                        CollectionLog.started_at >= cutoff_date
                    )
                )
                .options(selectinload(CollectionLog))
                .order_by(desc(CollectionLog.started_at))
            )
            
            failed_logs = result.fetchall()
            
            if not failed_logs:
                logger.info("✅ No failed collections found in the specified period")
                return {"total_errors": 0}
                
            # Analyze error patterns
            analysis = {
                "total_errors": len(failed_logs),
                "error_by_code": Counter(),
                "error_by_type": Counter(),
                "error_by_symbol": Counter(),
                "error_by_date": defaultdict(int),
                "problematic_symbols": [],
                "error_details": [],
                "recommendations": []
            }
            
            for log_entry, symbol in failed_logs:
                # Count by error code
                if log_entry.error_code:
                    analysis["error_by_code"][log_entry.error_code] += 1
                    
                # Count by error type
                if log_entry.error_type:
                    analysis["error_by_type"][log_entry.error_type] += 1
                    
                # Count by symbol
                analysis["error_by_symbol"][symbol.symbol] += 1
                
                # Count by date
                date_key = log_entry.started_at.strftime("%Y-%m-%d")
                analysis["error_by_date"][date_key] += 1
                
                # Store detailed error info
                error_detail = {
                    "symbol": symbol.symbol,
                    "error_code": log_entry.error_code,
                    "error_type": log_entry.error_type,
                    "error_message": log_entry.error_message,
                    "timestamp": log_entry.started_at.isoformat(),
                    "retry_count": log_entry.retry_count or 0
                }
                
                if log_entry.error_details:
                    error_detail["analysis"] = log_entry.error_details
                    
                analysis["error_details"].append(error_detail)
            
            # Identify problematic symbols (multiple failures)
            for symbol, count in analysis["error_by_symbol"].most_common():
                if count >= 3:  # 3 or more failures
                    analysis["problematic_symbols"].append({
                        "symbol": symbol,
                        "failure_count": count,
                        "failure_rate": round(count / len(failed_logs) * 100, 1)
                    })
            
            # Generate recommendations
            analysis["recommendations"] = self._generate_recommendations(analysis)
            
            return analysis
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations based on error analysis."""
        recommendations = []
        
        # Check for high-frequency error codes
        top_error_codes = analysis["error_by_code"].most_common(3)
        for error_code, count in top_error_codes:
            if error_code == 200:
                recommendations.append(
                    f"🚨 {count} 'No security definition' errors (Code 200) - "
                    "Consider running symbol cleanup script to deactivate delisted symbols"
                )
            elif error_code in [1100, 1102]:
                recommendations.append(
                    f"🔌 {count} connectivity errors (Code {error_code}) - "
                    "Check IBKR TWS/Gateway connection stability"
                )
            elif error_code == 162:
                recommendations.append(
                    f"⏰ {count} pacing violations (Code 162) - "
                    "Consider increasing delay between requests"
                )
        
        # Check for problematic symbols
        if analysis["problematic_symbols"]:
            symbol_count = len(analysis["problematic_symbols"])
            recommendations.append(
                f"📊 {symbol_count} symbols with multiple failures - "
                "Consider investigating these symbols for issues"
            )
            
        # Check error distribution
        if len(analysis["error_by_date"]) == 1:
            recommendations.append(
                "📅 All errors occurred on a single day - "
                "Likely a temporary system issue"
            )
        elif analysis["total_errors"] > 50:
            recommendations.append(
                "⚠️  High error volume - "
                "Consider reviewing collection configuration and system health"
            )
            
        return recommendations
    
    async def get_error_trends(self, days: int = 30) -> Dict:
        """Get error trends over time."""
        logger.info(f"📈 Analyzing error trends over {days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with AsyncSessionLocal() as session:
            # Get daily error counts
            result = await session.execute(
                select(
                    func.date(CollectionLog.started_at).label('date'),
                    func.count(CollectionLog.id).label('error_count'),
                    func.count(func.distinct(CollectionLog.symbol_id)).label('unique_symbols')
                )
                .where(
                    and_(
                        CollectionLog.status == "failed",
                        CollectionLog.started_at >= cutoff_date
                    )
                )
                .group_by(func.date(CollectionLog.started_at))
                .order_by(func.date(CollectionLog.started_at))
            )
            
            daily_stats = result.fetchall()
            
            trends = {
                "daily_errors": {},
                "daily_unique_symbols": {},
                "total_days": len(daily_stats),
                "average_daily_errors": 0,
                "peak_error_day": None,
                "peak_error_count": 0
            }
            
            if daily_stats:
                total_errors = 0
                for stat in daily_stats:
                    date_str = stat.date.strftime("%Y-%m-%d")
                    trends["daily_errors"][date_str] = stat.error_count
                    trends["daily_unique_symbols"][date_str] = stat.unique_symbols
                    total_errors += stat.error_count
                    
                    if stat.error_count > trends["peak_error_count"]:
                        trends["peak_error_count"] = stat.error_count
                        trends["peak_error_day"] = date_str
                        
                trends["average_daily_errors"] = round(total_errors / len(daily_stats), 1)
            
            return trends
    
    def print_analysis_report(self, analysis: Dict, trends: Dict = None):
        """Print a formatted analysis report."""
        print("\n" + "="*70)
        print("📊 COLLECTION ERROR ANALYSIS REPORT")
        print("="*70)
        
        # Summary
        print(f"\n📈 SUMMARY")
        print(f"   • Total Errors: {analysis['total_errors']}")
        if trends:
            print(f"   • Average Daily Errors: {trends['average_daily_errors']}")
            print(f"   • Peak Error Day: {trends['peak_error_day']} ({trends['peak_error_count']} errors)")
        
        # Top error codes
        print(f"\n🔢 TOP ERROR CODES")
        for error_code, count in analysis["error_by_code"].most_common(5):
            percentage = round(count / analysis["total_errors"] * 100, 1)
            error_category = ErrorAnalyzer.IBKR_ERROR_CATEGORIES.get(error_code, "Unknown")
            print(f"   • Code {error_code}: {count} errors ({percentage}%) - {error_category}")
        
        # Top error types
        print(f"\n🏷️  TOP ERROR TYPES")
        for error_type, count in analysis["error_by_type"].most_common(5):
            percentage = round(count / analysis["total_errors"] * 100, 1)
            print(f"   • {error_type}: {count} errors ({percentage}%)")
        
        # Problematic symbols
        if analysis["problematic_symbols"]:
            print(f"\n⚠️  PROBLEMATIC SYMBOLS")
            for symbol_info in analysis["problematic_symbols"][:10]:  # Top 10
                print(f"   • {symbol_info['symbol']}: {symbol_info['failure_count']} failures "
                      f"({symbol_info['failure_rate']}%)")
        
        # Recommendations
        if analysis["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"   {i}. {rec}")
        
        print("\n" + "="*70)


async def main():
    """Main execution function."""
    analyzer = CollectionErrorAnalyzer()
    
    try:
        # Analyze recent errors
        analysis = await analyzer.analyze_recent_errors(days=7)
        
        # Get trends
        trends = await analyzer.get_error_trends(days=30)
        
        # Print report
        analyzer.print_analysis_report(analysis, trends)
        
        # Save detailed results
        if analysis["total_errors"] > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"logs/error_analysis_{timestamp}.json"
            
            import json
            with open(report_file, 'w') as f:
                # Combine analysis and trends
                full_report = {
                    "generated_at": datetime.now().isoformat(),
                    "analysis_period_days": 7,
                    "trends_period_days": 30,
                    "error_analysis": analysis,
                    "error_trends": trends
                }
                json.dump(full_report, f, indent=2, default=str)
                
            print(f"\n💾 Detailed report saved to: {report_file}")
        
    except Exception as e:
        logger.error(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
