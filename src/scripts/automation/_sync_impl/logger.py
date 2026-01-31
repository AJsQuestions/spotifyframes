"""
Sync logging: timestamped log, verbose log, step banners, timed steps.

Buffers log lines for email notification when enabled.
"""

import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# Global log buffer for email notifications
_log_buffer = []
# Global verbose flag (set by CLI)
_verbose = False


def set_verbose(value: bool) -> None:
    """Enable or disable verbose logging."""
    global _verbose
    _verbose = value


def get_verbose() -> bool:
    """Return current verbose flag."""
    return _verbose


def get_log_buffer() -> list:
    """Return the in-memory log buffer (for email)."""
    return _log_buffer


def _is_email_enabled() -> bool:
    """Lazy check: email available and enabled."""
    try:
        import importlib.util
        parent = Path(__file__).resolve().parent.parent
        p = parent / "email_notify.py"
        if not p.exists():
            return False
        spec = importlib.util.spec_from_file_location("email_notify", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "is_email_enabled", lambda: False)()
    except Exception:
        return False


def log(msg: str) -> None:
    """Print message with timestamp and optionally buffer for email."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    if tqdm is not None:
        try:
            tqdm.write(log_line)
        except Exception:
            print(log_line)
    else:
        print(log_line)
    if _is_email_enabled():
        _log_buffer.append(log_line)


def verbose_log(msg: str) -> None:
    """Print verbose message only if verbose mode is enabled."""
    if _verbose:
        log(f"🔍 [VERBOSE] {msg}")


def log_step_banner(step_name: str, width: int = 60) -> None:
    """Log a clear demarcation banner for a sync workflow step."""
    sep = "=" * width
    log("")
    log(sep)
    log(f"  {step_name}")
    log(sep)


@contextmanager
def timed_step(step_name: str):
    """Context manager to time and log execution of a step."""
    log_step_banner(step_name)
    start_time = time.time()
    log(f"⏱️  [START] {step_name}")
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        log(f"⏱️  [END] {step_name} (took {elapsed:.2f}s)")
