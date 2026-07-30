"""Streamlit UI shell for local runs."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys

import streamlit as st

if __package__ in {None, ""}:
    # Direct ``streamlit run app/ui/app.py`` execution has no package context;
    # add the repository root so the sibling application modules remain importable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    shell_module = import_module("app.ui.shell")
else:
    shell_module = import_module(f"{__package__}.shell")

default_form_values = shell_module.default_form_values
handle_run_request = shell_module.handle_run_request


def main() -> None:
    defaults = default_form_values()

    st.set_page_config(page_title="Female Character Network Visualizer", layout="centered")
    st.title("Female Character Network Visualizer")
    st.caption("Local UI shell with Docker runner.")

    with st.form("run_form"):
        input_dir = st.text_input("Corpus directory", value=defaults.input_dir)
        output_dir = st.text_input("Output directory", value=defaults.output_dir)
        lmstudio_base_url = st.text_input(
            "LM Studio base URL",
            value=defaults.lmstudio_base_url,
        )
        model_name = st.text_input("Model name", value=defaults.model_name)
        submitted = st.form_submit_button("Start run")

    st.subheader("Status")

    if submitted:
        progress_placeholder = st.empty()
        output_lines: list[str] = []

        def show_progress(line: str) -> None:
            output_lines.append(line)
            progress = shell_module.ProgressReporter().from_result(
                stdout="\n".join(output_lines), stderr="", succeeded=True
            )
            progress_placeholder.write(
                f"Current stage: `{progress.current_stage}` — {progress.message}"
            )

        response = handle_run_request(
            {
                "input_dir": input_dir,
                "output_dir": output_dir,
                "lmstudio_base_url": lmstudio_base_url,
                "model_name": model_name,
            },
            output_callback=show_progress,
        )
        if response.result and response.result.succeeded:
            if (
                response.progress_state
                and response.progress_state.status == "completed_with_omissions"
            ):
                st.warning(response.status_message)
            else:
                st.success(response.status_message)
        else:
            st.error(response.status_message)

        if response.progress_state:
            st.write(f"Current stage: `{response.progress_state.current_stage}`")
            if (
                response.progress_state.completed_files is not None
                and response.progress_state.total_files is not None
            ):
                processed_count = response.progress_state.completed_files
                total_count = response.progress_state.total_files
                st.write(
                    "Files processed: "
                    f"{processed_count}/{total_count}"
                )
            st.write(f"Run state: `{response.progress_state.status}`")
            if response.progress_state.message:
                st.write(response.progress_state.message)

        if response.result:
            if response.result.stdout.strip():
                st.code(response.result.stdout.strip(), language="text")
            if response.result.stderr.strip():
                st.code(response.result.stderr.strip(), language="text")
    else:
        st.info(
            "Ready. Enter run inputs, then click Start run."
        )


if __name__ == "__main__":
    main()
