from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

def config_logging():
    """Configure logging settings"""
    
    #Create Log folder
    if not os.path.exists("log"):
        os.makedirs("log")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    logging.basicConfig(
        filename=f"log/{today}_bank_watch.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8"             
    )

def log_this(level, msg):
    if level == "info":
        logger.info(f"{msg}")
    elif level == "error":
        logger.error(f"{msg}")
    elif level == "warning":
        logger.warning(f"{msg}")
    elif level == "debug":
        logger.debug(f"{msg}")
        
    print(f"{level}: {msg}")