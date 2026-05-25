#!/usr/bin/env python3
import threading
import time
import urllib.request
import urllib.error
import json
import random
import string
import sys

API_URL = "http://127.0.0.1:8000"
NUM_WRITERS = 10
NUM_READERS = 10
PAYLOAD_SIZE = 1024 * 1024  # 1MB
TEST_DURATION = 30 # seconds

# Generate 1MB of garbage once to save CPU cycles in the loop
print(f"Generating {PAYLOAD_SIZE / 1024 / 1024}MB garbage template...")
BASE_GARBAGE = ''.join(random.choices(string.ascii_letters + string.digits, k=PAYLOAD_SIZE - 50))

def get_payload(thread_id):
    # Prefix with timestamp and thread ID to ensure the payload actually changes
    return f"{time.time()}_T{thread_id}_{BASE_GARBAGE}"

def writer_thread(thread_id, stats):
    print(f"[Writer {thread_id}] Started.")
    end_time = time.time() + TEST_DURATION
    successes = 0
    errors = 0
    while time.time() < end_time:
        key = f"torture_key_{thread_id}"
        payload = get_payload(thread_id)
        try:
            data = json.dumps({"key": key, "value": payload}).encode('utf-8')
            req = urllib.request.Request(f"{API_URL}/scratchpad", data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    successes += 1
                else:
                    errors += 1
        except Exception as e:
            print(f"[Writer {thread_id}] Request Failed: {e}")
            errors += 1
    
    stats['writers'][thread_id] = {'successes': successes, 'errors': errors}
    print(f"[Writer {thread_id}] Finished. Success: {successes}, Errors: {errors}")

def reader_thread(thread_id, stats):
    print(f"[Reader {thread_id}] Started.")
    end_time = time.time() + TEST_DURATION
    successes = 0
    errors = 0
    while time.time() < end_time:
        # Read from any of the keys being continuously overwritten
        key_id = random.randint(0, NUM_WRITERS - 1)
        key = f"torture_key_{key_id}"
        try:
            req = urllib.request.Request(f"{API_URL}/scratchpad/{key}")
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status in (200, 404):
                    successes += 1
                else:
                    errors += 1
        except urllib.error.HTTPError as e:
            if e.code == 404:
                successes += 1
            else:
                errors += 1
        except Exception as e:
            print(f"[Reader {thread_id}] Request Failed: {e}")
            errors += 1
            
    stats['readers'][thread_id] = {'successes': successes, 'errors': errors}
    print(f"[Reader {thread_id}] Finished. Success: {successes}, Errors: {errors}")

if __name__ == '__main__':
    print(f"==================================================")
    print(f"THE SCIENTIST: WAL Collision Torture Test")
    print(f"Target: {API_URL}")
    print(f"Writers: {NUM_WRITERS} (1MB Payload each)")
    print(f"Readers: {NUM_READERS}")
    print(f"Duration: {TEST_DURATION}s")
    print(f"==================================================\n")
    
    # Verify API is reachable before starting
    try:
        urllib.request.urlopen(f"{API_URL}/docs", timeout=2)
    except Exception:
        print(f"CRITICAL ERROR: Cannot reach Message Bus API at {API_URL}")
        sys.exit(1)

    threads = []
    stats = {'writers': {}, 'readers': {}}
    
    # Spawn Writers
    for i in range(NUM_WRITERS):
        t = threading.Thread(target=writer_thread, args=(i, stats))
        threads.append(t)
        t.start()
        
    # Spawn Readers
    for i in range(NUM_READERS):
        t = threading.Thread(target=reader_thread, args=(i, stats))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print(f"\n==================================================")
    print(f"TORTURE TEST COMPLETE")
    print(f"==================================================")
    
    total_writer_success = sum(s['successes'] for s in stats['writers'].values())
    total_writer_errors = sum(s['errors'] for s in stats['writers'].values())
    total_reader_success = sum(s['successes'] for s in stats['readers'].values())
    total_reader_errors = sum(s['errors'] for s in stats['readers'].values())
    
    print(f"Total Write Ops: {total_writer_success} successful, {total_writer_errors} errors")
    print(f"Total Read Ops:  {total_reader_success} successful, {total_reader_errors} errors")
    print(f"Total TPS (Transactions Per Second): {(total_writer_success + total_reader_success) / TEST_DURATION:.2f}")
    
    if total_writer_errors > 0 or total_reader_errors > 0:
        print("\n❌ FAILED: Database locked or timeouts occurred under load.")
        sys.exit(1)
    else:
        print("\n✅ PASSED: WAL Mode successfully handled high-concurrency 1MB payloads with zero locks.")
        sys.exit(0)