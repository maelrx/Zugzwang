"""Versioned schema identifiers.

Package versions, manifest API versions, bundle schemas, event schemas, plugin
APIs and metric versions are independent version spaces (design §25.1). These
constants are the canonical spelling of the v0.1 contract family.
"""

from __future__ import annotations

from typing import Final

MANIFEST_API: Final = "zgw.dev/v1alpha1"
EVENT_API: Final = "zgw.event/v1alpha1"
BUNDLE_API: Final = "zgw.bundle/v1alpha1"
PLUGIN_API: Final = "zgw.plugin/v1alpha1"
MODEL_REQUEST_API: Final = "zgw.model-request/v1alpha1"

EVENT_ENVELOPE_VERSION: Final = 1
