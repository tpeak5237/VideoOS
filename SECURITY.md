# Security and privacy boundaries

VideoOS is a local CLI. Inputs, paths, manifests, timelines and source media are untrusted. Its implemented P0 pipeline uses validated structured contracts and local FFmpeg/ffprobe commands with argument arrays rather than shell interpolation. These controls reduce specific risks; they do not establish a production security guarantee.

Use media you are authorized to process. Files and local analysis/transcripts may contain sensitive information; manage them under your own access, retention and backup policy. Generated QA and caches are local artifacts, not trusted remote audit records. No P0 upload, publishing or telemetry service is implemented. Optional transcription can require separately downloaded model assets and is an explicit capability with its own dependencies and terms.

Keep FFmpeg, Python and installed packages maintained. Inspect the actual FFmpeg build and redistribution terms before bundling it. This project does not include an FFmpeg binary. Missing project-level licensing is a separate redistribution blocker; see [license audit](docs/LICENSE_AUDIT.md).

Report concerns through GitHub private vulnerability reporting if enabled, or request a private contact channel without disclosing sensitive files or credentials publicly. There is no promised response SLA. Include a minimal synthetic reproducer, affected version, exact command and expected/observed behavior; never upload private source media for diagnosis.
