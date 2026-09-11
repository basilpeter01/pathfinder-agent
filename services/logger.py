import datetime

def log_event(level: str, component: str, message: str) -> None:
    """Format and print structured log message in standard format:
    YYYY-MM-DD HH:MM:SS | LEVEL    | COMPONENT | Message
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lvl = level.upper().ljust(8)
    comp = component.upper().ljust(9)
    print(f"{ts} | {lvl} | {comp} | {message}", flush=True)
