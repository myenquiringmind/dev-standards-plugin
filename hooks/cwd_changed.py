"""Force a language-profile re-detection when CC's cwd shifts.

Fires on the CwdChanged event. The framework's stamp at
``<project>/.language_profile.json`` is normally written once per
project at SessionStart and treated as immutable for the rest of
the session. CwdChanged is the exception: it indicates the user
has navigated to a new working directory (typical in monorepo
work) and the stamp may no longer reflect the right detection
result.

This hook simply calls
``detect_language.detect_and_stamp(force=True)``. The shared helper
re-runs the detection scan against the project root and overwrites
the stamp file, including the no-match sentinel case.

Note on monorepo limitations: detection currently scans markers
at the project root, not the new cwd. A true cwd-aware detection
(``pyproject.toml`` in ``services/api/`` activates the python
profile when the user is in that subtree) is deferred — Phase 3+
when scanner agents formalise multi-stack project layouts.

Never networks. Never blocks. Always exits 0.

Event: CwdChanged
Matcher: *
"""

from __future__ import annotations

import sys

from hooks import detect_language
from hooks._hook_shared import get_project_dir, read_hook_input


def main() -> int:
    read_hook_input()  # drain stdin even if we don't read fields
    detect_language.detect_and_stamp(get_project_dir(), force=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
