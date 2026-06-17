# Evaluation note

How I measure whether Gifty's recommendations are good, and how I would extend it.

The pipeline uses an LLM, so the same input can produce different output. Ordinary tests catch
crashes but not quality slipping after a prompt change or a model swap. So I split evaluation
into two kinds of check: automatic ones with a clear right answer that I verify in code, and
judgement ones that need an opinion, which I score against a simple 1-5 rubric.

## What I check

1. **Gift relevance.** Each gift should follow from a real signal in the profile, not a generic
   pick. I score this by judgement, 1-5.
2. **Link validity.** Every product URL must load and point to a store, not a blog. I check this
   automatically, and the pipeline already enforces it: the validate node drops dead links and
   the model can only reuse URLs that survived, so it cannot invent one.
3. **Budget and country fit.** The price must sit inside the given budget and currency, and the
   store must serve the contact's country. I parse the price automatically and judge the rest.
4. **Professional appropriateness.** It has to suit a work relationship, nothing too personal. I
   score this by judgement.
5. **Sensitive or creepy avoidance.** The output must avoid religion, politics, health,
   ethnicity, gender, and family status. I check this automatically by scanning for those terms,
   and a deterministic filter already strips such signals regardless of what the model returns.
6. **Message quality.** The note should be warm, specific to a signal, professional, free of
   false assumptions, and short. I score this by judgement.
7. **Failure handling.** When a profile is weak or search returns little, the system must lower
   confidence and flag for human input instead of faking certainty. I check this automatically,
   and it already does this: fewer than three grounded products lowers the result and writes a
   review note, after one bounded retry.

## What I have automated

`test_core.py` runs offline and covers the trust-critical logic:

- Sensitive-term scrubbing (check 5).
- Junk-link filtering and the SSRF guard (supports check 2).
- Defensive parsing of model output, so malformed responses never reach the API.
- Input validation and retry routing (supports check 7).

The grounding and guardrail pieces are covered. The judgement checks (1, 3, 4, 6) I score by
hand for now.

## How I would extend it

1. Build a small fixed set of example contacts across countries, budgets, and signal strength,
   including a few weak or sensitive ones to probe the guardrails.
2. Run the pipeline over that set and apply the automatic checks, failing the run if a link is
   dead or a sensitive term leaks.
3. Score the judgement checks against the 1-5 rubric, then automate that with an LLM grader once
   the rubric is stable, with a human spot-check so the grader does not drift.
4. Save the scores per run so I can compare before and after each change and catch regressions.

I kept the automatic checks focused on what matters most for trust: links are real, nothing
sensitive leaks, and the system degrades honestly on weak data. The quality scoring is the part
that still needs a labelled set and a rubric to fully automate.
