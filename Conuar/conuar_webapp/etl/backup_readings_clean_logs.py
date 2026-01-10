#!/usr/bin/env python3
"""
Backup Readings and Clean Logs Script - Sistema Conuar

This script:
1. Runs weekly to backup the PLC readings CSV file
2. Cleans log files by removing entries older than 60 days (without deleting the files)
3. If last execution was more than 7 days ago, executes immediately

Sistema de inspección de combustible Conuar
"""

import os
import sys
import shutil
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# Get the script's directory and project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Paths configuration
CSV_FILE = PROJECT_ROOT / 'etl' / 'NodeRed' / 'plc_reads' / 'plc_reads_nodered.csv'
CSV_DIR = CSV_FILE.parent
LOGS_DIR = PROJECT_ROOT / 'logs'
BACKUP_LOG_FILE = PROJECT_ROOT / 'logs' / 'backup_readings_clean_logs.log'
STATE_FILE = PROJECT_ROOT / 'logs' / '.backup_last_run'  # Hidden state file

# Time thresholds
DAYS_BETWEEN_BACKUPS = 7
LOG_RETENTION_DAYS = 60

# Configure logging for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BACKUP_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_last_execution_time() -> datetime:
    """
    Get the last execution time from the state file or log file.
    Returns datetime object, or None if never executed.
    """
    # First try to read from state file
    if STATE_FILE.exists():
        try:
            timestamp_str = STATE_FILE.read_text().strip()
            return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Could not read state file: {e}")
    
    # Fallback: try to get last execution from log file
    if BACKUP_LOG_FILE.exists():
        try:
            # Read last 50 lines to find last execution
            with open(BACKUP_LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_time = datetime.now()
            
            # Search backwards for last execution timestamp
            for line in reversed(lines[-50:]):
                # Look for execution start message
                if 'Starting backup and log cleanup process' in line:
                    # Extract timestamp from log line
                    match = re.match(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})', line)
                    if match:
                        log_time = datetime.strptime(f"{match.group(1)} {match.group(2)}", '%Y-%m-%d %H:%M:%S')
                        # Only return if this timestamp is at least 1 minute old
                        # This prevents matching the current execution's log entry
                        time_diff = (current_time - log_time).total_seconds()
                        if time_diff > 60:
                            return log_time
        except Exception as e:
            logger.warning(f"Could not read last execution from log: {e}")
    
    return None


def should_execute() -> bool:
    """
    Check if script should execute (either first time or > 7 days since last run).
    """
    last_run = get_last_execution_time()
    
    if last_run is None:
        logger.info("No previous execution found. Executing immediately.")
        return True
    
    days_since_last_run = (datetime.now() - last_run).days
    
    if days_since_last_run >= DAYS_BETWEEN_BACKUPS:
        logger.info(f"Last execution was {days_since_last_run} days ago (>= {DAYS_BETWEEN_BACKUPS} days). Executing immediately.")
        return True
    else:
        logger.info(f"Last execution was {days_since_last_run} days ago (< {DAYS_BETWEEN_BACKUPS} days). Skipping execution.")
        return False


def update_last_execution_time():
    """Update the state file with current execution time."""
    try:
        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(datetime.now().isoformat())
        logger.debug("Updated last execution time in state file.")
    except Exception as e:
        logger.warning(f"Could not update state file: {e}")


def backup_csv_file() -> bool:
    """
    Backup the PLC readings CSV file with naming convention bkp_plc_reads_nodered_YYYYMMDD.csv
    Returns True if successful, False otherwise.
    """
    if not CSV_FILE.exists():
        logger.error(f"CSV file not found: {CSV_FILE}")
        return False
    
    # Ensure backup directory exists
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Generate backup filename with current date
        date_str = datetime.now().strftime('%Y%m%d')
        backup_filename = f"bkp_plc_reads_nodered_{date_str}.csv"
        backup_path = CSV_DIR / backup_filename
        
        # Check if backup for today already exists
        if backup_path.exists():
            logger.warning(f"Backup file already exists for today: {backup_path}")
            # Optionally: add timestamp to make it unique
            timestamp = datetime.now().strftime('%H%M%S')
            backup_filename = f"bkp_plc_reads_nodered_{date_str}_{timestamp}.csv"
            backup_path = CSV_DIR / backup_filename
        
        # Perform backup
        shutil.copy2(CSV_FILE, backup_path)
        logger.info(f"Successfully backed up CSV file to: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error backing up CSV file: {e}")
        return False


def parse_log_timestamp(line: str) -> Tuple[datetime, bool]:
    """
    Parse timestamp from a log line.
    Supports multiple log formats:
    - Django verbose: 'INFO 2025-10-30 21:07:17,991 module process thread message'
    - Simple: 'INFO 2025-10-30 21:07:17 message'
    - ISO format timestamps
    
    Returns (datetime, is_valid) tuple.
    """
    # Try Django verbose format: INFO 2025-10-30 21:07:17,991 ...
    match = re.match(r'[A-Z]+\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            date_str = match.group(1)
            time_str = match.group(2)
            dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
            return dt, True
        except ValueError:
            pass
    
    # Try ISO format: 2025-10-30T21:07:17
    match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            iso_str = match.group(1).replace('T', ' ')
            dt = datetime.strptime(iso_str, '%Y-%m-%d %H:%M:%S')
            return dt, True
        except ValueError:
            pass
    
    # Try simple format: 2025-10-30 21:07:17
    match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            dt = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            return dt, True
        except ValueError:
            pass
    
    return None, False


def clean_log_file(log_file_path: Path) -> Tuple[int, int]:
    """
    Clean a log file by removing entries older than LOG_RETENTION_DAYS days.
    Does not delete the file, only removes old lines.
    
    Returns (total_lines, removed_lines) tuple.
    """
    if not log_file_path.exists():
        logger.warning(f"Log file does not exist: {log_file_path}")
        return 0, 0
    
    # Don't clean our own log file
    if log_file_path == BACKUP_LOG_FILE:
        logger.debug(f"Skipping own log file: {log_file_path}")
        return 0, 0
    
    cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    
    try:
        # Read all lines
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        kept_lines = []
        removed_count = 0
        
        # Process each line
        for line in lines:
            timestamp, is_valid = parse_log_timestamp(line)
            
            if is_valid and timestamp:
                # Keep line if timestamp is within retention period
                if timestamp >= cutoff_date:
                    kept_lines.append(line)
                else:
                    removed_count += 1
            else:
                # If we can't parse timestamp, keep the line (might be header or important info)
                kept_lines.append(line)
        
        # Write back only the kept lines
        if removed_count > 0:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.writelines(kept_lines)
            logger.info(f"Cleaned {log_file_path.name}: removed {removed_count}/{total_lines} lines older than {LOG_RETENTION_DAYS} days")
        else:
            logger.debug(f"No old lines to remove from {log_file_path.name}")
        
        return total_lines, removed_count
        
    except Exception as e:
        logger.error(f"Error cleaning log file {log_file_path}: {e}")
        return 0, 0


def clean_all_logs() -> Tuple[int, int]:
    """
    Clean all .log files in the logs directory.
    Returns (total_files_processed, total_lines_removed) tuple.
    """
    if not LOGS_DIR.exists():
        logger.warning(f"Logs directory not found: {LOGS_DIR}. Creating it.")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return 0, 0
    
    log_files = list(LOGS_DIR.glob('*.log'))
    
    if not log_files:
        logger.info("No .log files found in logs directory")
        return 0, 0
    
    total_files = len(log_files)
    total_lines_removed = 0
    
    logger.info(f"Found {total_files} log file(s) to process")
    
    for log_file in log_files:
        _, removed = clean_log_file(log_file)
        total_lines_removed += removed
    
    logger.info(f"Log cleanup complete: processed {total_files} file(s), removed {total_lines_removed} line(s)")
    return total_files, total_lines_removed


def main():
    """Main execution function."""
    # Check if we should execute BEFORE logging start message
    # This prevents detecting our own log entry as a previous execution
    if not should_execute():
        logger.info("Execution skipped. Next run should be in 7 days.")
        return
    
    # Log start message after we've confirmed we should execute
    logger.info("=" * 60)
    logger.info("Starting backup and log cleanup process")
    logger.info("=" * 60)
    
    success_count = 0
    error_count = 0
    
    # 1. Backup CSV file
    logger.info("Step 1: Backing up CSV file...")
    if backup_csv_file():
        success_count += 1
    else:
        error_count += 1
    
    # 2. Clean log files
    logger.info("Step 2: Cleaning log files...")
    try:
        files_processed, lines_removed = clean_all_logs()
        success_count += 1
        logger.info(f"Log cleanup: {files_processed} file(s) processed, {lines_removed} line(s) removed")
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")
        error_count += 1
    
    # Update last execution time
    update_last_execution_time()
    
    # Summary
    logger.info("=" * 60)
    logger.info(f"Process completed. Success: {success_count}, Errors: {error_count}")
    logger.info("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

