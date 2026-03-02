"""macOS Reminders integration via AppleScript for VELAR.

Creates reminders in macOS Reminders.app using osascript subprocess.
Reminders sync automatically to iPhone via iCloud.

No API keys or OAuth required — AppleScript has direct system access.
The backend must run on macOS for this tool to work.

Security note:
    Double quotes in reminder text are escaped before embedding in the AppleScript
    inline string to prevent AppleScript injection (Pitfall 6 from research).
"""

import asyncio
import datetime
import logging
import subprocess

logger = logging.getLogger(__name__)


def _set_reminder_sync(text: str, minutes_from_now: int) -> str:
    """Synchronous implementation — called via asyncio.to_thread.

    Args:
        text:             Reminder message. Double quotes are escaped for AppleScript safety.
        minutes_from_now: When to trigger the reminder (must be positive).

    Returns:
        Confirmation string: "Reminder set: 'text' in N minutes."

    Raises:
        RuntimeError: If osascript returns a non-zero exit code.
        ValueError:   If minutes_from_now is not positive.
    """
    if minutes_from_now <= 0:
        raise ValueError("minutes_from_now must be a positive integer")

    # Escape double quotes to prevent AppleScript injection (Pitfall 6)
    safe_text = text.replace('"', '\\"')

    due = datetime.datetime.now() + datetime.timedelta(minutes=minutes_from_now)
    # AppleScript date format: "MM/DD/YYYY HH:MM:SS"
    due_str = due.strftime("%m/%d/%Y %H:%M:%S")

    script = (
        f'tell application "Reminders"\n'
        f'    set newReminder to make new reminder with properties '
        f'{{name:"{safe_text}", remind me date:date "{due_str}"}}\n'
        f'end tell'
    )

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        logger.error("AppleScript failed (rc=%d): %s", result.returncode, result.stderr)
        raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")

    return f"Reminder set: '{text}' in {minutes_from_now} minutes."


async def set_reminder(text: str, minutes_from_now: int) -> str:
    """Create a reminder in macOS Reminders.app.

    Args:
        text:             The reminder message.
        minutes_from_now: How many minutes from now to trigger the reminder.

    Returns:
        Confirmation string suitable for voice response.
    """
    return await asyncio.to_thread(_set_reminder_sync, text, minutes_from_now)
