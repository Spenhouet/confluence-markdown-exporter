def str_to_bool(value: str) -> bool:
    """Convert a string to boolean."""
    true_set = {"true", "1", "yes", "on"}
    false_set = {"false", "0", "no", "off"}

    val = value.strip().lower()
    if val in true_set:
        return True
    if val in false_set:
        return False
    msg = f"Invalid boolean string: '{value}'"
    raise ValueError(msg)
