import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, case
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
    """Check IBKR connection state with enhanced monitoring"""
    try:
        # Get all connection states (multiple clients possible)
        result = await db_session.execute(
            select(ConnectionState)
            .order_by(desc(ConnectionState.last_heartbeat))
        )
        
        connections = result.scalars().all()
        
        if connections:
            connection_details = []
            overall_status = "healthy"
            
            for conn in connections:
                if conn.last_heartbeat:
                    time_since_heartbeat = datetime.now() - conn.last_heartbeat
                    minutes_since_heartbeat = round(time_since_heartbeat.total_seconds() / 60, 1)
                else:
                    time_since_heartbeat = None
                    minutes_since_heartbeat = None
                
                conn_detail = {
                    'client_id': conn.client_id,
                    'status': conn.status,
                    'last_heartbeat': conn.last_heartbeat.isoformat() if conn.last_heartbeat else None,
                    'minutes_since_heartbeat': minutes_since_heartbeat,
                    'error_count': conn.error_count,
                    'last_error_code': conn.last_error_code,
                    'last_error_message': conn.last_error_message,
                    'connection_started_at': conn.connection_started_at.isoformat() if conn.connection_started_at else None,
                    'last_data_received_at': conn.last_data_received_at.isoformat() if conn.last_data_received_at else None
                }
                
                # Check individual connection health
                if conn.status != 'CONNECTED':
                    overall_status = "warning"
                    report['warnings'].append(f"Client {conn.client_id}: Connection status {conn.status}")
                
                if time_since_heartbeat and time_since_heartbeat.total_seconds() > 300:  # > 5 minutes
                    overall_status = "critical"
                    report['critical_issues'].append(f"Client {conn.client_id}: Heartbeat stale ({minutes_since_heartbeat} min)")
                
                if conn.error_count > 100:  # High error threshold
                    overall_status = "warning" if overall_status == "healthy" else overall_status
                    report['warnings'].append(f"Client {conn.client_id}: High error count ({conn.error_count})")
                
                # Check data staleness
                if conn.last_data_received_at:
                    time_since_data = datetime.now() - conn.last_data_received_at
                    if time_since_data.total_seconds() > 1800:  # 30 minutes
                        report['warnings'].append(f"Client {conn.client_id}: No data received for {time_since_data.total_seconds() // 60:.0f} min")
                        conn_detail['data_stale'] = True
                
                connection_details.append(conn_detail)
            
            report['checks']['connection_state'] = {
                'status': overall_status,
                'total_clients': len(connections),
                'connections': connection_details
            }
                
        else:
            report['checks']['connection_state'] = {
                'status': 'unknown',
                'message': 'No connection state records found'
            }
            report['critical_issues'].append("No IBKR connection state available - system may not be running")
            
    except Exception as e:
        report['checks']['connection_state'] = {
            'status': 'error',
            'error': str(e)
        }
        report['critical_issues'].append(f"Connection state check failed: {str(e)}")


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


@celery_app.task(bind=True, name='app.tasks.monitoring.connection_recovery_check')
def connection_recovery_check(self):
    """
    Monitor connection state and trigger recovery actions
    Runs every 2 minutes to check for connection issues
    """
    task_id = self.request.id
    logger.info("Starting connection recovery check", task_id=task_id)
    
    try:
        result = asyncio.run(_async_connection_recovery_check(task_id))
        
        if result.get('recovery_actions'):
            logger.warning("Connection recovery actions taken",
                          actions=result['recovery_actions'],
                          task_id=task_id)
        
        return result
        
    except Exception as e:
        logger.error("Connection recovery check failed", error=str(e), task_id=task_id)
        return {
            'status': 'error',
            'error': str(e)
        }


async def _async_connection_recovery_check(task_id: str) -> Dict[str, Any]:
    """Async connection recovery check"""
    recovery_report = {
        'status': 'completed',
        'timestamp': datetime.now().isoformat(),
        'task_id': task_id,
        'connections_checked': 0,
        'recovery_actions': [],
        'warnings': []
    }
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Get all connection states
            result = await db_session.execute(
                select(ConnectionState)
                .order_by(ConnectionState.client_id)
            )
            
            connections = result.scalars().all()
            recovery_report['connections_checked'] = len(connections)
            
            current_time = datetime.now()
            
            for conn in connections:
                client_actions = []
                client_id = conn.client_id
                
                # Check for stale heartbeat (connection appears hung)
                if conn.last_heartbeat:
                    time_since_heartbeat = current_time - conn.last_heartbeat
                    if time_since_heartbeat.total_seconds() > 600:  # 10 minutes
                        client_actions.append("heartbeat_stale")
                        logger.warning(f"Client {client_id}: Heartbeat stale for {time_since_heartbeat}")
                
                # Check for disconnected state lasting too long
                if conn.status in ['DISCONNECTED', 'ERROR', 'RECONNECTING']:
                    if conn.last_heartbeat:
                        time_in_bad_state = current_time - conn.last_heartbeat
                        if time_in_bad_state.total_seconds() > 300:  # 5 minutes
                            client_actions.append("extended_disconnection")
                            logger.warning(f"Client {client_id}: Disconnected for {time_in_bad_state}")
                
                # Check for excessive error count
                if conn.error_count > 200:
                    client_actions.append("excessive_errors")
                    logger.warning(f"Client {client_id}: Excessive errors ({conn.error_count})")
                
                # Check for data staleness
                if conn.last_data_received_at:
                    time_since_data = current_time - conn.last_data_received_at
                    if time_since_data.total_seconds() > 3600:  # 1 hour
                        client_actions.append("data_stale")
                        logger.warning(f"Client {client_id}: No data received for {time_since_data}")
                
                # Record recovery actions needed
                if client_actions:
                    recovery_report['recovery_actions'].append({
                        'client_id': client_id,
                        'actions_needed': client_actions,
                        'status': conn.status,
                        'error_count': conn.error_count
                    })
                    
                    # For now, just log the issues. In the future, this could trigger
                    # actual recovery actions like restarting connections
                    recovery_report['warnings'].append(
                        f"Client {client_id} needs recovery: {', '.join(client_actions)}"
                    )
            
            # If we have critical connection issues, we could trigger alerts
            critical_clients = [
                action for action in recovery_report['recovery_actions']
                if 'heartbeat_stale' in action['actions_needed'] or 
                   'extended_disconnection' in action['actions_needed']
            ]
            
            if critical_clients:
                # This could trigger an alert task
                logger.critical(f"Critical connection issues detected for {len(critical_clients)} clients")
                
        except Exception as e:
            recovery_report['status'] = 'error'
            recovery_report['error'] = str(e)
            logger.error(f"Connection recovery check error: {str(e)}")
    
    return recovery_report


@celery_app.task(bind=True, name='app.tasks.monitoring.api_error_analysis')
def api_error_analysis(self):
    """
    Analyze API error patterns and rates
    Runs every hour to identify trends and issues
    """
    task_id = self.request.id
    logger.info("Starting API error analysis", task_id=task_id)
    
    try:
        result = asyncio.run(_async_api_error_analysis(task_id))
        
        if result.get('critical_patterns'):
            logger.error("Critical API error patterns detected",
                        patterns=result['critical_patterns'],
                        task_id=task_id)
        
        return result
        
    except Exception as e:
        logger.error("API error analysis failed", error=str(e), task_id=task_id)
        return {
            'status': 'error',
            'error': str(e)
        }


async def _async_api_error_analysis(task_id: str) -> Dict[str, Any]:
    """Async API error analysis"""
    analysis_report = {
        'status': 'completed',
        'timestamp': datetime.now().isoformat(),
        'task_id': task_id,
        'analysis_period_hours': 24,
        'error_patterns': {},
        'critical_patterns': [],
        'recommendations': []
    }
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Analyze last 24 hours of API requests
            since_time = datetime.now() - timedelta(hours=24)
            
            # Get error breakdown by error code
            result = await db_session.execute(
                select(
                    ApiRequest.error_code,
                    ApiRequest.request_type,
                    func.count(ApiRequest.id).label('count'),
                    func.max(ApiRequest.timestamp).label('last_occurrence')
                )
                .where(and_(
                    ApiRequest.timestamp >= since_time,
                    ApiRequest.error_code.isnot(None)
                ))
                .group_by(ApiRequest.error_code, ApiRequest.request_type)
                .order_by(func.count(ApiRequest.id).desc())
            )
            
            error_patterns = {}
            total_errors = 0
            
            for error_code, request_type, count, last_occurrence in result:
                total_errors += count
                
                if error_code not in error_patterns:
                    error_patterns[error_code] = {
                        'total_count': 0,
                        'request_types': {},
                        'last_occurrence': None
                    }
                
                error_patterns[error_code]['total_count'] += count
                error_patterns[error_code]['request_types'][request_type] = count
                error_patterns[error_code]['last_occurrence'] = max(
                    error_patterns[error_code]['last_occurrence'] or last_occurrence,
                    last_occurrence
                ).isoformat()
            
            analysis_report['error_patterns'] = error_patterns
            analysis_report['total_errors'] = total_errors
            
            # Identify critical patterns
            for error_code, pattern in error_patterns.items():
                count = pattern['total_count']
                
                # Rate limit errors (100) - critical if frequent
                if error_code == 100 and count > 50:
                    analysis_report['critical_patterns'].append({
                        'type': 'rate_limit_violation',
                        'error_code': error_code,
                        'count': count,
                        'severity': 'high'
                    })
                    analysis_report['recommendations'].append(
                        "Consider reducing API request rate or implementing better rate limiting"
                    )
                
                # Connection errors (1100, 1300) - critical if any
                elif error_code in [1100, 1300] and count > 0:
                    analysis_report['critical_patterns'].append({
                        'type': 'connection_failure',
                        'error_code': error_code,
                        'count': count,
                        'severity': 'critical'
                    })
                    analysis_report['recommendations'].append(
                        "Investigate TWS connection stability and network issues"
                    )
                
                # Market data subscription errors (354) - warning if frequent
                elif error_code == 354 and count > 20:
                    analysis_report['critical_patterns'].append({
                        'type': 'market_data_subscription',
                        'error_code': error_code,
                        'count': count,
                        'severity': 'medium'
                    })
                    analysis_report['recommendations'].append(
                        "Verify market data subscriptions and permissions"
                    )
                
                # Any error occurring very frequently
                elif count > 100:
                    analysis_report['critical_patterns'].append({
                        'type': 'frequent_error',
                        'error_code': error_code,
                        'count': count,
                        'severity': 'medium'
                    })
            
            # Calculate error rate
            total_requests_result = await db_session.execute(
                select(func.count(ApiRequest.id))
                .where(ApiRequest.timestamp >= since_time)
            )
            total_requests = total_requests_result.scalar() or 0
            
            if total_requests > 0:
                error_rate = (total_errors / total_requests) * 100
                analysis_report['error_rate_percent'] = round(error_rate, 2)
                
                if error_rate > 15:  # 15% error rate is concerning
                    analysis_report['critical_patterns'].append({
                        'type': 'high_error_rate',
                        'error_rate': error_rate,
                        'severity': 'high'
                    })
                    analysis_report['recommendations'].append(
                        f"Overall error rate is high ({error_rate:.1f}%) - investigate system health"
                    )
            
        except Exception as e:
            analysis_report['status'] = 'error'
            analysis_report['error'] = str(e)
    
    return analysis_report