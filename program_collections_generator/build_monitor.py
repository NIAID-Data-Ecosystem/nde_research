#!/usr/bin/env python3
"""
Build Monitor for Program Collections

This script continuously monitors the NIAID staging API for new builds
and triggers program collections updates when changes are detected.

Usage:
    python build_monitor.py [--interval 300] [--environment staging]
"""

import argparse
import logging
import signal
import sys
import time

from program_collections_automation import ProgramCollectionsGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BuildMonitor:
    """Monitors API builds and triggers updates"""

    def __init__(self, check_interval: int = 300, environment: str = 'staging'):
        self.generator = ProgramCollectionsGenerator()
        self.check_interval = check_interval  # seconds
        self.environment = environment
        self.running = True

        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def check_and_update(self) -> bool:
        """Check for new builds and update if needed"""
        try:
            logger.info(f"Checking for new {self.environment} build...")

            # Check if update is needed
            if self.generator.should_update(self.environment, force_update=False):
                logger.info("New build detected, triggering update...")

                success = self.generator.run_automation(
                    self.environment,
                    force_update=False
                )

                if success:
                    logger.info("✅ Program collections updated successfully!")
                    return True
                else:
                    logger.error("❌ Program collections update failed!")
                    return False
            else:
                logger.info("No new build detected, no update needed")
                return True

        except Exception as e:
            logger.error(f"Error during check and update: {e}")
            return False

    def run(self):
        """Main monitoring loop"""
        logger.info(f"🚀 Starting build monitor for {self.environment}")
        logger.info(f"📅 Check interval: {self.check_interval} seconds")
        logger.info(
            f"🔗 Monitoring: {self.generator.staging_metadata_api if self.environment == 'staging' else self.generator.prod_metadata_api}")

        # Perform initial check
        logger.info("Performing initial build check...")
        self.check_and_update()

        # Main monitoring loop
        while self.running:
            try:
                logger.info(
                    f"⏰ Waiting {self.check_interval} seconds until next check...")

                # Sleep in smaller chunks to respond to signals faster
                sleep_remaining = self.check_interval
                while sleep_remaining > 0 and self.running:
                    sleep_chunk = min(10, sleep_remaining)
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk

                if self.running:
                    self.check_and_update()

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitoring loop: {e}")
                time.sleep(60)  # Wait before retrying

        logger.info("🛑 Build monitor stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Monitor API builds and trigger program collections updates'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Check interval in seconds (default: 300 = 5 minutes)'
    )
    parser.add_argument(
        '--environment',
        choices=['staging', 'production', 'both'],
        default='staging',
        help='Environment to monitor (default: staging)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Validate interval
    if args.interval < 60:
        logger.warning(
            "Check interval is less than 60 seconds, this may be too frequent")

    # Create and run monitor
    try:
        monitor = BuildMonitor(args.interval, args.environment)
        monitor.run()
    except Exception as e:
        logger.error(f"Failed to start build monitor: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
