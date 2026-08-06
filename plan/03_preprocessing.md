# Realisation Plan: Preprocessing

## Objectives

For each input file:

1. read original text,
2. log original text,
3. normalize text to canonical Old East Slavic form,
4. remove line breaks,
5. preserve punctuation,
6. preserve token alignment where possible,
7. produce lemma sequence.

## Suggested outputs per file

- `logs/original/<file>.txt`
- `output/normalized/<file>.txt`
- `output/lemmas/<file>.txt`
- optional structured metadata row in aggregate table

## Implementation steps

### Step 1: file ingestion
- discover `.txt` files
- validate encoding assumptions
- assign stable file IDs

### Step 2: original logging
- save original plain text per file
- include filename mapping if file IDs are used

### Step 3: normalization
- implement prompt template for normalization only
- specify no commentary in output
- preserve punctuation
- remove line breaks in post-processing if needed
- record warnings when alignment likely changed

### Step 4: lemmatization
- separate prompt template for lemma sequence
- return one plain-text token sequence
- preserve token order where possible

## Fallback mode

If LLM quality is insufficient:

- use dictionary/rule-based normalization where available,
- use deterministic text transforms for safe substitutions,
- keep pipeline pluggable so LLM and fallback can be swapped.

## Quality controls

- reject empty outputs
- detect gross token-count drift
- log per-file preprocessing status
- keep raw LLM responses if debugging is enabled

## Risks

- small local model may hallucinate edits,
- historical forms may be normalized inconsistently,
- token alignment may degrade.

## Deliverables

- preprocessing module
- normalization prompt
- lemmatization prompt
- per-file logs and outputs
- preprocessing summary report
