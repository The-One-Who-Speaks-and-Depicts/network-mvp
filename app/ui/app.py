"""Streamlit UI shell for local runs."""

from __future__ import annotations

import streamlit as st

from app.ui.shell import default_form_values, handle_run_request


def main() -> None:
    defaults = default_form_values()

    st.set_page_config(page_title="Female Character Network Visualizer", layout="centered")
    st.title("Female Character Network Visualizer")
    st.caption("Local UI shell. Pipeline execution not implemented yet.")

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
        _, status_message = handle_run_request(
            {
                "input_dir": input_dir,
                "output_dir": output_dir,
                "lmstudio_base_url": lmstudio_base_url,
                "model_name": model_name,
            }
        )
        st.info(status_message)
    else:
        st.info("Ready. Enter run inputs, then click Start run.")


if __name__ == "__main__":
    main()
