# Rendering

The P0 renderer is local FFmpeg. It compiles validated structured timelines into argument arrays and never invokes a shell. Default outputs stay in the project `renders/` directory. An explicit `render --output PATH` may select a location outside the project: explicit `--output` paths use their own validated parent directory and are not constrained to the project directory. In either case, the output must not be an input source, an existing destination is rejected, and staging plus atomic publication are constrained to that selected destination parent.

Use `videoos render PROJECT_JSON --dry-run` after structured edits, then render and run `videoos qa OUTPUT --timeline timeline.json`. A dry run is plan validation, not a media render. Missing `ffmpeg` blocks actual rendering; missing `ffprobe` blocks source/output verification. Local integration tests exercise installed FFmpeg/ffprobe but do not establish CI or deployed/live behavior.
