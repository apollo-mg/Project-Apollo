#!/usr/bin/env python3
"""
Sovereign Mail Strategy - Zero-Abstraction Ingestion
Bypasses Cloud/OAuth complexities by reading directly from the local Maildir
synchronized via mbsync/isync. Features a 'Fast Path' domain filter and a 
'Smart Path' LLM intent router for urgent notifications.
"""

import mailbox
import os
import json
import time
import datetime
from email.header import decode_header
from bs4 import BeautifulSoup
from llm_interface import query_llm
import subprocess

# Paths
MAILDIR_PATH = os.path.expanduser("~/.mail/gmail/INBOX")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROCESSED_FILE = os.path.join(DATA_DIR, "processed_email_ids.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "email_domain_blacklist.json")
URGENT_LOG = os.path.join(os.path.dirname(__file__), "URGENT_COMMUNICATIONS.md")

os.makedirs(DATA_DIR, exist_ok=True)

def decode_header_value(header_val):
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    result = ""
    for frag, encoding in decoded_fragments:
        if isinstance(frag, bytes):
            try:
                result += frag.decode(encoding or 'utf-8', errors='replace')
            except LookupError:
                result += frag.decode('utf-8', errors='replace')
        else:
            result += str(frag)
    return result.strip()

def get_domain(email_str):
    try:
        if "<" in email_str and ">" in email_str:
            return email_str.split("<")[1].split(">")[0].split("@")[1].lower()
        elif "@" in email_str:
            return email_str.split("@")[1].lower()
    except:
        pass
    return "unknown"

def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            if 'attachment' in cdispo:
                continue
            if ctype == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                    break
                except Exception:
                    pass
            elif ctype == 'text/html':
                try:
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                    soup = BeautifulSoup(html, "html.parser")
                    body = soup.get_text(separator='\n', strip=True)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
        except Exception:
            pass
    return body

def load_json_list(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # For legacy blacklist format {"ignored_domains": [...]}
                    for k, v in data.items():
                        if isinstance(v, list): return v
        except Exception:
            pass
    return []

def save_json_list(filepath, data_list):
    with open(filepath, 'w') as f:
        json.dump(data_list, f, indent=2)

def notify_os(title, message):
    """Sends a desktop notification to KDE Plasma."""
    try:
        subprocess.run(["notify-send", "-u", "critical", title, message], check=True)
    except Exception as e:
        print(f"[!] Failed to send OS notification: {e}")

def assess_email_importance(sender, subject, body):
    system_prompt = """You are the Sovereign Mail Filter. Your job is to read an email and determine if it is IMPORTANT.
Important criteria: Personal emails, Work-related, Daughter's school/teachers, High-priority news, or sales on engineering/hobby items.
IGNORE: Spam, generic newsletters, receipts, generic social media, generic marketing.

You MUST reply with a pure JSON object, nothing else. Do NOT wrap it in markdown block quotes (```json).
Format:
{
  "important": true/false,
  "category": "Work/Family/Sales/Spam/etc",
  "summary": "A 1-sentence summary of why it matters."
}
"""
    prompt = f"From: {sender}\nSubject: {subject}\n\nBody Preview:\n{body}"
    
    # We enforce JSON structure via LLM prompt and parse it.
    response = query_llm(prompt=prompt, system_message=system_prompt, max_tokens=256)
    
    # Strip markdown if the model hallucinates it
    clean_resp = response.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(clean_resp)
    except json.JSONDecodeError:
        print(f"[!] LLM returned invalid JSON: {clean_resp}")
        return {"important": False, "category": "Error", "summary": "Failed to parse LLM response."}

def run_mail_daemon():
    print("[*] Starting Sovereign Mail Daemon...")
    blacklist = load_json_list(BLACKLIST_FILE)
    
    while True:
        processed_ids = set(load_json_list(PROCESSED_FILE))
        
        if not os.path.exists(MAILDIR_PATH):
            print(f"[!] Maildir not found at {MAILDIR_PATH}. Waiting...")
            time.sleep(60)
            continue
            
        mdir = mailbox.Maildir(MAILDIR_PATH)
        
        new_dir_path = os.path.join(MAILDIR_PATH, "new")
        new_keys = []
        if os.path.exists(new_dir_path):
            new_keys = os.listdir(new_dir_path)
            
        found_important = False
        
        for key in new_keys:
            if key in processed_ids:
                continue
                
            try:
                msg = mdir.get_message(key)
            except KeyError:
                continue
                
            sender = decode_header_value(msg.get("From"))
            subject = decode_header_value(msg.get("Subject"))
            domain = get_domain(sender)
            
            # Fast Path Filter
            if any(junk in domain for junk in blacklist) or any(junk in domain for junk in ['amazon', 'uber', 'marketing']):
                print(f"[-] Ignoring known junk domain: {domain}")
                processed_ids.add(key)
                continue
                
            print(f"[*] Analyzing new email: '{subject}' from {sender}")
            body = get_body(msg)
            # Truncate to first 30 lines to save VRAM
            body_preview = '\n'.join([line.strip() for line in body.splitlines() if line.strip()][:30]) 
            
            # Smart Path Filter
            assessment = assess_email_importance(sender, subject, body_preview)
            
            if assessment.get("important", False):
                print(f"[!] IMPORTANT: {assessment.get('summary')}")
                # Log it
                with open(URGENT_LOG, "a") as f:
                    f.write(f"\n### {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                    f.write(f"**From:** {sender}\n**Subject:** {subject}\n")
                    f.write(f"**Category:** {assessment.get('category')}\n")
                    f.write(f"**Summary:** {assessment.get('summary')}\n")
                
                # Desktop notification
                notify_os("Apollo URGENT Mail", f"{assessment.get('category')}: {assessment.get('summary')}")
                found_important = True
            else:
                print(f"[-] Ignored (LLM categorised as {assessment.get('category')})")
                
            processed_ids.add(key)
            save_json_list(PROCESSED_FILE, list(processed_ids))
            
            # Sleep briefly between LLM queries to prevent VRAM spikes
            time.sleep(2)
            
        if not new_keys:
            print("[zZz] No new mail. Sleeping for 1 hour...")
            
        # Sleep for an hour
        time.sleep(3600)

if __name__ == "__main__":
    try:
        run_mail_daemon()
    except KeyboardInterrupt:
        print("\n[!] Mail Daemon stopped by user.")
