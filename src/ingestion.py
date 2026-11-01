
import hashlib
import json
from pathlib import Path


def read_event_file(file_path):
    """
    Read a JSONL file and return:
    1. Parsed events
    2. Malformed records
    3. File checksum
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    file_bytes = file_path.read_bytes()
    file_checksum = hashlib.sha256(file_bytes).hexdigest()

    events = []
    malformed_records = []

    with file_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):

            # Ignore empty lines
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                events.append({
                    "line_number": line_number,
                    "raw_record": line.strip(),
                    "event": event,
                })

            except json.JSONDecodeError as error:
                malformed_records.append({
                    "line_number": line_number,
                    "raw_record": line.strip(),
                    "reason": f"Malformed JSON: {error.msg}",
                })

    return events, malformed_records, file_checksum
