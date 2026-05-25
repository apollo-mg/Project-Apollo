import imaplib
import socket

def test_gmail_imap_connection():
    print("--- Testing Gmail IMAP Connectivity ---")
    host = "imap.gmail.com"
    port = 993
    
    print(f"Attempting to connect to {host}:{port}...")
    try:
        # Check if we can resolve the host
        ip = socket.gethostbyname(host)
        print(f"Resolved {host} to {ip}")
        
        # Attempt a connection with a timeout
        mail = imaplib.IMAP4_SSL(host, port)
        print("Successfully established SSL connection to Gmail IMAP.")
        
        # Check capabilities
        typ, cap = mail.capability()
        print(f"Server Capabilities: {cap[0].decode('utf-8')}")
        
        mail.logout()
        print("Connection test successful.")
        return True
    except socket.gaierror:
        print("Error: Could not resolve hostname. Check your internet connection.")
    except socket.timeout:
        print("Error: Connection timed out.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    
    return False

if __name__ == "__main__":
    test_gmail_imap_connection()
