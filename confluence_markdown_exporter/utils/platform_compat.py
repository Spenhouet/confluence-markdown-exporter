import re


def handle_powershell_tilde_expansion(cli_argument: str) -> str:
    """Restore tilde (~) character in command-line arguments expanded by PowerShell on Windows.

    Args:
        cli_argument: A command-line argument that may have been expanded by PowerShell

    Returns:
        The command-line argument with PowerShell tilde expansion reversed
    """
    return re.sub(r"^[A-Z]:\\Users\\", "~", cli_argument, count=1, flags=re.IGNORECASE)
