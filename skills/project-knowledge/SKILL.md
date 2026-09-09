---
name: project-knowledge
description: Preserve development intent and implementation knowledge between agents and development sessions.
---

# Project Knowledge System

## Purpose

This project uses a persistent knowledge system to preserve development intent and implementation knowledge between agents and development sessions.

The knowledge system has three important concepts:

### Specifications

Specifications describe what the project is intended to do.

They represent agreed requirements and behavior.

Specifications are authoritative for intended behavior unless the user explicitly changes that intent.

### Documentation

Documentation describes what the implementation actually does.

Documentation is derived from the implementation and must remain consistent with it.

### Verification

Verification checks whether:

- the implementation satisfies specifications;
- documentation accurately describes implementation;
- the knowledge structure is complete and valid.

Knowledge is not considered trustworthy merely because an agent generated it. It should be verified against the project.

---

# Authority

Use the following authority order:

```text
User intent
    ↓
Specifications
    ↓
Implementation
    ↓
Documentation
```

The user is the final authority.

If a user request conflicts with an existing specification, do not silently change the specification. Ask the user to resolve the conflict.

If implementation conflicts with a clear specification, correct the implementation.

If documentation conflicts with implementation, update the documentation.

If the intended behavior is ambiguous, ask the user rather than inventing requirements.

---

# Core Development Loop

For significant changes, follow this process:

```text
Search
  ↓
Understand
  ↓
Plan
  ↓
Specify
  ↓
Implement
  ↓
Test
  ↓
Verify
  ↓
Document
  ↓
Verify
```

Do not treat this as a rigid ceremony for trivial changes. Use judgment about whether a change is significant enough to affect project knowledge.

---

# Before Making Significant Changes

## 1. Search

Search the knowledge system for information relevant to the change.

Use:

```text
knowledge search "<query>"
```

Look for:

- related specifications;
- related implementation documentation;
- architectural decisions;
- constraints;
- existing behavior.

Do not immediately begin modifying code without checking relevant project knowledge.

## 2. Read Relevant Knowledge

Read specifications and documentation that affect the planned change.

Determine:

- what behavior is required;
- what constraints exist;
- how the existing implementation works;
- what other components may be affected.

## 3. Determine Whether Intent Needs to Change

Ask:

> Is this change implementing existing intent, or does it introduce/change project requirements?

If existing intent is sufficient, continue.

If the change introduces new material requirements, create or update a specification before implementation.

Do not create specifications merely to document implementation details.

## 4. Resolve Ambiguity

If the required behavior cannot be determined confidently from:

- the user's request;
- existing specifications;
- existing documentation;
- the implementation;

ask the user.

Do not silently invent important requirements.

---

# During Implementation

Implement according to the specification.

If the implementation reveals that a requirement is ambiguous or contradictory, stop and resolve the ambiguity with the user.

Do not modify specifications simply to make an implementation appear compliant.

---

# After Implementation

## 1. Test

Run the project's appropriate tests and validation.

The knowledge system does not replace normal software testing.

## 2. Verify Specifications

Run verification for specifications affected by the change.

For example:

```text
knowledge spec verify knowledge/spec/authentication.spec.md
```

If verification fails:

1. inspect the failure;
2. determine whether the implementation violates the specification;
3. fix the implementation;
4. verify again.

Do not simply mark the specification as satisfied.

## 3. Update Documentation

Update documentation for every affected implementation file.

Documentation should describe the resulting implementation, not the implementation that existed before the change.

Create missing documentation where necessary.

## 4. Verify Documentation

Verify affected documentation against the implementation.

For example:

```text
knowledge doc verify src/auth/AuthService.cs
```

If verification fails:

1. inspect the implementation;
2. update the documentation;
3. verify again.

---

# Completion Criteria

A significant change is complete when:

- the implementation satisfies applicable specifications;
- tests pass or known failures have been explicitly addressed;
- affected files have documentation;
- documentation accurately describes the resulting implementation;
- relevant knowledge verification passes;
- no material ambiguity remains unresolved.

Do not consider a change complete merely because the code compiles.

---

# Maintaining Knowledge

Knowledge maintenance is part of normal development.

When changing a file:

```text
check its documentation
        ↓
make implementation changes
        ↓
update documentation
        ↓
verify documentation
```

When changing behavior:

```text
check specifications
        ↓
determine whether intent changes
        ↓
update specification if necessary
        ↓
implement
        ↓
verify
```

Do not rewrite unrelated knowledge.

Keep knowledge focused on information that helps another agent understand and modify the project.

---

# Using the Knowledge MCP

Prefer the knowledge MCP when available.

The MCP provides access to the knowledge system without requiring manual shell interaction.

Use it to:

- search knowledge;
- read specifications;
- read documentation;
- create specifications;
- update specifications;
- create documentation;
- update documentation;
- verify knowledge;
- inspect project health.

The MCP is an interface to the knowledge system. The underlying knowledge files remain the persistent source of project knowledge.

---

# When to Use Specifications

Create or update a specification when a change establishes meaningful project intent.

Examples include:

- introducing a new subsystem;
- establishing an API contract;
- defining important business behavior;
- establishing architectural constraints;
- changing externally visible behavior;
- defining non-trivial acceptance criteria.

Do not create a specification for every small code change. Use judgment.

---

# When to Ask the User

Ask the user when:

- existing specification conflicts with the requested behavior;
- requirements are materially ambiguous;
- multiple interpretations would produce meaningfully different implementations;
- an architectural decision cannot reasonably be inferred;
- verification reveals a conflict between stated intent and implementation that cannot be resolved automatically.

Do not ask unnecessary questions when the answer can reasonably be determined from the project.

---

# General Principle

The purpose of the knowledge system is not to eliminate the need for an agent to understand the codebase.

Its purpose is to preserve the understanding that previous agents and developers have already established.

Before changing the project, learn from its accumulated knowledge.

After changing the project, leave the knowledge accurate for the next agent.
