from __future__ import annotations

from typing import Any

import streamlit as st


PRESETS: dict[str, dict[str, str]] = {
    "Smoke (safe + fast)": {
        "experiment.target_valid_games": "1",
        "experiment.max_games": "1",
        "runtime.max_plies": "30",
    },
    "Budget guardrail": {
        "budget.max_total_usd": "1.0",
        "budget.estimated_avg_cost_per_game_usd": "0.2",
    },
    "Eval-ready sample": {
        "experiment.target_valid_games": "1",
        "experiment.max_games": "1",
        "runtime.max_plies": "60",
    },
}


def render(services: dict[str, Any]) -> None:
    st.title("Run Lab")
    st.caption("Configure baseline, apply presets/overrides, preview, and launch")

    config_service = services["config_service"]
    run_service = services["run_service"]

    templates = config_service.list_templates()
    if not templates:
        st.error("No config templates found under configs/")
        return

    option_map = {f"{item.category}/{item.name}": item.path for item in templates}
    keys = list(option_map.keys())

    if "run_lab_template" not in st.session_state:
        st.session_state["run_lab_template"] = _pick_default_template(option_map)
    if "run_lab_overrides" not in st.session_state:
        st.session_state["run_lab_overrides"] = ""

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Configuration")
        selected_key = st.selectbox("Baseline template", keys, key="run_lab_template")
        model_profile = st.text_input("Model profile path (optional)", value="")

        launch_mode = st.radio(
            "Launch mode",
            ["dry-run", "play", "run"],
            horizontal=True,
            captions=[
                "Validate and preview only",
                "Force 1 game",
                "Run as configured",
            ],
        )

        st.text_area(
            "Overrides (one dotted.path=value per line)",
            key="run_lab_overrides",
            height=180,
            help="Example: runtime.max_plies=80",
        )

        config_path = option_map[selected_key]

        col_validate, col_preview = st.columns(2)
        with col_validate:
            if st.button("Validate", use_container_width=True):
                validation = config_service.validate_config(
                    config_path=config_path,
                    model_profile=model_profile or None,
                    overrides=st.session_state["run_lab_overrides"],
                )
                st.session_state["run_lab_validation"] = validation
        with col_preview:
            if st.button("Refresh Preview", use_container_width=True):
                _refresh_preview(
                    config_service=config_service,
                    config_path=config_path,
                    model_profile=model_profile,
                    overrides=st.session_state["run_lab_overrides"],
                )

        validation = st.session_state.get("run_lab_validation")
        if validation is not None:
            if validation.ok:
                st.success(f"Config valid. hash={validation.config_hash}")
            else:
                st.error(validation.message)

        preview_error = st.session_state.pop("run_lab_preview_error", None)
        if preview_error:
            st.error(preview_error)

        preview = st.session_state.get("run_lab_preview")
        if preview is not None:
            st.subheader("Resolved Preview")
            st.json(
                {
                    "config_path": preview.config_path,
                    "config_hash": preview.config_hash,
                    "run_id": preview.run_id,
                    "scheduled_games": preview.scheduled_games,
                    "estimated_total_cost_usd": preview.estimated_total_cost_usd,
                }
            )
            with st.expander("Resolved config", expanded=False):
                st.json(preview.resolved_config)

        st.subheader("Launch")
        if st.button("Launch job", type="primary", use_container_width=True):
            _launch_run(
                run_service=run_service,
                config_path=config_path,
                model_profile=model_profile,
                overrides=st.session_state["run_lab_overrides"],
                mode=launch_mode,
            )

        launched_job = st.session_state.get("run_lab_last_job")
        if isinstance(launched_job, dict):
            st.success(f"Job launched: {launched_job['job_id']} ({launched_job['job_type']})")
            st.json(launched_job)
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Open Job Monitor", use_container_width=True):
                    _go_to("Job Monitor")
            with col_b:
                if st.button("Open Run Explorer", use_container_width=True):
                    _go_to("Run Explorer")

    with right:
        st.subheader("Quick presets")
        for preset_name, preset in PRESETS.items():
            if st.button(preset_name, use_container_width=True):
                current = st.session_state.get("run_lab_overrides", "")
                st.session_state["run_lab_overrides"] = _merge_overrides(current, preset)
                st.rerun()

        if st.button("Clear overrides", use_container_width=True):
            st.session_state["run_lab_overrides"] = ""
            st.rerun()

        st.subheader("Tips")
        st.write("- Start with mode=play to validate full pipeline fast.")
        st.write("- Use dry-run after changing many overrides.")
        st.write("- Use run only after preview looks correct.")
        st.write("- After launch, continue in Job Monitor.")


def _refresh_preview(
    *,
    config_service,
    config_path: str,
    model_profile: str,
    overrides: str,
) -> None:
    try:
        preview = config_service.resolve_config_preview(
            config_path=config_path,
            model_profile=model_profile or None,
            overrides=overrides,
        )
        st.session_state["run_lab_preview"] = preview
    except Exception as exc:
        st.session_state["run_lab_preview_error"] = str(exc)


def _merge_overrides(raw_text: str, preset: dict[str, str]) -> str:
    merged: dict[str, str] = {}
    for line in raw_text.splitlines():
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", 1)
        merged[key.strip()] = value.strip()
    for key, value in preset.items():
        merged[key] = value
    return "\n".join(f"{key}={value}" for key, value in sorted(merged.items()))


def _launch_run(
    *,
    run_service,
    config_path: str,
    model_profile: str,
    overrides: str,
    mode: str,
) -> None:
    handle = run_service.start_run(
        config_path=config_path,
        model_profile=model_profile or None,
        overrides=overrides,
        mode=mode,
    )
    st.session_state["run_lab_last_job"] = handle.to_dict()
    if handle.run_id:
        st.session_state["selected_run_id"] = handle.run_id


def _pick_default_template(option_map: dict[str, str]) -> str:
    preferred = [
        "baselines/best_known_start_zai_glm5",
        "baselines/best_known_start",
    ]
    for item in preferred:
        if item in option_map:
            return item
    return next(iter(option_map.keys()))


def _go_to(page: str) -> None:
    st.session_state["nav_page"] = page
    st.rerun()
