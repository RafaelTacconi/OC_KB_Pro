"""
service/ — the staging HTTP service (SPEC.md §20.9-§20.13).

A separate process from the Streamlit app. It REUSES retrieval/, prompting/, and
models/ and duplicates none of that logic. `service.engine` is the answer
pipeline; `service.api` is the stdlib HTTP server (localhost-only, static-key
auth). Start with `python -m service.api`.
"""
