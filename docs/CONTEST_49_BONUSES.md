# Armada Battery: contest 49 bonus evidence

Checked 13 November 2026 against the [bonus requirements](https://community.intersystems.com/post/technology-bonuses-intersystems-programming-contest-ai-agents-interoperability-workflows)
and [current results](https://community.intersystems.com/post/technology-bonus-results-intersystems-programming-contest-ai-agents-interoperability-workflows).
The published table awards Battery **5 points: first article (2) and video (3)**.
The work below supports additional claims; those points have not been awarded.

## What changed

- A native `Ens.OutboundAdapter` now performs the authenticated management evidence reads.
- An Embedded Python method inside IRIS validates each response against its saved receipt contract.
- Each probe and review now has its own saved message body. A fresh Visual Trace example and persistence checks cover the earlier request-reuse defect.
- The README links Community Idea DPI-I-689, with a reproducible trace guide.
- A second article is ready for publication. It describes the new trace defect, fix and evidence validation.

Source, native test results and reproduction commands are in
[Bonus implementation](BONUS_IMPLEMENTATION.md) and [Traceability](TRACEABILITY.md).

## All fifteen categories

| Category | Points | Current evidence and remaining step |
| --- | ---: | --- |
| Questionnaire | 1 | Submission not confirmed. Robin completes the [official questionnaire](https://forms.cloud.microsoft/r/upQDKbj78D) using his actual experience. |
| Production Extension (PEX) | 3 | Not implemented. Requires a useful Java/.NET PEX component running in the production. |
| Workflow Engine | 2 | Not implemented. Battery's custom case lifecycle does not establish IRIS Workflow Engine usage. |
| Custom Adapter | 2 | Implemented: [EvidenceAdapter](../interop/Battery/Interop/EvidenceAdapter.cls), attached to the evidence operation, qualified through real HTTP and native queued messages. Submit evidence for review. |
| Find a bug in AI Hub | up to 3 | No qualifying vendor report. The request-reuse defect fixed here belongs to Battery. |
| Embedded Python | 3 | Implemented: [EvidenceEnvelope](../interop/Battery/Interop/EvidenceEnvelope.cls), called inside IRIS by the evidence operation. Submit native qualification evidence. |
| IRIS Vector Search | 2 | Not implemented. No vector-query claim. |
| Docker | 2 | Present, but previously rewarded in the [management-portal contest](https://community.intersystems.com/post/technology-bonus-results-intersystems-programming-contest-build-your-own-management-portal). The current table marks it “-”; do not request it again. |
| ZPM package deployment | 2 | Not implemented. Requires a package, registry publication and a verified installation; Compose alone is insufficient. |
| Online Demo | 2 | Previously rewarded in the management-portal contest. The current public walkthrough uses synthetic records; no new native online-demo claim. |
| Community Idea | 4 | [DPI-I-689](https://ideas.intersystems.com/ideas/DPI-I-689): native model/evidence traceability. README mapping and [reproducible example](TRACEABILITY.md) supplied. Robin still needs to add the idea URL to the dedicated Open Exchange Ideas field. |
| Find a bug in Embedded Python | up to 3 | No qualifying vendor report. Application validation cases are not vendor bugs. |
| First article | 2 | Awarded: [An AI agent can be wrong and still be useful](https://community.intersystems.com/post/ai-agent-can-be-wrong-and-still-be-useful). |
| Second article | 1 | [New article draft](community/2026-11-13/article.md) prepared. Publish on Developer Community, add its link to the listing, then notify the results thread. |
| Video | 3 | Awarded. [Current 3:55 walkthrough](https://rbnbric.github.io/armada-battery/video/) and [direct MP4](https://github.com/rbnbric/armada-battery/releases/download/media-2026-11-11-v3/armada-battery-current-v3.mp4) are public. |

The adapter, Embedded Python and idea claims total **9 possible additional points**.
The questionnaire and published second article could add another **2**. That would
be 16 including the current 5, if all those claims are accepted. It is not the
current awarded score.

## Version question

The [contest announcement](https://community.intersystems.com/post/intersystems-programming-contest-ai-agents-interoperability-workflows)
names `2026.3.0AI.154.0`. The participant's EAP download page on 13 November
offers `iris-community-2027.1.0AI.109.0-docker.tar.gz`. That is the build used for
the native qualification. No build 154 qualification is claimed. Ask the
organizers to confirm the currently offered image is accepted.

## Next publication steps

1. Add `https://ideas.intersystems.com/ideas/DPI-I-689` to the Open Exchange **Ideas Portal link** field.
2. Publish the [second article](community/2026-11-13/article.md), then add its public link to the listing.
3. Complete or confirm the questionnaire.
4. Post the [short evidence update](community/2026-11-13/bonus-comment.md) on the **current results article**, where the organizers requested updates. Add the new article link after publication.

The article and comment are drafts. They have not been submitted on Robin's behalf.
