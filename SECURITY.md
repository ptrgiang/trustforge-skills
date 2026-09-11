# Security Policy

TrustForge deals with agent capabilities and potentially untrusted skill content. Treat analyzed repositories and skills as untrusted input.

## Current safety boundary

The v0.1 SkillDiff scanner performs static text inspection only. It does **not** execute the skill being analyzed.

Do not change that boundary casually. Any future behavioral replay must run in an explicit sandbox with constrained filesystem, network, credentials, CPU, memory, and time.

## Reporting a vulnerability

Please avoid publishing exploit details in a public issue before maintainers have had a reasonable opportunity to review them. Use GitHub's private vulnerability reporting feature when available.

Useful reports include:

- affected version/commit;
- minimal reproduction;
- expected vs actual security boundary;
- impact;
- suggested mitigation if known.

## Non-goals

A clean SkillDiff result is not proof that a skill is safe. Static heuristics can miss obfuscation, binaries, generated code, transitive dependencies, and runtime downloads.
