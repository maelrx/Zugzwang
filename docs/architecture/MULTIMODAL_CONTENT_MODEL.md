# Modelo de conteúdo multimodal

## Goal

Support image-based and mixed observations without coupling core to a provider SDK or Web UI.

## Content parts

```python
ContentPart = TextPart | StructuredStatePart | ImageArtifactPart | ToolResultPart
```

### TextPart

UTF-8 text, role/context metadata, content hash.

### StructuredStatePart

Canonical JSON-like state with schema ID. Providers may receive a rendered textual encoding, but the original structured source remains an artifact.

### ImageArtifactPart

References immutable bytes:

```yaml
artifact:
  sha256:
  mime_type:
  size_bytes:
image:
  width:
  height:
  renderer_id:
  renderer_version:
  source_state_hash:
  orientation:
  theme:
  piece_set:
  coordinates:
  alt_text_hash:
```

### ToolResultPart

Typed result from an authorized tool, with H/K impacts.

## Provider lowering

Each backend lowers canonical parts to provider-specific messages. The lowered request is stored separately from the canonical request when policy permits. This lets reviewers distinguish kernel intent from transport transformation.

## Image safety

- no remote URL fetch by default;
- local artifact bytes only;
- MIME sniffing and size limits;
- pixel dimension limits;
- deterministic renderers for benchmark boards;
- no EXIF or hidden metadata in generated boards;
- exact bytes hashed before inference.

## Conflict semantics

Observation source carries:

- authority: canonical, redundant, advisory, intentionally conflicting;
- source ID;
- truth target for evaluation;
- conflict group.

The model is never silently given inconsistent state.

## Capability fallback

If a model lacks image input:

- fail by default;
- optional explicit condition skip;
- never OCR/render image into text silently, because that changes the condition.
