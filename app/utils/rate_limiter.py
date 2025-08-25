import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import redis.asyncio as redis
import structlog
from dataclasses import dataclass
from enum import Enum

from app.config.settings import settings

logger = structlog.get_logger(__name__)


class RequestType(Enum):
    """Types of IBKR API requests with different rate limits"""
    GENERAL = "general"          # General API requests
    HISTORICAL = "historical"    # Historical data requests
    MARKET_DATA = "market_data"  # Live market data subscriptions
    IDENTICAL = "identical"      # Same request within window


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests: int
    window_seconds: int
    violation_penalty_seconds: int = None


class IBKRRateLimiter:
    """
    Token bucket rate limiter for IBKR TWS API requests
    
    Implements IBKR-specific rate limits using environment variables:
    - General: Configurable req/sec (default: 40 req/sec as safety margin)
    - Historical: Configurable req/window (default: 60 req per 10 minutes)
    - Market Data: Configurable req/minute (default: 100 req/minute)
    - Identical requests: Configurable minimum interval (default: 15 seconds)
    
    Uses Redis for distributed rate limiting across multiple workers
    """
    
    def __init__(self, redis_url: str = None, client_id: int = None):
        self.redis_url = redis_url or settings.redis_url
        self.client_id = client_id or settings.ibkr_client_id
        self.redis_client: Optional[redis.Redis] = None
        self._violation_until: Optional[datetime] = None
        self._local_cache: Dict[str, Dict] = {}  # Local cache for performance
        
        # Load rate limit configurations from settings
        self.rate_limits = {
            RequestType.GENERAL: RateLimitConfig(
                max_requests=settings.ibkr_general_rate_limit,
                window_seconds=settings.ibkr_general_window_seconds,
                violation_penalty_seconds=settings.ibkr_rate_violation_penalty_seconds
            ),
            RequestType.HISTORICAL: RateLimitConfig(
                max_requests=settings.ibkr_historical_rate_limit,
                window_seconds=settings.ibkr_historical_window_seconds,
                violation_penalty_seconds=settings.ibkr_rate_violation_penalty_seconds
            ),
            RequestType.MARKET_DATA: RateLimitConfig(
                max_requests=settings.ibkr_market_data_rate_limit,
                window_seconds=settings.ibkr_market_data_window_seconds,
                violation_penalty_seconds=settings.ibkr_rate_violation_penalty_seconds
            ),
            RequestType.IDENTICAL: RateLimitConfig(
                max_requests=1,
                window_seconds=settings.ibkr_identical_request_window_seconds,
                violation_penalty_seconds=settings.ibkr_rate_violation_penalty_seconds
            )
        }
        
        logger.info("IBKR Rate Limiter initialized", 
                   general_limit=f"{settings.ibkr_general_rate_limit}/{settings.ibkr_general_window_seconds}s",
                   historical_limit=f"{settings.ibkr_historical_rate_limit}/{settings.ibkr_historical_window_seconds}s",
                   market_data_limit=f"{settings.ibkr_market_data_rate_limit}/{settings.ibkr_market_data_window_seconds}s")
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.redis_client = redis.from_url(self.redis_url)
        await self.redis_client.ping()
        logger.info("Rate limiter connected to Redis")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.redis_client:
            await self.redis_client.close()
            
    def _get_rate_limit_key(self, request_type: RequestType, identifier: str = None) -> str:
        """Generate Redis key for rate limiting"""
        base_key = f"ibkr_rate_limit:{self.client_id}:{request_type.value}"
        if identifier:
            # For tracking identical requests
            return f"{base_key}:{identifier}"
        return base_key
    
    def _get_violation_key(self) -> str:
        """Get Redis key for tracking rate limit violations"""
        return f"ibkr_violation:{self.client_id}"
    
    async def _is_in_violation_timeout(self) -> bool:
        """Check if we're currently in a violation timeout period"""
        if self._violation_until and datetime.now() < self._violation_until:
            return True
            
        # Check Redis for violation state
        if self.redis_client:
            violation_until = await self.redis_client.get(self._get_violation_key())
            if violation_until:
                violation_time = datetime.fromisoformat(violation_until.decode())
                if datetime.now() < violation_time:
                    self._violation_until = violation_time
                    return True
                else:
                    # Violation period has expired, clean up
                    await self.redis_client.delete(self._get_violation_key())
        
        return False
    
    async def _set_violation_timeout(self, duration_seconds: int):
        """Set a violation timeout period"""
        violation_until = datetime.now() + timedelta(seconds=duration_seconds)
        self._violation_until = violation_until
        
        if self.redis_client:
            await self.redis_client.setex(
                self._get_violation_key(),
                duration_seconds,
                violation_until.isoformat()
            )
        
        logger.warning(
            "Rate limit violation - entering timeout period",
            timeout_seconds=duration_seconds,
            violation_until=violation_until
        )
    
    async def check_rate_limit(self, request_type: RequestType, identifier: str = None) -> bool:
        """
        Check if a request can be made without exceeding rate limits
        
        Args:
            request_type: Type of request (general, historical, etc.)
            identifier: Unique identifier for identical request tracking
            
        Returns:
            True if request can be made, False if rate limited
        """
        # Check if we're in violation timeout
        if await self._is_in_violation_timeout():
            return False
        
        config = self.rate_limits[request_type]
        key = self._get_rate_limit_key(request_type, identifier)
        
        if not self.redis_client:
            # Fallback to local rate limiting if Redis unavailable
            return self._check_local_rate_limit(key, config)
        
        try:
            # Use Redis sliding window counter
            now = time.time()
            window_start = now - config.window_seconds
            
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request timestamp
            pipe.zadd(key, {str(now): now})
            
            # Set key expiration
            pipe.expire(key, config.window_seconds + 1)
            
            results = await pipe.execute()
            current_count = results[1]  # Count after removing expired entries
            
            # Check if we're under the limit
            can_proceed = current_count < config.max_requests
            
            if not can_proceed:
                logger.warning(
                    "Rate limit exceeded",
                    request_type=request_type.value,
                    current_count=current_count,
                    limit=config.max_requests,
                    window_seconds=config.window_seconds
                )
                # Clean up the request we just added since it's not allowed
                await self.redis_client.zrem(key, str(now))
                
            return can_proceed
            
        except redis.RedisError as e:
            logger.error("Redis error in rate limiting, falling back to local", error=str(e))
            return self._check_local_rate_limit(key, config)
    
    def _check_local_rate_limit(self, key: str, config: RateLimitConfig) -> bool:
        """Fallback local rate limiting when Redis is unavailable"""
        now = time.time()
        window_start = now - config.window_seconds
        
        if key not in self._local_cache:
            self._local_cache[key] = {"timestamps": []}
        
        # Clean expired timestamps
        self._local_cache[key]["timestamps"] = [
            ts for ts in self._local_cache[key]["timestamps"] if ts > window_start
        ]
        
        current_count = len(self._local_cache[key]["timestamps"])
        
        if current_count < config.max_requests:
            self._local_cache[key]["timestamps"].append(now)
            return True
        
        logger.warning(
            "Local rate limit exceeded",
            current_count=current_count,
            limit=config.max_requests
        )
        return False
    
    async def wait_for_rate_limit(self, request_type: RequestType, identifier: str = None) -> float:
        """
        Wait until the rate limit allows the request
        
        Returns:
            Time waited in seconds
        """
        start_time = time.time()
        
        while not await self.check_rate_limit(request_type, identifier):
            if await self._is_in_violation_timeout():
                # Wait for violation timeout to expire
                wait_time = (self._violation_until - datetime.now()).total_seconds()
                if wait_time > 0:
                    logger.info("Waiting for violation timeout to expire", wait_seconds=wait_time)
                    await asyncio.sleep(min(wait_time, 60))  # Wait in chunks of max 60 seconds
                    continue
            
            # Calculate how long to wait based on request type
            config = self.rate_limits[request_type]
            if config.window_seconds <= 60:
                # For short windows, wait proportionally
                wait_time = config.window_seconds / config.max_requests
            else:
                # For long windows (like historical), wait 10 seconds and check again
                wait_time = 10
                
            logger.debug(
                "Rate limit hit, waiting",
                request_type=request_type.value,
                wait_seconds=wait_time
            )
            await asyncio.sleep(wait_time)
        
        total_wait = time.time() - start_time
        if total_wait > 1:  # Only log if we waited more than 1 second
            logger.info(
                "Rate limit wait completed",
                request_type=request_type.value,
                total_wait_seconds=total_wait
            )
        
        return total_wait
    
    async def handle_rate_limit_violation(self, error_code: int):
        """
        Handle IBKR rate limit violation (error code 100)
        Implements exponential backoff with jitter
        """
        if error_code == 100:
            # Calculate timeout duration based on violation history
            violation_key = f"{self._get_violation_key()}:count"
            
            try:
                if self.redis_client:
                    violation_count = await self.redis_client.incr(violation_key)
                    await self.redis_client.expire(violation_key, 3600)  # Reset count after 1 hour
                else:
                    violation_count = 1
                
                # Use configured violation penalty as base, with exponential backoff
                base_timeout = settings.ibkr_rate_violation_penalty_seconds
                timeout_seconds = min(base_timeout * (2 ** (violation_count - 1)), 600)
                
                # Add jitter (±25%)
                import random
                jitter = random.uniform(-0.25, 0.25) * timeout_seconds
                timeout_seconds = int(timeout_seconds + jitter)
                
                await self._set_violation_timeout(timeout_seconds)
                
                logger.error(
                    "IBKR rate limit violation detected",
                    error_code=error_code,
                    violation_count=violation_count,
                    timeout_seconds=timeout_seconds
                )
                
            except Exception as e:
                logger.error("Error handling rate limit violation", error=str(e))
                # Fallback to configured base timeout
                await self._set_violation_timeout(settings.ibkr_rate_violation_penalty_seconds)
    
    async def record_request(self, request_type: RequestType, 
                           symbol: str = None, 
                           success: bool = True,
                           error_code: int = None,
                           response_time_ms: int = None):
        """
        Record request statistics for monitoring
        
        Args:
            request_type: Type of request made
            symbol: Stock symbol (if applicable)
            success: Whether request was successful
            error_code: IBKR error code (if any)
            response_time_ms: Response time in milliseconds
        """
        try:
            # Store in database for monitoring
            from app.data.models.market import ApiRequest
            from app.config.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db_session:
                api_request = ApiRequest(
                    request_type=request_type.value.upper(),
                    symbol=symbol,
                    timestamp=datetime.now(),
                    status='SUCCESS' if success else 'FAILED',
                    error_code=error_code,
                    response_time_ms=response_time_ms,
                    client_id=self.client_id
                )
                
                db_session.add(api_request)
                await db_session.commit()
                
        except Exception as e:
            logger.error("Failed to record request statistics", error=str(e))
    
    async def get_current_usage(self, request_type: RequestType) -> Dict:
        """Get current usage statistics for a request type"""
        config = self.rate_limits[request_type]
        key = self._get_rate_limit_key(request_type)
        
        if not self.redis_client:
            return {"error": "Redis not available"}
        
        try:
            now = time.time()
            window_start = now - config.window_seconds
            
            # Get current count in window
            count = await self.redis_client.zcount(key, window_start, now)
            
            return {
                "request_type": request_type.value,
                "current_requests": count,
                "max_requests": config.max_requests,
                "window_seconds": config.window_seconds,
                "usage_percentage": (count / config.max_requests) * 100,
                "is_in_violation": await self._is_in_violation_timeout()
            }
            
        except redis.RedisError as e:
            logger.error("Error getting usage statistics", error=str(e))
            return {"error": str(e)}


class IBKRRequestContext:
    """
    Context manager for making rate-limited IBKR requests
    Automatically handles rate limiting and records statistics
    """
    
    def __init__(self, rate_limiter: IBKRRateLimiter, 
                 request_type: RequestType,
                 symbol: str = None,
                 identifier: str = None):
        self.rate_limiter = rate_limiter
        self.request_type = request_type
        self.symbol = symbol
        self.identifier = identifier
        self.start_time = None
        
    async def __aenter__(self):
        """Wait for rate limit before proceeding"""
        self.start_time = time.time()
        await self.rate_limiter.wait_for_rate_limit(self.request_type, self.identifier)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record request completion"""
        if self.start_time:
            response_time = int((time.time() - self.start_time) * 1000)
            
            # Determine if request was successful
            success = exc_type is None
            error_code = None
            
            # Extract IBKR error code if available
            if exc_val and hasattr(exc_val, 'error_code'):
                error_code = exc_val.error_code
                
                # Handle rate limit violations
                if error_code == 100:
                    await self.rate_limiter.handle_rate_limit_violation(error_code)
            
            # Record the request
            await self.rate_limiter.record_request(
                request_type=self.request_type,
                symbol=self.symbol,
                success=success,
                error_code=error_code,
                response_time_ms=response_time
            )


# Convenience function for creating request contexts
def rate_limited_request(rate_limiter: IBKRRateLimiter, 
                        request_type: RequestType,
                        symbol: str = None,
                        identifier: str = None):
    """Create a rate-limited request context"""
    return IBKRRequestContext(rate_limiter, request_type, symbol, identifier)