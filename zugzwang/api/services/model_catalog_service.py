from __future__ import annotations

from zugzwang.api.types import ModelOption, ModelProviderPreset


class ModelCatalogService:
    """Static provider/model catalog used by the Run Lab model selector."""

    def list_provider_presets(self) -> list[ModelProviderPreset]:
        return [
            ModelProviderPreset(
                provider="zai",
                provider_label="z.ai (GLM)",
                api_style="openai_chat_completions",
                base_url="https://api.z.ai/api/coding/paas/v4",
                api_key_env="ZAI_API_KEY",
                notes="Best for your current setup; supports GLM-5 on coding plan endpoint.",
                models=[
                    ModelOption(id="glm-5", label="GLM-5", recommended=True),
                    ModelOption(id="glm-5-code", label="GLM-5-Code"),
                    ModelOption(id="glm-4.7", label="GLM-4.7"),
                ],
            ),
            ModelProviderPreset(
                provider="openai",
                provider_label="OpenAI (GPT)",
                api_style="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                notes="Chat Completions-compatible endpoint.",
                models=[
                    ModelOption(id="gpt-5", label="GPT-5", recommended=True),
                    ModelOption(id="gpt-5-mini", label="GPT-5 Mini"),
                    ModelOption(id="gpt-4.1", label="GPT-4.1"),
                ],
            ),
            ModelProviderPreset(
                provider="anthropic",
                provider_label="Anthropic (Claude)",
                api_style="anthropic_messages",
                base_url="https://api.anthropic.com/v1",
                api_key_env="ANTHROPIC_API_KEY",
                notes="Messages API-compatible route.",
                models=[
                    ModelOption(id="claude-opus-4-1-20250805", label="Claude Opus 4.1", recommended=True),
                    ModelOption(id="claude-sonnet-4-5-20250929", label="Claude Sonnet 4.5"),
                ],
            ),
            ModelProviderPreset(
                provider="google",
                provider_label="Google (Gemini)",
                api_style="openai_chat_completions",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key_env="GEMINI_API_KEY",
                notes="Google Gemini OpenAI-compatible endpoint.",
                models=[
                    ModelOption(id="gemini-2.5-pro", label="Gemini 2.5 Pro", recommended=True),
                    ModelOption(id="gemini-2.5-flash", label="Gemini 2.5 Flash"),
                ],
            ),
            ModelProviderPreset(
                provider="grok",
                provider_label="xAI (Grok)",
                api_style="openai_chat_completions",
                base_url="https://api.x.ai/v1",
                api_key_env="XAI_API_KEY",
                notes="OpenAI SDK-compatible endpoint.",
                models=[
                    ModelOption(id="grok-4", label="Grok 4", recommended=True),
                    ModelOption(id="grok-code-fast-1", label="Grok Code Fast 1"),
                ],
            ),
            ModelProviderPreset(
                provider="deepseek",
                provider_label="DeepSeek",
                api_style="openai_chat_completions",
                base_url="https://api.deepseek.com",
                api_key_env="DEEPSEEK_API_KEY",
                notes="OpenAI-compatible endpoint; /v1 is optional.",
                models=[
                    ModelOption(id="deepseek-chat", label="DeepSeek Chat", recommended=True),
                    ModelOption(id="deepseek-reasoner", label="DeepSeek Reasoner"),
                ],
            ),
            ModelProviderPreset(
                provider="kimi",
                provider_label="Moonshot (Kimi)",
                api_style="openai_chat_completions",
                base_url="https://api.moonshot.cn/v1",
                api_key_env="MOONSHOT_API_KEY",
                notes="OpenAI-compatible endpoint for Kimi models.",
                models=[
                    ModelOption(id="kimi-k2-0905-preview", label="Kimi K2 Preview", recommended=True),
                    ModelOption(id="kimi-k2-turbo-preview", label="Kimi K2 Turbo Preview"),
                    ModelOption(id="kimi-thinking-preview", label="Kimi Thinking Preview"),
                    ModelOption(id="moonshot-v1-8k", label="Moonshot V1 8K"),
                ],
            ),
            ModelProviderPreset(
                provider="kimicode",
                provider_label="Kimi Code (Membership)",
                api_style="anthropic_messages",
                base_url="https://api.kimi.com/coding/v1",
                api_key_env="KIMI_CODE_API_KEY",
                notes="Kimi Code membership endpoint (Anthropic Messages-compatible).",
                models=[
                    ModelOption(id="kimi-for-coding", label="Kimi For Coding", recommended=True),
                ],
            ),
            ModelProviderPreset(
                provider="minimax",
                provider_label="MiniMax",
                api_style="anthropic_messages",
                base_url="https://api.minimaxi.com/anthropic",
                api_key_env="MINIMAX_API_KEY",
                notes="Anthropic Messages-compatible endpoint.",
                models=[
                    ModelOption(id="MiniMax-M2.5", label="MiniMax M2.5", recommended=True),
                    ModelOption(id="MiniMax-M2.1", label="MiniMax M2.1"),
                ],
            ),
        ]
