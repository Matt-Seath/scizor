import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from celery import current_task

from app.tasks.celery_app import celery_app
from app.data.models.market import DailyPrice, ApiRequest, ConnectionState
from app.data.models.portfolio import Position, Order, RiskMetric
from app.config.database import AsyncSessionLocal
from app.config.settings import settings

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name='app.tasks.monitoring.check_system_health')
def check_system_health(self):
    """
    Monitor overall system health
    Runs every 5 minutes to check critical metrics
    """
    task_id = self.request.id
    logger.info("Starting system health check", task_id=task_id)
    
    try:
        result = asyncio.run(_async_check_system_health(task_id))
        
        # Log critical issues
        if result['critical_issues']:
            logger.error("Critical system issues detected", 
                        issues=result['critical_issues'], 
                        task_id=task_id)
        
        return result
        
    except Exception as e:
        logger.error("System health check failed", error=str(e), task_id=task_id)
        return {
            'status': 'error',
            'error': str(e)
        }


async def _async_check_system_health(task_id: str) -> Dict[str, Any]:
    """Async system health check"""
    health_report = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'task_id': task_id,
        'checks': {},
        'warnings': [],
        'critical_issues': []
    }
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Check 1: Database connectivity
            await _check_database_health(db_session, health_report)
            
            # Check 2: Recent data availability
            await _check_data_freshness(db_session, health_report)
            
            # Check 3: API request patterns
            await _check_api_health(db_session, health_report)
            
            # Check 4: Connection state
            await _check_connection_state(db_session, health_report)
            
            # Check 5: Portfolio positions (if any)
            await _check_portfolio_health(db_session, health_report)
            
            # Determine overall health status
            if health_report['critical_issues']:
                health_report['status'] = 'critical'
            elif health_report['warnings']:
                health_report['status'] = 'warning'
            
        except Exception as e:
            health_report['status'] = 'error'
            health_report['critical_issues'].append(f"Health check error: {str(e)}")
    
    return health_report


async def _check_database_health(db_session: AsyncSession, report: Dict[str, Any]):
    """Check database connectivity and performance"""
    try:
        start_time = datetime.now()
        
        # Simple query to test connectivity
        result = await db_session.execute(select(func.current_timestamp()))
        db_time = result.scalar()
        
        query_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        report['checks']['database'] = {
            'status': 'healthy',
            'query_time_ms': round(query_time_ms, 2),
            'server_time': db_time.isoformat()
        }
        
        if query_time_ms > 1000:  # > 1 second
            report['warnings'].append(f"Slow database response: {query_time_ms:.0f}ms")
        
    except Exception as e:
        report['checks']['database'] = {
            'status': 'error',
            'error': str(e)
        }
        report['critical_issues'].append(f"Database connectivity issue: {str(e)}")


async def _check_data_freshness(db_session: AsyncSession, report: Dict[str, Any]):
    """Check if market data is up to date"""
    try:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Check today's data count
        result = await db_session.execute(
            select(func.count(DailyPrice.id))
            .where(DailyPrice.date == today)
        )
        today_count = result.scalar()
        
        # Check yesterday's data for comparison
        result = await db_session.execute(
            select(func.count(DailyPrice.id))
            .where(DailyPrice.date == yesterday)
        )
        yesterday_count = result.scalar()
        
        # Get latest data timestamp
        result = await db_session.execute(
            select(func.max(DailyPrice.created_at))
            .where(DailyPrice.date >= yesterday)
        )
        latest_data = result.scalar()
        
        report['checks']['data_freshness'] = {
            'status': 'healthy',
            'today_records': today_count,
            'yesterday_records': yesterday_count,
            'latest_data': latest_data.isoformat() if latest_data else None
        }
        
        # Check for data issues
        if today_count == 0 and datetime.now().hour > 17:  # After 5 PM
            report['warnings'].append("No data collected for today after market close")
        
        if today_count > 0 and today_count < 50:  # Very low data count
            report['warnings'].append(f"Low data count for today: {today_count}")
        
        if latest_data and (datetime.now() - latest_data).days > 1:
            report['critical_issues'].append("Data is more than 1 day old")
            
    except Exception as e:
        report['checks']['data_freshness'] = {
            'status': 'error',
            'error': str(e)
        }
        report['warnings'].append(f"Data freshness check failed: {str(e)}")


async def _check_api_health(db_session: AsyncSession, report: Dict[str, Any]):
    """Check API request patterns and errors"""
    try:
        # Check recent API requests (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        
        result = await db_session.execute(
            select(
                ApiRequest.status,
                func.count(ApiRequest.id).label('count')
            )
            .where(ApiRequest.timestamp >= yesterday)
            .group_by(ApiRequest.status)
        )
        
        status_counts = {row.status: row.count for row in result}
        
        total_requests = sum(status_counts.values())
        success_rate = status_counts.get('SUCCESS', 0) / total_requests * 100 if total_requests > 0 else 0
        
        report['checks']['api_health'] = {
            'status': 'healthy',
            'total_requests_24h': total_requests,
            'success_rate_percent': round(success_rate, 1),
            'status_breakdown': status_counts
        }
        
        if success_rate < 90:
            report['warnings'].append(f"Low API success rate: {success_rate:.1f}%")
        
        if success_rate < 50:
            report['critical_issues'].append(f"Critical API failure rate: {success_rate:.1f}%")
            
    except Exception as e:
        report['checks']['api_health'] = {
            'status': 'error',
            'error': str(e)
        }
        report['warnings'].append(f"API health check failed: {str(e)}")


async def _check_connection_state(db_session: AsyncSession, report: Dict[str, Any]):
    """Check IBKR connection state"""
    try:
        # Get latest connection state
        result = await db_session.execute(
            select(ConnectionState)
            .order_by(desc(ConnectionState.last_heartbeat))
            .limit(1)
        )
        
        latest_connection = result.scalar_one_or_none()
        
        if latest_connection:
            time_since_heartbeat = datetime.now() - latest_connection.last_heartbeat
            
            report['checks']['connection_state'] = {
                'status': latest_connection.status,
                'client_id': latest_connection.client_id,
                'last_heartbeat': latest_connection.last_heartbeat.isoformat(),
                'minutes_since_heartbeat': round(time_since_heartbeat.total_seconds() / 60, 1),
                'error_count': latest_connection.error_count
            }
            
            if latest_connection.status != 'CONNECTED':
                report['warnings'].append(f"IBKR connection status: {latest_connection.status}")
            
            if time_since_heartbeat.total_seconds() > 300:  # > 5 minutes
                report['critical_issues'].append("IBKR connection heartbeat is stale")
                
        else:
            report['checks']['connection_state'] = {
                'status': 'unknown',
                'message': 'No connection state records found'
            }
            report['warnings'].append("No IBKR connection state available")
            
    except Exception as e:
        report['checks']['connection_state'] = {
            'status': 'error',
            'error': str(e)
        }
        report['warnings'].append(f"Connection state check failed: {str(e)}")


async def _check_portfolio_health(db_session: AsyncSession, report: Dict[str, Any]):
    """Check portfolio positions and orders"""
    try:
        # Count open positions
        result = await db_session.execute(
            select(func.count(Position.id))
            .where(Position.status == 'OPEN')
        )
        open_positions = result.scalar()
        
        # Count pending orders
        result = await db_session.execute(
            select(func.count(Order.id))
            .where(Order.status == 'PENDING')
        )
        pending_orders = result.scalar()
        
        # Get latest risk metrics
        result = await db_session.execute(
            select(RiskMetric)
            .order_by(desc(RiskMetric.date))
            .limit(1)
        )
        latest_risk = result.scalar_one_or_none()
        
        report['checks']['portfolio'] = {
            'status': 'healthy',
            'open_positions': open_positions,
            'pending_orders': pending_orders,
            'latest_risk_date': latest_risk.date.isoformat() if latest_risk else None
        }
        
        # Check for issues
        if open_positions > settings.max_positions:
            report['critical_issues'].append(
                f"Too many open positions: {open_positions} (max: {settings.max_positions})"
            )
        
        if pending_orders > 10:  # Arbitrary threshold
            report['warnings'].append(f"High number of pending orders: {pending_orders}")
            
    except Exception as e:
        report['checks']['portfolio'] = {
            'status': 'error',
            'error': str(e)
        }
        report['warnings'].append(f"Portfolio health check failed: {str(e)}")


@celery_app.task(bind=True, name='app.tasks.monitoring.generate_weekly_report')
def generate_weekly_report(self):
    """
    Generate weekly performance and system report
    Runs every Friday at 6 PM
    """
    task_id = self.request.id
    logger.info("Generating weekly report", task_id=task_id)
    
    try:
        result = asyncio.run(_async_generate_weekly_report(task_id))
        
        logger.info("Weekly report generated", 
                   data_points=result.get('total_data_points', 0),
                   api_requests=result.get('total_api_requests', 0),
                   task_id=task_id)
        
        return result
        
    except Exception as e:
        logger.error("Weekly report generation failed", error=str(e), task_id=task_id)
        return {
            'status': 'error',
            'error': str(e)
        }


async def _async_generate_weekly_report(task_id: str) -> Dict[str, Any]:
    """Generate async weekly report"""
    week_ago = datetime.now() - timedelta(days=7)
    
    report = {
        'status': 'completed',
        'period_start': week_ago.isoformat(),
        'period_end': datetime.now().isoformat(),
        'task_id': task_id,
        'metrics': {}
    }
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Data collection metrics
            result = await db_session.execute(
                select(func.count(DailyPrice.id))
                .where(DailyPrice.created_at >= week_ago)
            )
            data_points = result.scalar()
            
            # API request metrics
            result = await db_session.execute(
                select(
                    ApiRequest.status,
                    func.count(ApiRequest.id).label('count')
                )
                .where(ApiRequest.timestamp >= week_ago)
                .group_by(ApiRequest.status)
            )
            api_stats = {row.status: row.count for row in result}
            
            # Unique trading days
            result = await db_session.execute(
                select(func.count(func.distinct(DailyPrice.date)))
                .where(DailyPrice.created_at >= week_ago)
            )
            trading_days = result.scalar()
            
            report['metrics'] = {
                'data_collection': {
                    'total_data_points': data_points,
                    'trading_days_covered': trading_days,
                    'avg_symbols_per_day': round(data_points / max(trading_days, 1), 1)
                },
                'api_performance': {
                    'total_requests': sum(api_stats.values()),
                    'success_rate': round(
                        api_stats.get('SUCCESS', 0) / max(sum(api_stats.values()), 1) * 100, 2
                    ),
                    'status_breakdown': api_stats
                }
            }
            
            # Store the report metrics
            report['total_data_points'] = data_points
            report['total_api_requests'] = sum(api_stats.values())
            
        except Exception as e:
            report['status'] = 'error'
            report['error'] = str(e)
    
    return report


@celery_app.task(bind=True, name='app.tasks.monitoring.alert_critical_issues')
def alert_critical_issues(self, issues: List[str]):
    """
    Send alerts for critical system issues
    Called by other tasks when critical issues are detected
    """
    task_id = self.request.id
    logger.critical("Critical system issues detected", 
                   issues=issues, task_id=task_id)
    
    # TODO: Implement actual alerting mechanism (email, Slack, etc.)
    # For now, just log the critical issues
    
    return {
        'status': 'completed',
        'alerts_sent': len(issues),
        'issues': issues
    }