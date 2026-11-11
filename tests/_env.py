"""Shared test setup: a temporary data folder and stand-ins for FastAPI and httpx.

The tests call the endpoint functions directly, so no web server and no network are needed.
Only numpy and Pillow have to be installed.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)


def setup():
    tmp = tempfile.mkdtemp(prefix="synoargus-test-")
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(TESTS, "fakes"))
    os.environ.pop("SYNOARGUS_UNLOCK", None)
    return tmp


def day(offset, hour, minute=0):
    """A clock time on a Monday some weeks ahead, plus offset days. Schedule tests need times after the real
    "now", because a schedule entry older than the last mode change is skipped."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today + timedelta(days=14 - today.weekday())
    return monday + timedelta(days=offset, hours=hour, minutes=minute)
