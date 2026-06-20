import logging
import sys

def setup_logging(log_file=None):
    logger = logging.getLogger('VietDocProof')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    if log_file:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
