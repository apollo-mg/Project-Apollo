import os

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[36m"
CLR_GOLD = "\033[33m"
CLR_GREEN = "\033[32m"
CLR_RED = "\033[31m"
CLR_BLUE = "\033[34m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"

# The Sovereign Persona
USER_NAME = "ǟքօʟʟօ"

def stylized_print(module, message, color=CLR_CYAN, symbol="◈"):
    """Prints a consistent, industrial-style status line."""
    print(f"{color}{CLR_BOLD}{symbol} [{module.upper()}]{CLR_RESET} {CLR_DIM}{message}{CLR_RESET}")

def get_banner():
    banner = f"""
{CLR_GOLD}   ___  ___  ____  __    __    ____ 
  / _ \/ _ \/ __ \/ /   / /   / __ 
 / /_/ / /_/ / / / /   / /   / / / /
/ ___ / ____/ /_/ / /___/ /___/ /_/ / 
/_/  /_/    \____/_____/_____/\____/  {CLR_RESET}
{CLR_CYAN}{CLR_BOLD}   --- SOVEREIGN AI OPERATING SYSTEM ---{CLR_RESET}
    """
    return banner

def get_thought_block(text):
    return f"{CLR_BLUE}{CLR_DIM}💭 Thinking: {text}...{CLR_RESET}"

def get_success(text):
    return f"{CLR_GREEN}✅ {text}{CLR_RESET}"

def get_alert(text):
    return f"{CLR_RED}{CLR_BOLD}🚨 [ALERT] {text}{CLR_RESET}"

def get_audit(text):
    return f"{CLR_GOLD}⚖️ [AUDIT] {text}{CLR_RESET}"
