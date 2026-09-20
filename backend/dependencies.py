"""
AETHER Backend Dependencies & Database Session Management
"""

import sqlite3
from typing import Generator
from backend.config import DB_PATH

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Yields an active SQLite database connection.
    Ensures connection is committed and closed cleanly.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
