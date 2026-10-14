"""
Shared test setup.

Content suggestions are off by default on a real server; the suites that
exercise the engine through POST /recommend need them on, and adding content
needs the operator key. Set before any test module imports the app.
"""
import os

os.environ.setdefault("RECOMMENDATIONS_ENABLED", "true")

# Adding content and saving engine state are operator-only.
os.environ.setdefault("OPERATOR_KEY", "test-operator-key")
OPERATOR_HEADERS = {"X-Operator-Key": os.environ["OPERATOR_KEY"]}
