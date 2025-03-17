import time
from collections.abc import Callable
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import ParamSpec
from typing import TypeVar

from dateutil.relativedelta import relativedelta

T = TypeVar("T")
P = ParamSpec("P")


def measure_time(func: Callable[P, T]) -> Callable[P, T]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Function '{func.__name__}' took {elapsed_time:.4f} seconds to execute.")
        return result

    return wrapper


def format_log_message(step: str, time: datetime, state: str) -> str:
    """Format the timestamp log message.

    Args:
        step: The step name
        time: A timestamp
        state: The execution state
    """
    return f"{step} {state} at {time.strftime('%Y-%m-%d %H:%M:%S')}"


@contextmanager
def measure(step: str) -> Generator[None, None, None]:
    """Measure and log the execution time of the encapsulated methods.

    This can be used via python environments:

    .. code-block:: python

        with measure("My Step"):
            time.sleep(2)

    The log output for the above will be something like:

    .. code-block::

        My Step started at 2020-07-09 13:49:00
        My Step ended at 2020-07-09 13:49:00
        Duration of My Step was relativedelta(seconds=+2, microseconds=+1405)

    Args:
        step: The step name.
        logger: The logger instance.

    Raises:
        e: Reraised exception from execution
    """
    start_time = datetime.now()
    print(format_log_message(step, time=start_time, state="started"))
    state = "stopped"
    try:
        yield
        state = "ended"
    except Exception:
        state = "failed"
        raise
    finally:
        end_time = datetime.now()
        print(format_log_message(step, time=end_time, state=state))
        duration = relativedelta(end_time, start_time)
        print(f"{step} took {duration}")
