# THINK Remix v2.0: Multi-Agent Reasoning Workflow

A sophisticated multi-agent reasoning system that processes questions through multiple analytical personas with different epistemological frameworks, maintains a centralized evidence registry with credibility scoring, validates persona diversity, enforces evidence consistency, adjudicates null hypotheses, and produces robust final decisions with quantified confidence scores.

## Architecture Overview

The workflow consists of 19 nodes organized into several phases:

### Phase 1: Question Processing & Setup
1. **User Input** - Receives user question
2. **Question Audit Gate** - Validates question is answerable and well-formed
3. **Analyze Question** - Breaks down question structure
4. **Generate Null Hypotheses** - Creates skeptical falsification tests
5. **Central Evidence Registry** - Stateful accumulator for all evidence

### Phase 2: Persona Analysis
6. **Dynamic Persona Allocator** - Determines optimal number and types of personas
7. **Persona Divergence Validator** - Ensures cognitive diversity
8. **Persona Analysis (A-N)** - Multiple analytical personas with different frameworks
9. **Synthesis Engine** - Integrates conflicting analyses
10. **Adversarial Evidence Injector** - Finds systematically ignored evidence

### Phase 3: Evidence & Disagreement Resolution
11. **Analyze Disagreement** - Maps conflicts and divergence points
12. **Null Hypothesis Adjudicator** - Systematically tests null hypotheses
13. **Conduct Research** - Dual-track confirmatory/disconfirmatory research
14. **Evidence Consistency Enforcer** - Detects cherry-picking
15. **Evidence Adjudicator** - Resolves conflicts using credibility scores

### Phase 4: Final Synthesis
16. **Case File** - Compiles evidence with traceability
17. **Coverage Validator** - Ensures information preservation
18. **Decision Robustness Calculator** - Quantifies decision strength
19. **Final Arbiter** - Produces final judgment with confidence bounds

## Key Features

- **Evidence-Grounded**: All claims trace to Central Evidence Registry (CER) fact IDs
- **Diversity-Enforced**: Persona Divergence Validator ensures cognitive diversity
- **Falsification-Tested**: Null Hypothesis Adjudicator systematically tests skeptical claims
- **Compression-Resistant**: Coverage Validator prevents information loss
- **Robustness-Quantified**: Decision Robustness Score (DRS) constrains confidence
- **Adversarially-Hardened**: Adversarial Evidence Injector finds blind spots

## Usage

```python
from google.adk import Runner
from . import agent

runner = Runner()
result = await runner.run_async(
    agent=agent.root_agent,
    user_input="Your question here"
)
```

## Implementation Status

This is a foundational implementation. Full implementation requires:
- Custom state management for Central Evidence Registry
- Complex conditional workflow logic
- JSON schema validation between nodes
- Custom tools for credibility scoring and validation

See the specification document for complete implementation details.

