# Public heldout v2 interrupted process observation

## Verified stop, not an observation timeout

The [explicitly approved trial](2026-10-02-public-heldout-transport-v2-approved.md)
started under the four-CPU/two-GiB 9,000-second Windows process-tree fence.
The retained last progress reported eleven new calls. At 15:29 UTC, both
recorded supervisor/worker handles were absent; an authoritative Win32 process
inventory also found no interpreter running either exact v2 script. There
is no caller result, supervisor-complete or launcher-failure receipt. System
boot preceded this trial; no reboot/shutdown event ID was found in the narrow
interval. The cause of interruption is **unknown**, not attributed to quota,
model quality or a machine restart. Nothing was restarted or replayed.

## Immutable receipt reconciliation

Read-only admission rechecked the approval, all frozen public inputs, current
code hashes, previous failed trial and checkpoint binding. All **eleven new
physical claims have matching receipts**, with no additional in-flight claim
without a receipt. Each request/receipt/claim hash, ID/verdict, usage and
30-second minimum start spacing was validated; old records remain intact.
The separate ignored aggregate observation SHA is
`59f6147432ad4f562cb73f4faaf317fa3e9de44d92f15cac104d4f5324c95615`.
It does not replace or fabricate the absent caller result.

- Nine new valid replies; Q013/Q014 returned HTTP503.
- Three inherited valid replies plus eleven new outcomes = **14/60 evaluated**.
- All **19 displayed cards are useful** in this partial sample; 8 positive
  hits and 4 conclusive empty controls. **46 questions remain unattempted**.
- Complete gates are not passed. At best all remaining requests succeeding
  could reach 58/60 valid responses; either another failure or insufficient
  hit/no-match/usefulness would prevent a pass.
- New reported usage 61,580 input / 15,813 output tokens; known guard
  **USD0.058010**, with both HTTP503 charges unknown. Including calibration
  and earlier known heldout spend gives **USD0.490610**, plus all historical
  unknown charges. This is usage-times-guard, not a billing receipt.
- Six historical physical requests plus eleven new = **17 observed physical
  requests**. No same-question automatic retry or weak padding was performed.

The valid new replies, failed replies, claims and ledger remain unchanged.
The one-use caller cannot resume itself. Any subsequent provider attempt
needs a new exact approval and a concrete checkpoint/stop design; generic
continuation does not authorize extra calls. Keep all sixty questions, both
new service failures and original failed-trial history in any later report.
Ask/source judging remain disabled; no private data/DB write/enablement or
Lane 6 closure is claimed. Lane 6 remains **3/7**, goal active.
