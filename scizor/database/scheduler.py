"""
Automated scheduler for stock data collection.
"""

import schedule
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import threading

from scizor.database.collector import StockDataCollector
from scizor.config.settings import get_settings


class DataScheduler:
    """Automated scheduler for stock data collection."""
    
    def __init__(self, database_url: str = None):
        self.settings = get_settings()
        self.database_url = database_url or "sqlite:///scizor_data.db"
        self.collector = StockDataCollector(self.database_url)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self._running = False
        self._thread = None
        
    def setup_schedules(self):
        """Setup automated schedules."""
        
        # Daily after market close (6 PM ET)
        schedule.every().day.at("18:00").do(self._daily_update)
        
        # Weekly full update (Sunday at 2 AM)
        schedule.every().sunday.at("02:00").do(self._weekly_update)
        
        # Intraday updates during market hours (every 15 minutes, 9:30 AM - 4 PM ET)
        for hour in range(9, 16):
            for minute in [0, 15, 30, 45]:
                if hour == 9 and minute < 30:
                    continue  # Market opens at 9:30
                schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(self._intraday_update)
        
        # Special 4 PM update (market close)
        schedule.every().day.at("16:00").do(self._market_close_update)
        
        self.logger.info("Scheduled tasks configured")
        
    def _daily_update(self):
        """Daily data update after market close."""
        self.logger.info("Starting daily update...")
        
        try:
            # Update last 2 days to catch any missed data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)
            
            self.collector.update_all_symbols(start_date, end_date)
            self.logger.info("Daily update completed successfully")
            
        except Exception as e:
            self.logger.error(f"Daily update failed: {e}")
    
    def _weekly_update(self):
        """Weekly comprehensive update."""
        self.logger.info("Starting weekly update...")
        
        try:
            # Update last 7 days comprehensively
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            self.collector.update_all_symbols(start_date, end_date, batch_size=5)
            self.logger.info("Weekly update completed successfully")
            
        except Exception as e:
            self.logger.error(f"Weekly update failed: {e}")
    
    def _intraday_update(self):
        """Intraday updates during market hours."""
        self.logger.info("Starting intraday update...")
        
        try:
            # Only update today's data
            today = datetime.now().date()
            start_date = datetime.combine(today, datetime.min.time())
            end_date = datetime.now()
            
            self.collector.update_all_symbols(start_date, end_date, batch_size=10)
            self.logger.info("Intraday update completed successfully")
            
        except Exception as e:
            self.logger.error(f"Intraday update failed: {e}")
    
    def _market_close_update(self):
        """Special update at market close."""
        self.logger.info("Starting market close update...")
        
        try:
            # Get final prices for the day
            today = datetime.now().date()
            start_date = datetime.combine(today, datetime.min.time())
            end_date = datetime.now()
            
            self.collector.update_all_symbols(start_date, end_date, batch_size=15)
            self.logger.info("Market close update completed successfully")
            
        except Exception as e:
            self.logger.error(f"Market close update failed: {e}")
    
    def add_custom_schedule(self, time_str: str, function_name: str, **kwargs):
        """
        Add a custom schedule.
        
        Args:
            time_str: Time string (e.g., "09:30", "14:15")
            function_name: Function to call ('daily_update', 'weekly_update', etc.)
            **kwargs: Additional arguments for the function
        """
        if function_name == 'daily_update':
            schedule.every().day.at(time_str).do(self._daily_update)
        elif function_name == 'weekly_update':
            schedule.every().day.at(time_str).do(self._weekly_update)
        elif function_name == 'intraday_update':
            schedule.every().day.at(time_str).do(self._intraday_update)
        
        self.logger.info(f"Added custom schedule: {function_name} at {time_str}")
    
    def start(self):
        """Start the scheduler in a separate thread."""
        if self._running:
            self.logger.warning("Scheduler is already running")
            return
            
        self.setup_schedules()
        self._running = True
        
        def run_scheduler():
            self.logger.info("Data scheduler started")
            while self._running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            self.logger.info("Data scheduler stopped")
        
        self._thread = threading.Thread(target=run_scheduler, daemon=True)
        self._thread.start()
        
        return self._thread
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        schedule.clear()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            
        self.logger.info("Scheduler stopped")
    
    def run_now(self, update_type: str = "daily"):
        """Run an update immediately."""
        self.logger.info(f"Running {update_type} update now...")
        
        if update_type == "daily":
            self._daily_update()
        elif update_type == "weekly":
            self._weekly_update()
        elif update_type == "intraday":
            self._intraday_update()
        elif update_type == "market_close":
            self._market_close_update()
        else:
            self.logger.error(f"Unknown update type: {update_type}")
    
    def get_schedule_info(self) -> Dict[str, Any]:
        """Get information about scheduled jobs."""
        jobs = []
        
        for job in schedule.jobs:
            jobs.append({
                'next_run': job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else None,
                'interval': str(job.interval),
                'unit': job.unit,
                'job_func': job.job_func.__name__ if hasattr(job.job_func, '__name__') else str(job.job_func)
            })
        
        return {
            'total_jobs': len(jobs),
            'jobs': jobs,
            'running': self._running
        }


def run_scheduler_daemon():
    """Run the scheduler as a daemon process."""
    import signal
    import sys
    
    scheduler = DataScheduler()
    
    def signal_handler(sig, frame):
        print("\nShutting down scheduler...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting data collection scheduler...")
    print("Press Ctrl+C to stop")
    
    scheduler.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()


if __name__ == "__main__":
    run_scheduler_daemon()
