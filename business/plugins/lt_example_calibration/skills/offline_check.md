---
name: lt_example_offline_check
description: Non-confidential guidance for the LT example offline calibration plugin.
plugin_id: lt.example.offline_check
triggers: [offline, calibration, LT-C, LT-R]
max_context_chars: 2000
---

# LT Example Offline Check

Use this guidance only when the LT example offline calibration plugin is selected.

Check whether the uploaded logs represent offline setup activity. Prefer a prepare step before analysis when the data has not been normalized in the current case. Summarize any result as auxiliary engineering evidence, not as a final disposition.

The final answer should mention that this is a non-confidential example analysis and that real LT calibration logic should replace the example service before production use.
