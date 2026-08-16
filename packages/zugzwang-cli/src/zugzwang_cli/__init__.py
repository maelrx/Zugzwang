"""Zugzwang CLI: thin adapter over application services (ADR-009).

No domain logic lives here. Every command maps to an application service;
a future API would call the same objects (design §18.5).
"""

__version__ = "0.1.0.dev0"
