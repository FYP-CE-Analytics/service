from datetime import datetime


def datetime_now_sec():
    return datetime.now().replace(microsecond=0)


def parse_date(date_input):
    """
    Parse a date string or datetime object into a normalized datetime object.
    Removes timezone information and standardizes the format.

    Args:
        date_input: String date or datetime object

    Returns:
        Timezone-naive datetime object or None if parsing fails
    """
    # If it's already a datetime, just normalize it
    if isinstance(date_input, datetime):
        # Remove timezone info if present
        if date_input.tzinfo:
            return date_input.replace(tzinfo=None)
        return date_input

    # Handle string input
    if isinstance(date_input, str):
        try:
            # Try ISO format first (most common)
            dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try specific format with timezone
                dt = datetime.strptime(date_input, "%Y-%m-%d %H:%M:%S.%f%z")
            except ValueError:
                try:
                    # Try date-only format
                    dt = datetime.strptime(date_input, "%Y-%m-%d")
                except ValueError:
                    print(
                        f"Warning: Could not parse date string: {date_input}")
                    return None

        # Remove timezone information to create naive datetime
        if dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt

    # Return None for unsupported types
    return None

def is_within_interval(date, start_date, end_date):
    start_date = parse_date(start_date).date()
    end_date = parse_date(end_date).date()
    date = parse_date(date).date()
    return start_date <= date <= end_date
