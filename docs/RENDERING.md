# Rendering

The P0 renderer is local FFmpeg. It compiles validated structured timelines into argument arrays and never invokes a shell. Outputs must not be the input source; staging and final paths are constrained to the output project directory before atomic publication.

Use `videoos render PROJECT_JSON --dry-run` after structured edits, then render and run `videoos qa OUTPUT --timeline timeline.json`. A dry run is plan validation, not a media render. Missing `ffmpeg` blocks actual rendering; missing `ffprobe` blocks source/output verification. Local integration tests exercise installed FFmpeg/ffprobe but do not establish CI or deployed/live behavior.
