import sqlite3
from lxml import etree
import os
import logging
import sys

# --- Configuration ---
# Update these paths to match your actual extracted Stack Overflow dump
# Recommended: /media/mark/TG 2TB/shop_vault/stackoverflow/Posts.xml
XML_FILE_PATH = "/media/mark/TG 2TB/shop_vault/stackoverflow/Posts.xml"
DB_FILE_PATH = "/media/mark/TG 2TB/shop_vault/shop_knowledge.db"

# Quality Filters ("Zero-Hallucination Mandate")
MIN_SCORE_THRESHOLD = 5  # Only keep high-quality, peer-reviewed content
BATCH_SIZE = 5000        # Commit to DB every N records to balance RAM vs Disk I/O

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("so_ingestion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Librarian")

def init_db(db_path):
    """Initializes the SQLite database schema."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Enable WAL mode for better concurrency/performance
    c.execute('PRAGMA journal_mode=WAL;')
    
    logger.info("Creating database schema...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            title TEXT,
            body TEXT,
            tags TEXT,
            accepted_answer_id INTEGER,
            view_count INTEGER,
            score INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            body TEXT,
            score INTEGER,
            is_accepted BOOLEAN
        )
    ''')
    
    # Create indices for fast joining later (CRITICAL for RAG pipeline)
    c.execute('CREATE INDEX IF NOT EXISTS idx_answers_parent ON answers(parent_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_questions_accepted ON questions(accepted_answer_id)')
    
    conn.commit()
    conn.close()

def process_posts(xml_path, db_path):
    """Streams the XML file and filters high-quality posts into SQLite."""
    if not os.path.exists(xml_path):
        logger.error(f"XML file not found at: {xml_path}")
        logger.info("Please update XML_FILE_PATH in the script.")
        return

    init_db(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    logger.info(f"Starting ingestion of {xml_path}...")
    
    # Stream parsing context (SAX-like, low memory usage)
    context = etree.iterparse(xml_path, events=('end',), tag='row')
    
    batch_q = []
    batch_a = []
    total_processed = 0
    kept_count = 0

    try:
        for event, elem in context:
            total_processed += 1
            
            try:
                post_type = elem.get('PostTypeId')
                score = int(elem.get('Score', 0))
                
                # --- FILTER LAYER ---
                # Drop low-quality content immediately
                if score < MIN_SCORE_THRESHOLD:
                    elem.clear()
                    continue

                # --- EXTRACT QUESTIONS ---
                if post_type == '1':
                    batch_q.append((
                        int(elem.get('Id')),
                        elem.get('Title'),
                        elem.get('Body'),
                        elem.get('Tags'),
                        elem.get('AcceptedAnswerId'), # Can be None
                        int(elem.get('ViewCount', 0)),
                        score
                    ))
                    kept_count += 1

                # --- EXTRACT ANSWERS ---
                elif post_type == '2':
                    batch_a.append((
                        int(elem.get('Id')),
                        int(elem.get('ParentId')),
                        elem.get('Body'),
                        score,
                        False # 'IsAccepted' logic is derived from Questions table later
                    ))
                    kept_count += 1

                # --- BATCH COMMIT ---
                if len(batch_q) >= BATCH_SIZE:
                    c.executemany('INSERT OR IGNORE INTO questions VALUES (?,?,?,?,?,?,?)', batch_q)
                    batch_q = []
                    conn.commit()
                
                if len(batch_a) >= BATCH_SIZE:
                    c.executemany('INSERT OR IGNORE INTO answers VALUES (?,?,?,?,?)', batch_a)
                    batch_a = []
                    conn.commit()

                # Progress Update
                if total_processed % 100000 == 0:
                    logger.info(f"Scanned: {total_processed:,} | Kept: {kept_count:,} (High Quality)")

            except Exception as e:
                logger.error(f"Error parsing row: {e}")

            # --- CRITICAL MEMORY MANAGEMENT ---
            # Clear element and previous siblings to keep RAM usage minimal
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

    except Exception as e:
        logger.critical(f"Parser crashed: {e}")
    finally:
        # Commit remaining
        if batch_q: c.executemany('INSERT OR IGNORE INTO questions VALUES (?,?,?,?,?,?,?)', batch_q)
        if batch_a: c.executemany('INSERT OR IGNORE INTO answers VALUES (?,?,?,?,?)', batch_a)
        conn.commit()
        conn.close()
        del context
        logger.info(f"Ingestion Complete. Total Scanned: {total_processed:,} | Total Indexed: {kept_count:,}")

if __name__ == "__main__":
    process_posts(XML_FILE_PATH, DB_FILE_PATH)
