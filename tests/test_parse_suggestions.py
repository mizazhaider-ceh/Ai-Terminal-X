import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from command_suggester import parse_suggestions

GOOD_RESPONSE = """1. `grep -ri 'error' /var/log`
Explanation: Recursively searches for 'error' case-insensitively in /var/log.
2. `find /var/log -type f -name '*.log'`
Explanation: Finds all .log files under /var/log.
3. `journalctl -p err`
Explanation: Shows system journal entries with error priority or worse.
Recommended: `grep -ri 'error' /var/log`
Explanation: Recursively searches for 'error' case-insensitively in /var/log.
"""

NO_RECOMMENDED_RESPONSE = """1. `df -h`
Explanation: Shows disk usage in human-readable form.
2. `du -sh *`
Explanation: Shows the size of each item in the current directory.
"""


def test_parses_three_suggestions():
    suggestions, recommended, error = parse_suggestions(GOOD_RESPONSE)
    assert error is None
    assert len(suggestions) == 3
    assert suggestions[0]["command"] == "grep -ri 'error' /var/log"
    assert suggestions[1]["command"] == "find /var/log -type f -name '*.log'"
    assert all(s["explanation"] for s in suggestions)


def test_parses_recommended():
    _, recommended, error = parse_suggestions(GOOD_RESPONSE)
    assert error is None
    assert recommended["command"] == "grep -ri 'error' /var/log"
    assert "case-insensitively" in recommended["explanation"]


def test_falls_back_to_first_suggestion_without_recommended_line():
    suggestions, recommended, error = parse_suggestions(NO_RECOMMENDED_RESPONSE)
    assert error is None
    assert recommended["command"] == "df -h"


def test_garbage_response_returns_error():
    suggestions, recommended, error = parse_suggestions("the AI just rambled here")
    assert suggestions is None
    assert recommended is None
    assert error is not None
    assert "Could not understand" in error
