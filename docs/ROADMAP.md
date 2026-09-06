# Roadmap and proof boundary

## P0 implemented locally

Versioned validated schemas; local source analysis/cache; packaged built-in profiles; deterministic talking-head planning; controlled caption serialization with an explicit FFmpeg subtitle capability gate; local FFmpeg rendering; Shorts candidate/project generation; and measured local QA reports/tests. Caption burn-in additionally requires libass and usable fonts.

## P1 interfaces, not implemented

Faceless assembly, licensed-asset workflows/indexing, remote vision/audio adapters, advertising briefs/creative review, and richer platform-specific export policies.

## P2 interfaces, not implemented

Publishing/account integrations, collaboration, remote job orchestration, telemetry/observability, and commercial workflow controls.

Status: implementation and local tests are distinct from CI, deployment, authenticated providers, persistence outside the local filesystem, and live verification. P0 documentation does not claim those higher proof layers.

## P0 local verification checkpoint (2026-09-06)

`IMPLEMENTED` and `TESTED`: the local P0 workflow has a timestamped record in [VERIFICATION.md](VERIFICATION.md), including Ruff, complete pytest, FFmpeg integration, CLI smoke, artifact, source-immutability, and QA checks. `DEPLOYED` and `VERIFIED LIVE` remain `BLOCKED / UNVERIFIED — no deployment target in scope`.

## Explicit design-contract deferrals after final review

These are tracked omissions from the approved design, not evidence of full design completion:

- Migration registry: version 1 and future-version rejection exist; registered upgrade migrations do not.
- Style/profile provenance in persisted projects: profile loading retains provenance in memory; manifest-level style/profile/version/brand snapshots remain deferred.
- Overlays/transitions and track composition: no compositor or standalone audio mixing; P0 rejects unsupported layouts. Descriptive segment roles do not implement overlay behavior.
- Configurable export preset registry: CLI derives matching sizes for the four named aspect ratios, but platform preset objects and broader encoding policy are deferred.
- `render --json` remains deferred; Rich dry-run output is human-readable and is not advertised as a machine-readable JSON interface.
- Broader direct primitive tests (time helpers and exception hierarchy) remain a minor coverage follow-up; the final wave covers actual source/output collisions, exclusive publication, and relative/symlink containment.
- Native subtitle burn-in/fonts, optional Whisper inference, and VideoToolbox encoding require capability-equipped execution evidence. Only the hardware selection gate is tested locally here. In-process provider execution bounds remain deferred.
