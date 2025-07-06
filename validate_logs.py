# File: validate_logs.py
# (Place this in your root project directory)

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_query_logs(log_path: str = "logs/query_logs.json"):
    """Validate query logs before training"""
    try:
        log_file = Path(log_path)
        if not log_file.exists():
            logger.error(f"Log file not found: {log_path}")
            return False
            
        valid_entries = 0
        total_entries = 0
        
        with open(log_file, 'r') as f:
            for line in f:
                total_entries += 1
                try:
                    log = json.loads(line)
                    if isinstance(log, dict) and 'nlp_query' in log and 'mongodb_query' in log:
                        if log['nlp_query'] and log['mongodb_query']:
                            valid_entries += 1
                except json.JSONDecodeError:
                    continue
                    
        logger.info(f"Found {valid_entries} valid entries out of {total_entries} total entries")
        return valid_entries > 0
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False

if __name__ == "__main__":
    is_valid = validate_query_logs()
    if is_valid:
        logger.info("Query logs are valid for training")
    else:
        logger.error("Query logs need attention before training")