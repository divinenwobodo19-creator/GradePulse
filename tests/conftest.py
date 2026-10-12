"""
Shared test setup.

Content suggestions are off by default on a real server; the suites that
exercise the engine through POST /recommend need them on. Set before any test
module imports the app.
"""
import os

os.environ.setdefault("RECOMMENDATIONS_ENABLED", "true")
