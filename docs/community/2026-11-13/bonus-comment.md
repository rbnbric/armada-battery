Hi Tatiana and team — Armada Battery now has source and native test evidence for three additional bonuses:

- **Custom Adapter (2):** a native `Ens.OutboundAdapter` performs the production's authenticated evidence reads. [Implementation and qualification](https://github.com/rbnbric/armada-battery/blob/main/docs/BONUS_IMPLEMENTATION.md).
- **Embedded Python (3):** the evidence operation calls a Python validator inside IRIS to check response structure, JSON types, receipt scope and duplicate keys. The same qualification includes its individual test results.
- **Community Idea DPI-I-689 (4):** native Visual Trace records the reviewer, investigator, evidence reads and follow-up review, including saved inputs, answers and usage counters. [Reproducible example and idea mapping](https://github.com/rbnbric/armada-battery/blob/main/docs/TRACEABILITY.md). The idea is linked in the repository README.

Could you also confirm the currently offered EAP image is accepted? The download portal offers `iris-community-2027.1.0AI.109.0-docker.tar.gz`, and our tests identify that exact runtime. The contest announcement still names `2026.3.0AI.154.0`.

The first article and video already show as awarded in the results table. Thank you for reviewing the additional evidence.
