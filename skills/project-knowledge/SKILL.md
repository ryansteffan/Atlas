---
name: project-knowledge
description: Preserve project intent and implementation knowledge across AI-assisted development sessions.
---

# Project Knowledge Skill

Use the `knowledge` CLI to preserve project intent and implementation knowledge.

## Before significant changes

1. Run `knowledge search "<query>"`.
2. Read relevant specifications and canonical documentation.
3. Create or update a specification when the change establishes meaningful intent.
4. Ask the user when material intent is ambiguous.

## During implementation

Implement according to applicable specifications. Do not rewrite specifications merely
to accommodate an incorrect implementation.

## After implementation

Run project tests, then run `knowledge verify`. Update affected documentation with
`knowledge doc update <project-path>` and verify it. Verification reports are
read-only; fix the implementation or knowledge explicitly.
