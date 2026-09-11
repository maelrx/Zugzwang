"""Per-call identity helpers for chess strategies (ZGW-0103 R1).

Every ``infer`` call must carry a caller attempt id that the SAME ``CallRecord``
stamps, so the decision trace joins evidence by call identity — never by order
and never via an ``att-placeholder`` sentinel (dossier §13: 2.068/2.273
mismatched references came from exactly that ambiguity).
"""

from __future__ import annotations

import uuid


def new_call_attempt_id() -> str:
    """One opaque caller id per inference call (NOT a backend attempt id)."""
    return f"call-{uuid.uuid4().hex}"
