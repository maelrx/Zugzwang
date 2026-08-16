---
name: implement-multimodal-observation
description: Implement typed image/state observations, deterministic chess rendering, multimodal provider lowering, redundancy or conflict conditions, and modality provenance.
---

# Implement multimodal observation

## Workflow

1. Define canonical state independently of its visual rendering.
2. Render image into immutable CAS bytes with MIME, dimensions, theme, orientation, coordinates, renderer version and source-state hash.
3. Build typed `ImageArtifactPart`; never rely on mutable remote URL by default.
4. Declare observation profile and modality authority policy.
5. Add provider capability preflight for image input.
6. Preserve canonical request and provider-lowered form.
7. For redundancy, confirm image and symbolic state hashes map to the same state.
8. For conflict experiments, generate deliberate delta and record conflict manifest; never let accidental mismatch pass.
9. Test themes, orientation and resolution as controlled variables.
10. Separate perception/state reconstruction from move quality in metrics.

## Required controls

- image only;
- symbolic only;
- consistent image + symbolic;
- one-piece conflict;
- explicit textual-authoritative vs image-authoritative instruction;
- no-image provider must fail preflight, not silently OCR/describe.
