# Project format

`project.json` is `{version:"1", project_id, name, sources, target, analysis}`. A source is `{id, path}`. `target` is `{aspect_ratio:"W:H", resolution:"WIDTHxHEIGHT"}`. Analysis references use `{source_id, path, source_sha256, analysis_config_fingerprint, tool_fingerprint}`; all fingerprints are lowercase SHA-256 values and permit cache reuse only together. Legacy `cache_key` is accepted only without modern fingerprints and is not reusable.

`timeline.json` is `{version:"1", tracks, captions, removed}`. A track has `id`, `kind`, and `segments`. A segment requires `source_id` and `source_end`; optional fields are `source_start`, `timeline_start`, `role` (`primary`, `b_roll`, `cutaway`, `overlay`, `voiceover`), `transform` (`crop_x`, `crop_y`, `zoom_scale >= 1`), `audio` (`gain_db` -60..24, `target_lufs` -70..0, fade fields), and evidence. Captions use `start`, `end`, and `text`.

All timestamps are finite non-negative numbers. Source end must not precede source start. On render, source IDs must exist, source ends must be within verified durations, same-track segments may not overlap, and captions must end within assembled duration. See the non-media [talking-head example](../examples/talking-head/).
