---
id: ADR-053
title: "Call provider reasoning fields telemetry, not hidden CoT"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 16-17"
---

# ADR-053: Reasoning telemetry

The provider-neutral artifact stores exposed reasoning items, summaries,
reasoning-token counts and availability flags. Unknown fields remain null or
empty. Token usage does not prove private reasoning.

This wording is part of the research protocol. It prevents a normalized output
or a token count from being presented as a verbatim thought process.
