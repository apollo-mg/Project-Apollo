import time
import logging
from modules.chronicler import ingest_emails

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("chronicler_background.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BackgroundIngest")

def run():
    logger.info("Starting continuous email ingestion loop...")
    batch_size = 500
    consecutive_empty_runs = 0
    
    while True:
        try:
            logger.info(f"Ingesting next {batch_size} emails...")
            # ingest_emails returns a string like "Indexed X new emails (Skipped Y existing/empty)."
            result = ingest_emails(limit=batch_size)
            logger.info(f"Batch result: {result}")
            
            # Simple heuristic to slow down if we aren't finding anything new
            if "Indexed 0 new emails" in result and "Skipped 0" in result:
                consecutive_empty_runs += 1
            elif "Indexed 0 new emails" in result:
                 # If we skipped a lot but indexed 0, we're likely caught up and just iterating over newly synced empty things
                 consecutive_empty_runs += 1
            else:
                consecutive_empty_runs = 0
                
            sleep_time = min(300, 10 + (consecutive_empty_runs * 30))
            logger.info(f"Sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Error in background ingest: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run()
