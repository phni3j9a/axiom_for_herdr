# Independent Sol review

An Astra planning/advisory participant cannot be the independent Reviewer. Astra
may advise Main on a technical dispute, but Main still adjudicates findings and
decides whether the same Sol Reviewer needs another pass.

Adapted from phni3j9a/axiom's MIT-licensed review guidance.

Start the review cycle in a fresh `reviewer` pane (Sol XHIGH), independent of
implementation and design participants. Keep that same Codex session for useful
re-review. Main owns acceptance, risk tolerance, scope, and the decision to end
or reset a review cycle.

## Review boundary

Supply accepted intent, acceptance criteria, relevant decisions/non-goals, the
candidate diff, existing changes outside scope, and verification already performed.
Scale this to the task; do not demand fields that add no value.

Review project content read-only: no project edits, commits, formatters, auto-fixes,
or commands likely to mutate the candidate. The assigned report directory is the
sole permitted output location. Return evidence and bounded remediation advice.

## Admissible findings

A material finding needs independent current evidence of at least one of:

- a violation of accepted intent or an existing supported contract;
- a concrete failure or regression in the candidate;
- a concrete security, data-integrity, trust-boundary, or compatibility defect;
- a verification gap that materially prevents judging one of those obligations.

Hypothetical future use, optional hardening, preference, style, and generic advice
are not blocking findings. Candidate-created code, tests, schemas, migrations,
documentation, state, or abstractions do not establish that their capability is
required. Prior reviewer suggestions also do not create requirements.

Unnecessary complexity is reviewable when it lacks independent current
justification and materially increases failure surface, operational behavior,
state, dependencies, migrations, or maintenance. Prefer removing unjustified
machinery when that is the smallest correction that meets the current contract.
Do not redesign beyond accepted intent unless that intent cannot otherwise be met.

## Return and adjudication

Use stable finding IDs, for example:

```text
FINDINGS:
- AX-001 <title>
  Evidence: <file/symbol/behavior and independent current basis>
  Impact: <concrete consequence>
  Remediation direction: <smallest useful correction>

VERIFICATION_GAPS: <only material gaps>
RESIDUAL_RISK: <concise relevant uncertainty>
DIRECT_USER_INSTRUCTIONS: <instruction and effect, or none>
```

Return `FINDINGS: none` when there are no material findings. A report's `complete`
status means the review response is finished; it is not a release verdict.

Main classifies findings as ACCEPT, REJECT, DEFER, or ESCALATE as useful. It
translates accepted findings into bounded fixes, preserving design intent and
the user's risk tolerance. Do not blindly forward every reviewer suggestion to
a worker. Concrete evidence remains visible even when Main defers a mitigation.

## Finding Freeze and continuity

The initial review establishes finding IDs and a review boundary, without a fixed
finding count or round limit. After accepted fixes, Main sends the same Reviewer
its adjudication, updated candidate, and verification evidence.

Keep accepted fixes central. Do not reopen REJECT/DEFER concerns without materially
new independent evidence. New findings remain admissible for:

- material defects directly introduced or revealed by an accepted fix;
- newly evidenced concrete material correctness, security, data-integrity,
  trust-boundary, or compatibility defects, including ones missed initially;
- independently evidenced violations of requirements already inside the boundary.

New candidate machinery and prior suggestions still do not create requirements.
Do not restart preference or optional-hardening review. If intent, acceptance,
non-goals, architecture, or risk policy materially changes, Main re-adjudicates
and chooses whether the same session can reset its boundary or a fresh cycle is
useful. A boundary change does not automatically mandate either choice.

If the Reviewer session is lost, Main may create a fresh Sol replacement with
the earlier findings, adjudication, fixes, current candidate, and evidence.
Treat that as recovery, not routine re-review. Never substitute Luna as Reviewer.

Main ends review when the candidate is sufficiently resolved and no accepted
material finding remains unaddressed. Then it closes the Reviewer pane.
