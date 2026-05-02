# HackerRank Orchestrate Agent

A terminal-based support triage agent that routes tickets across HackerRank, Claude, and Visa using a local support corpus.

## Installation

```bash
# No external dependencies required — uses only stdlib (os, csv, json, pathlib, re, collections)
python3 --version  # Requires Python 3.7+
```

## Running the Agent

```bash
cd code/
python3 main.py
```

This will:
1. Load all markdown files from `data/` into memory
2. Process each row in `support_tickets/support_tickets.csv`
3. Write predictions to `support_tickets/output.csv`

## Architecture

### CorpusLoader
- Loads all markdown files from `data/{hackerrank,claude,visa}/`
- Builds in-memory index of word → (company, doc_id) mappings
- Provides `search()` method for keyword-based retrieval

### TicketClassifier
- **classify_company()** — Infer company from issue text if not provided
- **get_risk_level()** — Detect high-risk categories (billing, fraud, account access, compliance)
- **classify_request_type()** — Map to product_issue/feature_request/bug/invalid
- **infer_product_area()** — Guess specific product area (api, billing, auth, etc.)

### SupportAgent
- **process_ticket()** — Main routing logic:
  1. Classify request and assess risk
  2. If high-risk → escalate immediately
  3. If invalid → escalate with explanation
  4. Search corpus for relevant docs
  5. If no match → escalate
  6. If match found → reply with excerpt + justification

## Design Decisions

### Why keyword-based retrieval?
- **Pro**: Fast, deterministic, no API calls, interpretable, no hallucination
- **Con**: Lower recall on semantic variations
- **Future**: Can upgrade to TF-IDF or embeddings (sentence-transformers) for better matching

### Why escalate on high-risk categories?
- Billing, fraud, account access, compliance issues require human judgment
- Prevents hallucinated policies or incorrect procedures
- Aligns with safety-first philosophy

### Why no external dependencies?
- Keeps the solution portable and reproducible
- No dependency pinning issues
- Fast startup (corpus loads instantly from local markdown)

## Future Improvements

1. **Better Retrieval**:
   - TF-IDF scoring instead of simple word counts
   - BM25 algorithm
   - Sentence-transformers for semantic search

2. **Smarter Response Generation**:
   - Extract relevant sections from matched docs (not just first 300 chars)
   - Multi-document synthesis
   - Question-answering model (e.g., LFQA)

3. **Better Escalation**:
   - Confidence scores on matches
   - Threshold-based routing
   - User sentiment analysis

4. **Structured Reasoning**:
   - Chain-of-thought logging for explainability
   - Prompt templates for response generation
   - LLM-powered classification (optional, requires API key)

## Running on Sample Data

To test your agent during development:

```bash
# Copy sample tickets over for testing
cp support_tickets/sample_support_tickets.csv support_tickets/support_tickets.csv
python3 main.py

# Compare output.csv against the expected outputs in sample_support_tickets.csv
```

## Environment Variables

Currently, no environment variables are required. If you add LLM support later:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
python3 main.py
```

## Notes

- Responses are grounded in the provided corpus only
- No hallucination of policies or steps
- Deterministic (seeded, no randomness)
- Reproducible (all results depend only on input CSV and corpus)
