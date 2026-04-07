import logging
import time
from collections.abc import Callable
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import ParamSpec
from typing import TypeVar

from dateutil.relativedelta import relativedelta
from rich.rule import Rule

from confluence_markdown_exporter.utils.rich_console import console

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger(__name__)


def _format_duration(delta: relativedelta) -> str:
    """Return a human-readable duration string from a relativedelta.

    Args:
        delta: The duration as a relativedelta.

    Returns:
        A formatted string like "2m 3s" or "45s".
    """
    parts = []
    if delta.hours:
        parts.append(f"{delta.hours}h")
    if delta.minutes:
        parts.append(f"{delta.minutes}m")
    seconds = delta.seconds + round(delta.microseconds / 1_000_000)
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def measure_time(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to measure and print the execution time of a function."""

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"Function '{func.__name__}' took {elapsed_time:.4f} seconds to execute.")
        return result

    return wrapper


@contextmanager
def measure(step: str) -> Generator[None, None, None]:
    """Measure and display the execution time of the encapsulated block.

    Prints a rich rule banner at start and a summary line at end.

    Args:
        step: The step name shown in the banner.

    Raises:
        e: Reraised exception from execution.
    """
    start_time = datetime.now()
    console.print(Rule(f"[highlight]{step}[/highlight]", style="dim"))
    logger.debug("Started at %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    state = "stopped"
    try:
        yield
        state = "ended"
    except Exception:
        state = "failed"
        raise
    finally:
        end_time = datetime.now()
        duration = relativedelta(end_time, start_time)
        duration_str = _format_duration(duration)
        if state == "ended":
            console.print(
                f"[success]✓[/success] [dim]{step}[/dim] "
                f"completed in [highlight]{duration_str}[/highlight]"
            )
        elif state == "failed":
            console.print(
                f"[error]✗[/error] [dim]{step}[/dim] "
                f"failed after [highlight]{duration_str}[/highlight]"
            )
        else:
            console.print(
                f"[warning]![/warning] [dim]{step}[/dim] "
                f"stopped after [highlight]{duration_str}[/highlight]"
            )
