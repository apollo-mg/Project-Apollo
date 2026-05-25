import os
import email
from email.policy import default
import json
import logging
import asyncio
from openai import AsyncOpenAI
import mailbox

# --- Configuration ---
MAIL_DIR = os.path.expanduser("~/.mail/gmail")
VLLM_API_BASE = "http://localhost:8000/v1"
# Update to match the model we are downloading
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-AWQ"  
BATCH_SIZE = 10

client = AsyncOpenAI(api_key="EMPTY", base_url=VLLM_API_BASE)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def extract_body(msg):
    """Extracts plain text body from the email."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
    return ""

def get_emails(limit=1000):
    """Parses local Maildir folders and extracts email metadata + body."""
    emails = []
    folders = ['INBOX', '[Gmail].Sent Mail']
    
    for folder in folders:
        folder_path = os.path.join(MAIL_DIR, folder)
        if not os.path.exists(folder_path):
            logging.warning(f"Maildir folder not found: {folder_path}")
            continue
            
        logging.info(f"Parsing Maildir: {folder_path}")
        mbox = mailbox.Maildir(folder_path)
        for i, msg in enumerate(mbox):
            if i >= limit: break
            
            subject = msg.get('subject', 'No Subject')
            from_ = msg.get('from', 'Unknown')
            date_ = msg.get('date', 'Unknown')
            body = extract_body(msg)
            
            if body:
                emails.append({
                    "id": msg.get('Message-ID', str(i)),
                    "from": str(from_),
                    "date": str(date_),
                    "subject": str(subject),
                    "body": body[:2000] # Truncate extremely long emails to save context window
                })
    return emails

async def process_batch(batch_idx, batch):
    """Sends a batch of emails to vLLM for JSON extraction."""
    system_prompt = """You are a highly efficient data extraction assistant. 
Your task is to analyze the provided emails and output ONLY a valid JSON array.
Each object in the array MUST contain:
- "Sender": The name or email of the sender.
- "Core Topic": A 1-sentence summary of the email's topic.
- "Action Required": A boolean (true/false) indicating if the user needs to reply or take a real-world action.

Output ONLY JSON. Do not include markdown formatting or conversational text."""

    prompt = f"Analyze the following {len(batch)} emails:\n\n"
    for i, em in enumerate(batch):
        prompt += f"--- Email {i+1} ---\nFrom: {em['from']}\nSubject: {em['subject']}\nDate: {em['date']}\nBody: {em['body']}\n\n"
        
    logging.info(f"Sending Batch {batch_idx+1} to vLLM (Batch Size: {len(batch)} emails)...")
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4096
        )
        
        content = response.choices[0].message.content
        return {"batch": batch_idx + 1, "status": "success", "raw_response": content}
        
    except Exception as e:
        logging.error(f"Failed to process batch {batch_idx+1}: {e}")
        return {"batch": batch_idx + 1, "status": "failed", "error": str(e)}

async def main():
    logging.info("Starting Email Extraction Pipeline via vLLM...")
    
    # Limit to 100 for a quick benchmark test. We can increase this to 10,000+ later.
    emails = get_emails(limit=100) 
    logging.info(f"Successfully loaded {len(emails)} emails into memory.")
    
    # Chunk into batches
    batches = [emails[i:i + BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]
    logging.info(f"Divided into {len(batches)} batches of {BATCH_SIZE} emails each.")
    
    # Process concurrently using vLLM's asynchronous backend
    tasks = [process_batch(idx, b) for idx, b in enumerate(batches)]
    results = await asyncio.gather(*tasks)
    
    # Save the raw results to disk for inspection
    output_file = "vllm_email_ingestion_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
        
    logging.info(f"Extraction complete! Results saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
