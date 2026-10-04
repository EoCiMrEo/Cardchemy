# Isolated local follow-up query candidate

## Scope and decision boundary

Lane 6's source-only Ask worker uses immutable `related_knowledge_navigation_v3`
and `hybrid_source_navigation_v9` snapshots. Its current local follow-up
resolver can confuse a prior multi-topic turn with one antecedent. This work
stages a general, conservative candidate only. The active resolver, worker,
policy constants, migrations, database, installed services and Ask gate were
not changed. No private review roster, lecture content, provider or network
request was used. Runtime integration needs a separately approved versioned
policy and migration decision.

## Candidate and reason

`backend/app/ai/navigation_query_candidate.py` accepts a named owner in the
current question without consulting history. It considers prior context only
for a parsed bare owner pronoun or narrow possessive ellipsis. It checks the
whole immediately preceding user turn for coordinated/comparison entities,
multiple clauses, multiple acronyms, ambiguous pronouns and generic event
nouns. The earlier turn must yield one short, explicit topic; uncertainty
returns `None` for a clarification outcome. Direct and expanded local queries
stay within 4,000 characters and twelve FTS terms. The candidate has no
provider or source-text interface.

`backend/tests/test_navigation_query_candidate.py` uses invented examples and
temporarily substitutes the candidate into a test worker. The spy confirms
the original current question is the sole embedding input, while only local
retrieval sees the expanded query. It checks one physical embedding attempt,
zero retries and no answer message.

## Verification and limits

- `backend\\venv\\Scripts\\python.exe -m pytest -q
  tests/test_navigation_query_candidate.py tests/test_source_navigation.py
  tests/test_rag_source_only.py`: **53 passed**.
- The targeted `ruff` invocation was unavailable because the backend venv
  has no `ruff` module. Imports and syntax passed under pytest; `git diff
  --check` reported no whitespace errors for the new files.
- These synthetic tests prove only a local candidate contract. They do not
  measure PDF usefulness, real hybrid retrieval, a fresh private holdout or
  release readiness. Ask remains disabled. The failed public GTE audit was
  not repeated or tuned.
