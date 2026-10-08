# Maintenance decisions

## Verify the actual local media boundary

CI provisions Python 3.12, uv, FFmpeg/ffprobe and local fonts, then runs unit/CLI and real media integration tests. Tests must exercise the installed wheel as well as source imports so packaged profiles and the command entrypoint cannot be accidentally omitted. Installing dependencies through uv supplies the cache for the existing offline wheel installation test.

## Lock verification dependencies

A universal, hashed `requirements-dev.lock` pins the base runtime, tests and package-build toolchain. CI syncs this lock, installs the local project without resolving dependencies or creating a separate build environment, and builds with the locked setuptools. Optional providers remain explicitly outside the lock. The review raises pytest to 9.0.3 or newer within major 9 because the previously allowed 8.4.2 had PYSEC-2026-1845; all existing tests are rerun on that runner.

## Keep the pipeline local and non-destructive

This maintenance branch preserves existing source, manifest, timeline, renderer and QA behavior. It does not add providers, cloud storage, uploads, publishing or a compositor. P0 still supports the documented continuous single-video-track workflow and rejects unsupported layouts.

## Make development artifacts explicit

The Git ignore file excludes local virtual environments, caches, generated media, analysis, QA and package build output. Synthetic fixtures remain generated in temporary test directories. Ignore rules supplement review; they do not remove already tracked files.

## Preserve the licensing limitation

No project-level license was present in the public baseline. This branch does not invent one or imply legally open-source reuse rights. Dependency attribution and actual FFmpeg binary obligations are separate from ownership of VideoOS and source-media rights.

## Separate tests from release proof

A successful local suite describes the interpreter and installed tools used for that run. GitHub CI results, publishing a branch/PR, installing a package elsewhere and verifying optional hardware/provider capabilities require separate evidence. Packaging is a local build, not publication to a package registry.
