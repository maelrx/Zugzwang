---
name: implement-knowledge-packet
description: Author or implement static expert KnowledgePacket support, including provenance, controls, token matching, leakage checks, and K-class assignment before dynamic RAG exists.
---

# Implement KnowledgePacket

## Purpose

KnowledgePacket is a versioned static artifact used to test causal knowledge injection without introducing retrieval infrastructure.

## Workflow

1. Identify the knowledge type: generic principle, phase, opening structure, motif, example or current-position analysis.
2. Record source, author/license, extraction method and semantic scope.
3. Prohibit current best move, PV or transposition-near lookup unless the condition is explicitly K7.
4. Produce correct, wrong/plausible, irrelevant token-matched and persona controls where the experiment requires them.
5. Normalize token budget and presentation format.
6. Compute content hash and assign K class.
7. Validate against `knowledge-packet.schema.json`.
8. Add leakage audit and expected applicability criteria.
9. Test manifest resolution and event provenance.
10. Update experiment card, not just prompt text.

## Evidence

A performance difference between baseline and any extra text is insufficient. Prefer contrasts such as:

```text
correct skill > wrong plausible skill ≈ irrelevant token-matched control
```

Report susceptibility when wrong or adversarial knowledge changes behavior.
