# Issue 20: LLM-based gender inference for merged entities

## Problem

Current rule-based `gender_inference` is too weak for this corpus. Suffix heuristics fail on obvious female cases and interact badly with noisy merged names, for example candidates like `анна<tab>...` that should still be recoverable as female from nearby evidence such as `цесарица`.

## Scope

Replace primary rule-based female/non-female inference in entity merge with local-LLM classification over merged aliases and evidence.

## Deliverables

- prompt for merged-entity gender inference
- entity-merge wiring that calls local LLM for gender classification
- canonical-name sanitization for obvious extraction-noise markers before merge
- regression tests for noisy-name female cases
- plan/docs updates describing LLM-first gender inference

## Acceptance criteria

- merged entities can obtain `gender_inference` from local LLM
- noisy names like `анна<tab>...` are canonicalized to usable labels such as `анна`
- obvious female evidence such as `цесарица` can lead to `female`
- existing graph/export pipeline still works with enriched `gender_inference`
- tests cover both heuristic fallback and LLM-driven inference

## Plan

1. add dedicated prompt template for merged-entity gender inference
2. update entity merge service to:
   - sanitize extraction-noise markers before canonicalization
   - merge aliases/evidence first
   - classify merged entity gender with local LLM when available
   - fall back to existing heuristic only when LLM path is unavailable or unusable
3. wire main pipeline to pass shared LLM client into merge stage
4. update project and plan docs to describe LLM-first gender inference
5. add regression tests for `анна<tab>...` / `цесарица` style cases
6. run scaffold test suite
