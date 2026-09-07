# Synthetic integration media

Integration tests generate their own four-second `640x360` H.264/AAC MP4 at
runtime with local FFmpeg. Its audio is one second of silence, two seconds of a
440 Hz sine tone, then one second of silence. The generated media is never
stored in Git and is created only through an argv-array subprocess invocation
with `shell=False`.

The suite skips explicitly when either `ffmpeg` or `ffprobe` is unavailable.
