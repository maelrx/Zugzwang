"""PromptProgram (design §13.3).

A prompt is a versioned artifact, not a string scattered in code: template
ID/version, system instructions, observation renderer, output schema,
strategy stage, optional examples, canonicalization policy. The runtime
stores the rendered version and its hash.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .canonical import hash_canonical
from .events import JsonValue


class PromptProgram(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    system_instructions: str = ""
    output_schema: dict[str, JsonValue] | None = None
    strategy_stage: str = ""
    examples: tuple[dict[str, str], ...] = ()
    canonicalize_whitespace: bool = True

    def render(
        self,
        observation: str,
        *,
        variables: dict[str, str] | None = None,
    ) -> str:
        """Render the full prompt text (system + observation + schema hints)."""
        sections: list[str] = []
        if self.system_instructions:
            sections.append(self.system_instructions)
        sections.append(observation)
        for example in self.examples:
            sections.append(f"Example {example.get('label', '')}:\n{example.get('text', '')}")
        if self.output_schema is not None:
            from .canonical import canonical_json_string

            sections.append(
                f"Output must be valid JSON matching this schema:\n"
                f"{canonical_json_string(self.output_schema)}"
            )
        text = "\n\n".join(sections)
        if self.canonicalize_whitespace:
            text = "\n".join(line.rstrip() for line in text.splitlines())
        return text

    def hash(self, observation: str) -> str:
        """Hash of the rendered prompt for this observation (non-secret vars included)."""
        return hash_canonical(
            {
                "template_id": self.template_id,
                "version": self.version,
                "observation": observation,
                "canonicalize_whitespace": self.canonicalize_whitespace,
            }
        )


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """The rendered prompt plus its provenance metadata (design §13.3)."""

    template_id: str
    version: str
    text: str
    sha256: str
    variables: tuple[str, ...] = ()
    token_estimate: int | None = None

    @classmethod
    def from_program(
        cls,
        program: PromptProgram,
        observation: str,
        *,
        variables: dict[str, str] | None = None,
        token_estimate: int | None = None,
    ) -> RenderedPrompt:
        from .canonical import sha256_hex

        text = program.render(observation, variables=variables)
        return cls(
            template_id=program.template_id,
            version=program.version,
            text=text,
            sha256=sha256_hex(text.encode("utf-8")),
            variables=tuple(variables or {}),
            token_estimate=token_estimate,
        )
