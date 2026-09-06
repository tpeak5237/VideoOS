# Editing profiles

Built-ins are `generic`, `podcast`, `talking-head-shortform`, `talking-head-longform`, and `vlog`. A profile controls silence removal, caption line length, subject-tracking policy, zoom interval/scale, audio LUFS targets, and carries local provenance. Supply a built-in slug or a `.yaml`, `.yml`, or `.json` profile path; unknown keys are rejected.

P0 planning applies supported policies deterministically. `subject_tracking: true` is policy intent, not a claim that a vision tracking provider is installed; check `videoos doctor` and inspect generated timeline evidence.
