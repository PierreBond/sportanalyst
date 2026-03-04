# PROMPTS.md — Operator's Prompt Library

> **Purpose:** Ready-to-paste prompts for working with, reviewing, and analyzing the AI agent building the Sports Prediction System. Copy the prompt you need, paste it into your AI agent session, and go.
>
> **Files in the system:**
> | File | Role |
> |:---|:---|
> | `AI Agent Coding Guide.md` | Immutable spec (agent reads, never modifies) |
> | `PROGRESS.md` | Mutable state (agent reads and updates every step) |
> | `PROMPTS.md` | **This file** — your operator toolkit (human use only) |

---

## Table of Contents

1. [Session Prompts](#1-session-prompts) — Start, resume, end sessions
2. [Review Prompts](#2-review-prompts) — Audit code quality, rules compliance
3. [Analysis Prompts](#3-analysis-prompts) — Understand decisions, measure progress
4. [Debugging Prompts](#4-debugging-prompts) — Investigate failures, fix issues
5. [Steering Prompts](#5-steering-prompts) — Redirect, reprioritize, course-correct
6. [Testing Prompts](#6-testing-prompts) — Validate quality, run checks
7. [Reporting Prompts](#7-reporting-prompts) — Get summaries, status updates

---

## 1. Session Prompts

### 1.1 Start a New Session (Standard)

```
You are building the Sports Prediction System.

WORKFLOW:
1. Read "AI Agent Coding Guide.md" — this is your immutable specification.
2. Read "PROGRESS.md" — this is your mutable state tracker.
3. Pick up where the last session left off.
4. After completing each step, update PROGRESS.md (check the box + add a session log entry).
5. Follow ALL rules in the guide (Sections A-Q). No exceptions.
6. If anything is ambiguous, default to the safer, more explicit option.
7. Write tests alongside implementation code.
8. Do not create extra markdown files for tracking — use PROGRESS.md only.

BEGIN.
```

### 1.2 Start a Session — Specific Step

```
You are building the Sports Prediction System.

Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Skip ahead and work on STEP [XX] specifically. Follow all rules from the guide.
After completing the step, update PROGRESS.md.
If STEP [XX] has unmet dependencies, list them and ask before proceeding.

BEGIN.
```

### 1.3 Start a Session — Specific Sprint

```
You are building the Sports Prediction System.

Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Focus on completing all remaining steps in Sprint [N].
Work through them sequentially. After each step, update PROGRESS.md.
Follow all rules from the guide.

BEGIN.
```

### 1.4 Resume After a Crash / Interrupted Session

```
You are building the Sports Prediction System.

Read "AI Agent Coding Guide.md" and "PROGRESS.md".
The last session was interrupted. Check PROGRESS.md for any step marked [~] (in progress).
If you find one:
  1. Inspect the actual files to determine what was partially done.
  2. Complete the remaining work for that step.
  3. Mark it [x] and log what you finished.
Then continue to the next step.

BEGIN.
```

### 1.5 End a Session Gracefully

```
Stop working on new steps. For the current step:
- If it's nearly done, finish it and mark [x] in PROGRESS.md.
- If it's far from done, mark it [~] and describe exactly what remains.

Add a session log entry to PROGRESS.md with:
- All steps completed this session
- Any decisions made
- Any issues encountered
- NEXT: the exact next action for the following session

Update the "Current Status" table at the top of PROGRESS.md.
Do not start any new steps.
```

---

## 2. Review Prompts

### 2.1 Full Code Review — Last Session's Work

```
Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Look at the session log for the most recent session. Identify every file that was created or modified.

For each file, review against the guide's rules:
- Does it follow RULE-01 through RULE-28 (Section A)?
- Are all functions type-hinted with docstrings?
- Is logging done with structlog (no print)?
- Are there any magic numbers?
- For features: does the code respect temporal boundaries (RULE-24, RULE-25)?

Report your findings as:

## Code Review — Session [N]
### ✅ Compliant
- [list files that pass all rules]

### ⚠️ Minor Issues
- [file:line — what's wrong — which rule is violated]

### ❌ Critical Issues
- [file:line — what's wrong — which rule is violated]

### Suggested Fixes
- [concrete code changes]

Do NOT modify any files. Report only.
```

### 2.2 Review a Specific Module

```
Read "AI Agent Coding Guide.md".
Review all code in the [services/MODULE_NAME/] directory.

Check for:
1. Compliance with all rules in Section A (code style, types, logging, errors).
2. Compliance with the module-specific section in the guide (Section [X]).
3. Test coverage — does every public function have a corresponding test?
4. Data safety — any risk of temporal leakage (RULE-24 through RULE-28)?
5. Schema compliance — does it use the shared Pydantic schemas from libs/?

Produce a structured review report. Do NOT modify any files.
```

### 2.3 Review Database Migrations

```
Read Section D of "AI Agent Coding Guide.md".
Read all files in the Alembic migrations directory.

Check:
1. Does every migration have a corresponding DOWN revision?
2. Do table schemas match the SQL in Section D.1 of the guide?
3. Are there any migrations that could cause data loss?
4. Are indexes present as specified?
5. Is there any drift between the SQLAlchemy models and the migration files?

Report findings. Do NOT modify files.
```

### 2.4 Review for Data Leakage

```
Read "AI Agent Coding Guide.md" — specifically RULE-24 through RULE-28 and Section G.3.

Scan ALL feature engineering code and training data loaders for potential data leakage:
1. Any feature that uses data from AFTER the prediction timestamp.
2. Any join that uses `<` instead of `<=` on timestamps.
3. Any feature marked `training_eligible: false` that appears in training datasets.
4. Any use of closing-line odds in training features.
5. Any random cross-validation splits instead of chronological.

This is the most critical review. Be exhaustive. Report every suspicious pattern.
Do NOT modify files.
```

### 2.5 Diff Review — What Changed Since Last Commit

```
Read "PROGRESS.md" to see what was done in the last session.
Run `git diff HEAD~1` (or check uncommitted changes with `git status` and `git diff`).

Review every changed line against "AI Agent Coding Guide.md" rules.
Flag anything that:
- Violates a numbered RULE
- Deviates from the folder structure in Section B
- Uses a schema not defined in libs/sports_common/schemas/
- Introduces a new dependency not in the tech stack (Section 11 of Implementation Plan)

Report findings as a structured review.
```

---

## 3. Analysis Prompts

### 3.1 Progress Summary

```
Read "PROGRESS.md".
Give me a concise status report:

1. **Overall:** X of 84 steps done (Y%).
2. **Current sprint:** Sprint [N] — X of Y steps done.
3. **Velocity:** Average steps per session over the last 3 sessions.
4. **Estimated completion:** At current velocity, how many sessions remain?
5. **Blockers:** Any steps marked [!]? What's blocking them?
6. **Risk areas:** Any steps marked [~] for too long?

Keep it brief — table format preferred.
```

### 3.2 Architecture Analysis

```
Read "AI Agent Coding Guide.md" and examine the current codebase.

Analyze the system architecture as built so far:
1. Draw the data flow: which services talk to which? Via Kafka or HTTP?
2. Are there any circular dependencies between modules?
3. Are the shared schemas in libs/ actually being used consistently?
4. Is the Kafka topic design from Section E.2 correctly implemented?
5. Any architectural concerns or tech debt accumulating?

Present findings with a text-based diagram if helpful.
```

### 3.3 Decision Audit

```
Read "PROGRESS.md" — specifically the Decisions Log and Session Log sections.

List every decision the agent made that deviated from the guide.
For each, evaluate:
1. Was the deviation justified?
2. Could it cause problems downstream?
3. Should it be reverted or accepted?

Present as a table:
| Decision | Justified? | Risk | Recommendation |
```

### 3.4 Dependency Analysis

```
Read the pyproject.toml files across all services and libs/.
Also check package.json for the frontend.

Analyze:
1. Are all dependencies pinned to specific versions?
2. Any conflicting version requirements between services?
3. Are there unused dependencies (imported but never used in code)?
4. Are there missing dependencies (imported in code but not in pyproject.toml)?
5. Any known security vulnerabilities? (check against recent CVE databases)

Report findings.
```

### 3.5 Quality Metrics Snapshot

```
Read the codebase and run analysis:

1. Run `ruff check .` — how many lint violations?
2. Run `mypy` — how many type errors?
3. Run `pytest --co -q` — how many tests exist?
4. Estimate test coverage based on test file count vs. source file count.
5. Count: how many functions lack type hints? Lack docstrings?
6. Count: how many files use `print()` instead of structlog?

Present as a quality dashboard table.
```

---

## 4. Debugging Prompts

### 4.1 Investigate a Failing Test

```
Read "AI Agent Coding Guide.md" for context.

The following test is failing:
[paste test output or describe the failure]

1. Read the test file and understand what it's testing.
2. Read the source code it's testing.
3. Identify the root cause.
4. Fix the issue in the source code (not the test), unless the test itself is wrong.
5. Run the test again to verify the fix.
6. Update PROGRESS.md if this relates to a tracked step.
```

### 4.2 Investigate a Runtime Error

```
Read "AI Agent Coding Guide.md" for context.

The following error occurred at runtime:
[paste the error/traceback]

1. Trace the error to its source file and line.
2. Read the surrounding code and the relevant guide section.
3. Identify root cause — is it a code bug, config issue, or missing dependency?
4. Fix it.
5. Write a test that would have caught this error.
6. Update PROGRESS.md log.
```

### 4.3 Debug Data Pipeline Issues

```
Read Sections E, F, and G of "AI Agent Coding Guide.md".

Data is not flowing correctly through the pipeline. Investigate:
1. Kafka: Are messages being produced to the expected topics? Check consumer lag.
2. Adapters: Are API calls succeeding? Check response status codes in logs.
3. Validators: Are events being rejected? Check validation error logs.
4. Feature engine: Is the Spark job running? Check Spark UI / logs.
5. Database: Are records appearing in the expected tables?

Trace the flow step-by-step from source to destination. Report where it breaks.
```

### 4.4 Debug Model Training Issues

```
Read Section H of "AI Agent Coding Guide.md".

Model training is failing or producing poor results. Investigate:
1. Data loader: Is the chronological split correct? Check train/val/test sizes.
2. Features: Any NaN/inf values in the feature matrix? Run `df.describe()`.
3. Target: Is the target column correctly encoded?
4. Hyperparameters: Compare config YAML to Section H.3.
5. MLflow: Check the run's logged metrics — are they reasonable?
6. Leakage: Run the data leakage tests. Any failures?

Report findings and fix if the cause is clear.
```

---

## 5. Steering Prompts

### 5.1 Skip a Step

```
Read "PROGRESS.md".
Mark STEP [XX] as [-] (skipped).
Add a note to the Decisions Log: "Skipped STEP XX because: [your reason]."
Update the Current Status table.
Continue to the next step.
```

### 5.2 Redo a Step

```
Read "AI Agent Coding Guide.md" and "PROGRESS.md".
STEP [XX] was previously completed but needs to be redone.

1. Change its status from [x] to [ ] in PROGRESS.md.
2. Read the guide section for that step.
3. Review the existing code for that step.
4. Reimplement it from scratch (or fix the specific issues below):
   [describe what's wrong]
5. Mark [x] when done and log the redo in the session log.
```

### 5.3 Change Priority — Do This Step Next

```
Read "PROGRESS.md".
Regardless of the normal sequence, work on STEP [XX] next.
Check if its dependencies are met. If not, list what's missing and work on those first.
Update PROGRESS.md accordingly.
```

### 5.4 Add a New Step

```
Read "PROGRESS.md".

Add a new step to the checklist:
- Step number: STEP 84.X (insert after STEP [XX])
- Description: [describe the new task]
- Guide section: [relevant section or "custom"]

Log this addition in the Decisions Log with rationale.
Then implement it.
```

### 5.5 Pause and Explain Before Continuing

```
STOP coding. Do NOT write or modify any files.

Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Before doing any more work, explain:

1. What is the next step you would take?
2. What files would you create or modify?
3. What guide sections are relevant?
4. Are there any decisions you'd need to make?
5. Are there any risks or concerns?

Wait for my approval before proceeding.
```

---

## 6. Testing Prompts

### 6.1 Run All Tests and Report

```
Run the full test suite:
  pytest --tb=short -q

Report the results as:
- Total tests: X
- Passed: X
- Failed: X (list each with file:test_name and failure reason)
- Errors: X
- Warnings: X

For any failures, identify which STEP they relate to by checking PROGRESS.md.
```

### 6.2 Run Data Leakage Tests Only

```
Run ONLY the data leakage tests:
  pytest -k "leakage" -v

This is the most critical test category.
If ANY test fails, treat it as a P0 blocker.
Report every failure with the exact violated rule from Section A (RULE-24 through RULE-28).
```

### 6.3 Test a Specific Module

```
Run tests for the [MODULE_NAME] service only:
  pytest services/[MODULE_NAME]/tests/ -v

Report results. For any failures, read the source code, identify the bug, and fix it.
Update PROGRESS.md if a fix was applied.
```

### 6.4 Generate Missing Tests

```
Read "AI Agent Coding Guide.md" Section Q (Testing Strategy).
Scan the codebase for public functions and API endpoints that lack tests.

For each missing test:
1. List the function/endpoint and its location.
2. Write the test in the correct test file.
3. Run it to verify it passes.

Target: meet the coverage requirements in RULE-QA1 through RULE-QA5.
Update PROGRESS.md after.
```

### 6.5 Validate Schema Consistency

```
Read the Pydantic schemas in libs/sports_common/schemas/.
Read the database schema in the Alembic migrations.
Read the API response schemas in model_serving.

Check:
1. Do Pydantic field names match database column names?
2. Do API responses match the schema defined in Section M.2 of the guide?
3. Are there any schema fields defined in code but not in the guide (or vice versa)?

Report mismatches.
```

---

## 7. Reporting Prompts

### 7.1 Daily Standup Summary

```
Read "PROGRESS.md".

Give me a 30-second standup summary:
- **Yesterday:** Steps completed in the last session.
- **Today:** Next 2-3 steps to work on.
- **Blockers:** Anything preventing progress.

Keep it under 5 bullet points total.
```

### 7.2 Sprint Retrospective

```
Read "PROGRESS.md" — specifically all session logs from Sprint [N].

Produce a sprint retrospective:

1. **Planned vs Actual:**
   - How many steps were planned for this sprint?
   - How many were completed?
   - Any steps that took significantly longer than expected?

2. **What went well:**
   - [agent findings from the session logs]

3. **What went wrong:**
   - [issues, blockers, redos from the session logs]

4. **Decisions made:**
   - [list from Decisions Log that fall within this sprint]

5. **Recommendations for next sprint:**
   - [based on patterns observed]
```

### 7.3 Full Project Health Report

```
Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Also scan the codebase.

Produce a health report:

| Area | Status | Details |
|:---|:---|:---|
| Progress | X/84 steps (Y%) | Sprint N, on track / behind / ahead |
| Code Quality | ✅/⚠️/❌ | Lint violations, type errors, missing docstrings |
| Test Coverage | X% estimated | Y tests passing, Z failing |
| Data Safety | ✅/⚠️/❌ | Leakage test results |
| Architecture | ✅/⚠️/❌ | Any structural concerns |
| Tech Debt | Low/Med/High | Accumulated shortcuts or TODOs |
| Blockers | N active | List if any |

Then list the top 3 risks and recommended actions.
```

### 7.4 Generate Changelog

```
Read "PROGRESS.md" session logs from Session [X] to Session [Y].

Generate a changelog in Keep a Changelog format:

## [Unreleased]
### Added
- ...

### Changed
- ...

### Fixed
- ...

Group by module/service when possible.
```

### 7.5 Export Current State for Handoff

```
Read "AI Agent Coding Guide.md" and "PROGRESS.md".
Scan the codebase.

Produce a handoff document that a NEW agent (or human developer) can read to take over:

1. **Project summary:** One paragraph.
2. **Current state:** Which steps are done, in progress, blocked.
3. **Codebase map:** What exists in each directory, how big each module is.
4. **Key decisions:** Any deviations from the guide and why.
5. **Known issues:** Anything broken or incomplete.
6. **Immediate next steps:** Exactly what to do first.
7. **Environment setup:** How to get a dev environment running.

This should be self-contained — the reader should not need to ask clarifying questions.
```

---

## Tips for Using These Prompts

1. **Always start sessions with 1.1** — the standard start prompt. Use the others only when you need specific behavior.
2. **Run 2.1 (code review) after every 3-5 steps** — don't let quality drift accumulate.
3. **Run 2.4 (leakage review) after Sprint 3** — this is the highest-risk area.
4. **Use 5.5 (pause and explain) when the agent seems off track** — forces it to plan before acting.
5. **Use 7.1 (standup) at the start of your day** — quick snapshot before deciding what to work on.
6. **Use 3.1 (progress summary) weekly** — track whether velocity is sustainable.
7. **Keep this file open alongside PROGRESS.md** — they're your two control surfaces.

---

*This prompt library is for human operators. The AI agent should not read or modify this file.*
