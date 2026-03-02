import os
import mailbox
import hashlib
import logging
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from modules.vdb import get_vector_store, get_text_splitter, Document

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("chronicler_ingest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Chronicler")

MAILDIR_PATH = os.path.expanduser("~/.mail/gmail/INBOX")
PROCESSED_KEYS_FILE = "vault/email_processed_keys.txt"

def load_processed_keys():
    if not os.path.exists(PROCESSED_KEYS_FILE):
        return set()
    with open(PROCESSED_KEYS_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_processed_key(key):
    os.makedirs(os.path.dirname(PROCESSED_KEYS_FILE), exist_ok=True)
    with open(PROCESSED_KEYS_FILE, 'a') as f:
        f.write(f"{key}\n")

def get_body(msg):
    """Extracts the plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                try:
                    return part.get_payload(decode=True).decode()
                except:
                    pass
            elif ctype == 'text/html' and 'attachment' not in cdispo:
                try:
                    html = part.get_payload(decode=True).decode()
                    soup = BeautifulSoup(html, "html.parser")
                    return soup.get_text(separator="\\n").strip()
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True).decode()
            if msg.get_content_type() == 'text/html':
                return BeautifulSoup(payload, "html.parser").get_text(separator="\\n").strip()
            return payload
        except:
            pass
    return ""

def ingest_emails(limit=None):
    """Parses emails from Maildir and ingests them into the Vector DB."""
    if not os.path.exists(MAILDIR_PATH):
        logger.error(f"Maildir not found at {MAILDIR_PATH}")
        return "Error: Maildir not found."

    mbox = mailbox.Maildir(MAILDIR_PATH)
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()
    
    indexed_count = 0
    skipped_count = 0
    processed_keys = load_processed_keys()

    logger.info(f"Starting ingestion from {MAILDIR_PATH}. Total messages: {len(mbox)}")

    for key, msg in mbox.items():
        if limit and (indexed_count + skipped_count) >= limit:
            break
            
        if key in processed_keys:
            skipped_count += 1
            continue

        message_id = msg.get("Message-ID", "")
        if not message_id:
            save_processed_key(key)
            processed_keys.add(key)
            skipped_count += 1
            continue
            
        msg_hash = hashlib.sha256(message_id.encode()).hexdigest()
        
        # Check if already indexed
        try:
            existing = vector_store.get(where={"msg_hash": msg_hash}, limit=1)
            if existing['ids']:
                save_processed_key(key)
                processed_keys.add(key)
                skipped_count += 1
                continue
        except Exception:
            pass # Fails if collection is empty
            
        subject = msg.get("Subject", "No Subject")
        sender = msg.get("From", "Unknown Sender")
        date_str = msg.get("Date", "")
        
        try:
            date_dt = parsedate_to_datetime(date_str)
            iso_date = date_dt.isoformat()
        except:
            iso_date = date_str

        body = get_body(msg)
        if not body:
            save_processed_key(key)
            processed_keys.add(key)
            skipped_count += 1
            continue

        full_text = f"Subject: {subject}\\nFrom: {sender}\\nDate: {date_str}\\n\\n{body}"
        
        doc = Document(page_content=full_text, metadata={
            "source": f"email:{message_id}",
            "msg_hash": msg_hash,
            "type": "email",
            "subject": subject,
            "sender": sender,
            "date": iso_date
        })
        
        chunks = text_splitter.split_documents([doc])
        if chunks:
            vector_store.add_documents(documents=chunks)
            indexed_count += 1
            if indexed_count % 50 == 0:
                logger.info(f"Indexed {indexed_count} new emails...")
                
        # Always mark key as processed once we've handled it
        save_processed_key(key)
        processed_keys.add(key)

    logger.info(f"Ingestion complete. Indexed {indexed_count} new emails. Skipped {skipped_count}.")
    return f"Indexed {indexed_count} new emails (Skipped {skipped_count} existing/empty)."

def search_emails(query, n_results=5):
    """Searches the Vector DB specifically for emails."""
    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, k=n_results, filter={"type": "email"})
    
    if not results:
        return "No relevant emails found."
        
    output = []
    for doc in results:
        subject = doc.metadata.get('subject', 'Unknown')
        sender = doc.metadata.get('sender', 'Unknown')
        date = doc.metadata.get('date', 'Unknown')
        output.append(f"--- Email: {subject} | From: {sender} | Date: {date} ---\\n{doc.page_content[:500]}...\\n")
        
    return "\\n".join(output)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        print(ingest_emails(limit))
    elif len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:])
        print(search_emails(query))
    else:
        print("Usage: python chronicler.py [ingest <limit> | search <query>]")
