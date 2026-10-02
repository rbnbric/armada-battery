# Review response

This revision follows the first public review of Armada Battery.

| Review observation | Revision |
|---|---|
| Build was lengthy because it began with the older IRIS 2026.1 EM image | The default Compose path now starts the lightweight synthetic application; the optional live overlay uses the current `latest-cd` Community Edition image. |
| Container startup took time | The credential-free hosted walkthrough remains immediate, and `docker compose up -d` no longer starts IRIS. |
| Testing required local Python | `docker compose run --rm proof` runs all eight deterministic scenarios inside the application image. The full suite has a containerized test target. |
| Results were not tangible | The portal and README now lead with the measured result: one dispatch, zero automatic retries, eight of eight checks passed, and verified reconciliation from fresh evidence. |
| Video was not convincing | A public follow-up video shows the before/after experience, the new task finding, and its verified receipt while retaining the original demonstration. |
| Traditional portal was useful | The portal layout and operational navigation remain intact. |

The quick path qualifies the synthetic engine. The optional IRIS path remains
read-only by default and keeps live qualification separate.

A follow-up adds a visible synthetic task-history finding to the judge path.
Reviewing it opens the existing guarded run request; a verified receipt resolves
the finding, while a failed or unattributed attempt stays in review. This is one
bounded example, not a claim of general live IRIS health assessment.

[Watch the public follow-up video](https://www.youtube.com/watch?v=GbEMgSDRCZk).
