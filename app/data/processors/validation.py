import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.data.models.market import DailyPrice

logger = structlog.get_logger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Single validation issue"""
    symbol: str
    date: Optional[datetime]
    severity: ValidationSeverity
    issue_type: str
    description: str
    current_value: Optional[float] = None
    expected_value: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    symbol: str
    total_records: int
    validation_date: datetime
    issues: List[ValidationIssue]
    quality_score: float  # 0-100
    data_completeness: float  # 0-100
    anomaly_count: int
    gap_count: int
    summary: Dict[str, Any]


class DataValidator:
    """
    Market data validation and quality assessment
    Implements comprehensive checks for price data integrity
    """
    
    def __init__(self):
        # Market-specific validation parameters
        self.min_price = 0.001  # Minimum valid price (0.1 cents)
        self.max_price = 10000.0  # Maximum reasonable price for stocks
        self.max_daily_change = 0.50  # 50% maximum daily change (generous for volatility)
        self.min_volume = 0  # Minimum volume (0 is valid for some stocks)
        self.max_volume = 1000000000  # 1 billion shares max
        
        # Gap detection parameters
        self.max_trading_gap_days = 5  # Maximum gap between trading days
        
    async def validate_symbol_data(self, symbol: str, db_session: AsyncSession, 
                                 days_lookback: int = 30) -> ValidationReport:
        """
        Comprehensive validation of symbol data
        
        Args:
            symbol: Stock symbol to validate
            db_session: Database session
            days_lookback: Number of days to look back for validation
            
        Returns:
            ValidationReport with all validation results
        """
        cutoff_date = datetime.now().date() - timedelta(days=days_lookback)
        
        # Fetch data for validation
        result = await db_session.execute(
            select(DailyPrice)
            .where(DailyPrice.symbol == symbol)
            .where(DailyPrice.date >= cutoff_date)
            .order_by(DailyPrice.date)
        )
        
        price_records = result.scalars().all()
        
        if not price_records:
            return ValidationReport(
                symbol=symbol,
                total_records=0,
                validation_date=datetime.now(),
                issues=[ValidationIssue(
                    symbol=symbol,
                    date=None,
                    severity=ValidationSeverity.ERROR,
                    issue_type="NO_DATA",
                    description="No price data found for validation period"
                )],
                quality_score=0.0,
                data_completeness=0.0,
                anomaly_count=0,
                gap_count=0,
                summary={"status": "no_data"}
            )
        
        # Convert to DataFrame for analysis
        df = self._records_to_dataframe(price_records)
        
        # Run all validation checks
        issues = []
        issues.extend(self._validate_price_logic(df, symbol))
        issues.extend(self._validate_volume_logic(df, symbol))
        issues.extend(self._detect_price_anomalies(df, symbol))
        issues.extend(self._detect_volume_anomalies(df, symbol))
        issues.extend(self._validate_data_completeness(df, symbol, days_lookback))
        issues.extend(self._detect_trading_gaps(df, symbol))
        issues.extend(self._validate_ohlc_consistency(df, symbol))
        
        # Calculate quality metrics
        quality_score = self._calculate_quality_score(issues, len(price_records))
        data_completeness = self._calculate_data_completeness(df, days_lookback)
        anomaly_count = len([i for i in issues if i.issue_type.startswith("ANOMALY")])
        gap_count = len([i for i in issues if i.issue_type == "TRADING_GAP"])
        
        # Generate summary
        summary = self._generate_validation_summary(df, issues)
        
        logger.info("Data validation completed", 
                   symbol=symbol, 
                   total_issues=len(issues),
                   quality_score=quality_score,
                   data_completeness=data_completeness)
        
        return ValidationReport(
            symbol=symbol,
            total_records=len(price_records),
            validation_date=datetime.now(),
            issues=issues,
            quality_score=quality_score,
            data_completeness=data_completeness,
            anomaly_count=anomaly_count,
            gap_count=gap_count,
            summary=summary
        )
    
    def _records_to_dataframe(self, records: List[DailyPrice]) -> pd.DataFrame:
        """Convert database records to DataFrame for analysis"""
        data = []
        for record in records:
            data.append({
                'date': record.date,
                'open': float(record.open),
                'high': float(record.high),
                'low': float(record.low),
                'close': float(record.close),
                'volume': record.volume,
                'adj_close': float(record.adj_close) if record.adj_close else float(record.close),
                'created_at': record.created_at
            })
        
        df = pd.DataFrame(data)
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    def _validate_price_logic(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Validate basic price logic and ranges"""
        issues = []
        
        for date, row in df.iterrows():
            # Check for non-positive prices
            if any(row[col] <= 0 for col in ['open', 'high', 'low', 'close']):
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.CRITICAL,
                    issue_type="INVALID_PRICE",
                    description="Non-positive price detected",
                    metadata={
                        'open': row['open'], 'high': row['high'], 
                        'low': row['low'], 'close': row['close']
                    }
                ))
            
            # Check price ranges
            if any(row[col] > self.max_price for col in ['open', 'high', 'low', 'close']):
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.WARNING,
                    issue_type="PRICE_RANGE",
                    description=f"Price exceeds maximum threshold ({self.max_price})",
                    current_value=max(row['open'], row['high'], row['low'], row['close']),
                    expected_value=self.max_price
                ))
            
            # Check OHLC logic: Low <= Open, Close <= High and High >= Low
            if not (row['low'] <= row['open'] <= row['high'] and 
                   row['low'] <= row['close'] <= row['high']):
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.ERROR,
                    issue_type="OHLC_LOGIC",
                    description="OHLC price logic violated",
                    metadata={
                        'open': row['open'], 'high': row['high'], 
                        'low': row['low'], 'close': row['close']
                    }
                ))
            
            # Check for high = low (no trading)
            if row['high'] == row['low'] and row['volume'] > 0:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.INFO,
                    issue_type="NO_INTRADAY_MOVEMENT",
                    description="No intraday price movement despite volume",
                    current_value=row['volume']
                ))
        
        return issues
    
    def _validate_volume_logic(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Validate volume data logic"""
        issues = []
        
        for date, row in df.iterrows():
            # Check for negative volume
            if row['volume'] < 0:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.CRITICAL,
                    issue_type="INVALID_VOLUME",
                    description="Negative volume detected",
                    current_value=row['volume']
                ))
            
            # Check for extremely high volume
            if row['volume'] > self.max_volume:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.WARNING,
                    issue_type="VOLUME_RANGE",
                    description=f"Volume exceeds maximum threshold ({self.max_volume:,})",
                    current_value=row['volume'],
                    expected_value=self.max_volume
                ))
            
            # Check for zero volume with price movement
            if row['volume'] == 0 and row['open'] != row['close']:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.WARNING,
                    issue_type="ZERO_VOLUME_MOVEMENT",
                    description="Price movement with zero volume",
                    metadata={
                        'open': row['open'], 'close': row['close'],
                        'price_change': abs(row['close'] - row['open'])
                    }
                ))
        
        return issues
    
    def _detect_price_anomalies(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Detect price anomalies using statistical methods"""
        issues = []
        
        if len(df) < 5:
            return issues  # Need minimum data for anomaly detection
        
        # Calculate daily returns
        df['daily_return'] = df['close'].pct_change()
        
        # Detect extreme daily movements
        for date, row in df.iterrows():
            if pd.isna(row['daily_return']):
                continue
                
            abs_return = abs(row['daily_return'])
            
            # Flag extreme daily changes
            if abs_return > self.max_daily_change:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.WARNING,
                    issue_type="ANOMALY_EXTREME_MOVEMENT",
                    description=f"Extreme daily price movement: {abs_return:.1%}",
                    current_value=abs_return,
                    expected_value=self.max_daily_change,
                    metadata={'price_change_pct': row['daily_return']}
                ))
        
        # Statistical outlier detection using Z-score
        if len(df) >= 20:  # Need sufficient data for statistical analysis
            returns = df['daily_return'].dropna()
            z_scores = np.abs((returns - returns.mean()) / returns.std())
            
            outlier_threshold = 3.0  # 3 standard deviations
            outliers = z_scores[z_scores > outlier_threshold]
            
            for date in outliers.index:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.INFO,
                    issue_type="ANOMALY_STATISTICAL_OUTLIER",
                    description=f"Statistical price outlier (Z-score: {z_scores[date]:.2f})",
                    current_value=z_scores[date],
                    expected_value=outlier_threshold,
                    metadata={'daily_return': df.loc[date, 'daily_return']}
                ))
        
        return issues
    
    def _detect_volume_anomalies(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Detect volume anomalies"""
        issues = []
        
        if len(df) < 10:
            return issues
        
        # Calculate volume statistics
        volume_mean = df['volume'].mean()
        volume_std = df['volume'].std()
        
        # Detect unusual volume spikes
        volume_threshold = volume_mean + (3 * volume_std)
        
        for date, row in df.iterrows():
            if row['volume'] > volume_threshold and volume_threshold > 0:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=date,
                    severity=ValidationSeverity.INFO,
                    issue_type="ANOMALY_VOLUME_SPIKE",
                    description=f"Unusual volume spike: {row['volume']:,} (avg: {volume_mean:,.0f})",
                    current_value=row['volume'],
                    expected_value=volume_threshold,
                    metadata={'volume_multiple': row['volume'] / volume_mean if volume_mean > 0 else 0}
                ))
        
        return issues
    
    def _validate_data_completeness(self, df: pd.DataFrame, symbol: str, days_lookback: int) -> List[ValidationIssue]:
        """Validate data completeness for expected trading days"""
        issues = []
        
        # Generate expected trading days (excluding weekends)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_lookback)
        
        expected_dates = []
        current_date = start_date
        while current_date <= end_date:
            # Only include weekdays (Monday=0, Sunday=6)
            if current_date.weekday() < 5:
                expected_dates.append(current_date)
            current_date += timedelta(days=1)
        
        # Find missing dates
        actual_dates = set(df.index.to_pydatetime() if hasattr(df.index, 'to_pydatetime') else 
                          [d.date() if hasattr(d, 'date') else d for d in df.index])
        expected_dates_set = set(expected_dates)
        missing_dates = expected_dates_set - actual_dates
        
        for missing_date in missing_dates:
            # Skip very recent dates (data might not be available yet)
            if missing_date >= (datetime.now().date() - timedelta(days=1)):
                continue
                
            issues.append(ValidationIssue(
                symbol=symbol,
                date=datetime.combine(missing_date, datetime.min.time()),
                severity=ValidationSeverity.WARNING,
                issue_type="MISSING_DATA",
                description=f"Missing trading day data",
                metadata={'expected_date': missing_date.isoformat()}
            ))
        
        return issues
    
    def _detect_trading_gaps(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Detect gaps in trading data"""
        issues = []
        
        if len(df) < 2:
            return issues
        
        # Check for gaps between consecutive trading days
        dates = [d.date() if hasattr(d, 'date') else d for d in df.index]
        
        for i in range(1, len(dates)):
            current_date = dates[i]
            previous_date = dates[i-1]
            
            # Calculate business days between dates
            business_days = pd.bdate_range(previous_date, current_date, freq='B')
            gap_days = len(business_days) - 1  # Subtract 1 to exclude the end date
            
            if gap_days > self.max_trading_gap_days:
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=datetime.combine(current_date, datetime.min.time()),
                    severity=ValidationSeverity.WARNING,
                    issue_type="TRADING_GAP",
                    description=f"Large gap in trading data: {gap_days} business days",
                    current_value=gap_days,
                    expected_value=self.max_trading_gap_days,
                    metadata={
                        'previous_date': previous_date.isoformat(),
                        'current_date': current_date.isoformat()
                    }
                ))
        
        return issues
    
    def _validate_ohlc_consistency(self, df: pd.DataFrame, symbol: str) -> List[ValidationIssue]:
        """Validate OHLC data consistency across time"""
        issues = []
        
        if len(df) < 2:
            return issues
        
        # Check for unrealistic overnight gaps
        for i in range(1, len(df)):
            prev_close = df.iloc[i-1]['close']
            current_open = df.iloc[i]['open']
            current_date = df.index[i]
            
            # Calculate overnight gap
            gap_percent = abs(current_open - prev_close) / prev_close
            
            if gap_percent > 0.20:  # 20% overnight gap threshold
                issues.append(ValidationIssue(
                    symbol=symbol,
                    date=current_date,
                    severity=ValidationSeverity.WARNING,
                    issue_type="OVERNIGHT_GAP",
                    description=f"Large overnight gap: {gap_percent:.1%}",
                    current_value=gap_percent,
                    expected_value=0.20,
                    metadata={
                        'prev_close': prev_close,
                        'current_open': current_open
                    }
                ))
        
        return issues
    
    def _calculate_quality_score(self, issues: List[ValidationIssue], total_records: int) -> float:
        """Calculate overall data quality score (0-100)"""
        if total_records == 0:
            return 0.0
        
        # Weighted penalty system
        penalty_weights = {
            ValidationSeverity.CRITICAL: 10.0,
            ValidationSeverity.ERROR: 5.0,
            ValidationSeverity.WARNING: 2.0,
            ValidationSeverity.INFO: 0.5
        }
        
        total_penalty = sum(penalty_weights.get(issue.severity, 1.0) for issue in issues)
        
        # Calculate score (higher is better)
        max_possible_penalty = total_records * 2  # Assume max 2 points penalty per record
        penalty_ratio = min(total_penalty / max_possible_penalty, 1.0) if max_possible_penalty > 0 else 0
        
        quality_score = (1.0 - penalty_ratio) * 100
        return max(0.0, min(100.0, quality_score))
    
    def _calculate_data_completeness(self, df: pd.DataFrame, days_lookback: int) -> float:
        """Calculate data completeness percentage"""
        # Estimate expected trading days (roughly 5/7 of total days)
        expected_trading_days = int(days_lookback * 5 / 7)
        actual_records = len(df)
        
        completeness = (actual_records / expected_trading_days) * 100 if expected_trading_days > 0 else 0
        return min(100.0, completeness)
    
    def _generate_validation_summary(self, df: pd.DataFrame, issues: List[ValidationIssue]) -> Dict[str, Any]:
        """Generate validation summary statistics"""
        if len(df) == 0:
            return {"status": "no_data"}
        
        # Group issues by severity
        issues_by_severity = {}
        for severity in ValidationSeverity:
            issues_by_severity[severity.value] = len([i for i in issues if i.severity == severity])
        
        # Group issues by type
        issues_by_type = {}
        for issue in issues:
            issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1
        
        # Basic data statistics
        latest_price = df['close'].iloc[-1]
        price_change = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100 if len(df) > 1 else 0
        avg_volume = df['volume'].mean()
        
        return {
            "status": "validated",
            "date_range": {
                "start": df.index[0].strftime('%Y-%m-%d'),
                "end": df.index[-1].strftime('%Y-%m-%d')
            },
            "price_stats": {
                "latest_price": round(latest_price, 3),
                "period_change_percent": round(price_change, 2),
                "avg_daily_volume": int(avg_volume),
                "price_range": {
                    "min": round(df['low'].min(), 3),
                    "max": round(df['high'].max(), 3)
                }
            },
            "issues_by_severity": issues_by_severity,
            "issues_by_type": issues_by_type,
            "total_issues": len(issues),
            "critical_issues": issues_by_severity.get('critical', 0),
            "data_integrity": "good" if issues_by_severity.get('critical', 0) == 0 else "poor"
        }


class BatchDataValidator:
    """Batch validation for multiple symbols"""
    
    def __init__(self):
        self.validator = DataValidator()
    
    async def validate_batch(self, db_session: AsyncSession, symbols: List[str] = None, 
                                  days_lookback: int = 30) -> Dict[str, ValidationReport]:
        """
        Validate multiple symbols in batch
        
        Args:
            db_session: Database session
            symbols: List of symbols to validate (None for all available)
            days_lookback: Days to look back for validation
            
        Returns:
            Dictionary mapping symbol to ValidationReport
        """
        if symbols is None:
            # Get all symbols with recent data
            cutoff_date = datetime.now().date() - timedelta(days=days_lookback)
            result = await db_session.execute(
                select(DailyPrice.symbol)
                .where(DailyPrice.date >= cutoff_date)
                .distinct()
            )
            symbols = [row[0] for row in result]
        
        validation_reports = {}
        
        for symbol in symbols:
            try:
                report = await self.validator.validate_symbol_data(symbol, db_session, days_lookback)
                validation_reports[symbol] = report
                
                logger.debug("Symbol validation completed", 
                           symbol=symbol, 
                           quality_score=report.quality_score,
                           issue_count=len(report.issues))
                           
            except Exception as e:
                logger.error("Symbol validation failed", symbol=symbol, error=str(e))
                validation_reports[symbol] = ValidationReport(
                    symbol=symbol,
                    total_records=0,
                    validation_date=datetime.now(),
                    issues=[ValidationIssue(
                        symbol=symbol,
                        date=None,
                        severity=ValidationSeverity.CRITICAL,
                        issue_type="VALIDATION_ERROR",
                        description=f"Validation process failed: {str(e)}"
                    )],
                    quality_score=0.0,
                    data_completeness=0.0,
                    anomaly_count=0,
                    gap_count=0,
                    summary={"status": "validation_failed", "error": str(e)}
                )
        
        logger.info("Batch validation completed", 
                   symbols_processed=len(validation_reports),
                   total_symbols_requested=len(symbols))
        
        return validation_reports
    
    def generate_batch_summary(self, reports: Dict[str, ValidationReport]) -> Dict[str, Any]:
        """Generate summary statistics for batch validation"""
        if not reports:
            return {"status": "no_reports"}
        
        total_symbols = len(reports)
        avg_quality_score = sum(r.quality_score for r in reports.values()) / total_symbols
        avg_completeness = sum(r.data_completeness for r in reports.values()) / total_symbols
        
        # Count symbols by quality tiers
        excellent_quality = len([r for r in reports.values() if r.quality_score >= 90])
        good_quality = len([r for r in reports.values() if 70 <= r.quality_score < 90])
        poor_quality = len([r for r in reports.values() if r.quality_score < 70])
        
        # Count critical issues across all symbols
        total_critical_issues = sum(
            len([i for i in r.issues if i.severity == ValidationSeverity.CRITICAL]) 
            for r in reports.values()
        )
        
        return {
            "batch_summary": {
                "total_symbols": total_symbols,
                "avg_quality_score": round(avg_quality_score, 1),
                "avg_data_completeness": round(avg_completeness, 1),
                "quality_distribution": {
                    "excellent": excellent_quality,  # 90-100
                    "good": good_quality,           # 70-89
                    "poor": poor_quality            # <70
                },
                "total_critical_issues": total_critical_issues,
                "symbols_with_critical_issues": len([
                    r for r in reports.values() 
                    if any(i.severity == ValidationSeverity.CRITICAL for i in r.issues)
                ])
            },
            "validation_timestamp": datetime.now().isoformat(),
            "status": "completed"
        }