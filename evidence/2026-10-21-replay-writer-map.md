# Static replay-writer mapping

2026-10-21, root / writer_map. Read-only investigation of the supplied 13.0.5 generated source and current runtime; no writer-watch experiment was performed. Private generated source and raw traces remain under ignored local storage. This is source evidence, not a gameplay ownership verdict.

Exact stores, without inferring ownership from neighboring symbols:

- `main+593b470`: guest PC `710374a254` stores the result of GetSystemTick called at `710374a234` in `f_7103747810`. Import 1270 resolves to GetSystemTick. `runtime/nnsdk.c` supplies real QPC time for this caller, outside its narrow deterministic seed handling.
- `main+529b844` and `main+529b848`: producer and consumer indices for a four-entry callback queue. Producer `f_710398bc70` stores at `710398bcd0` and signals an event; consumer `f_710398b8a0` stores at `710398b970` after invoking a callback. Initialization installs an empty callback, but later callback replacement has not been ruled out.
- `main+6dd52e8`: exact store at `7103963850` in `f_71039635c0`, following a floating-point comparison.
- `main+5298aa0`: exact store at `71039648ac` in that same function.
- `main+529b928` and `main+6df5038` remain unmapped. The nearby store to `529b924` is not evidence for `529b928`.

These findings support investigating real-clock and asynchronous execution after the restore checkpoints. They do not establish that the differing state is harmless, prove which writer executed in the recorded trial, or justify excluding any page.

Next bounded experiment: trace writes after the post-continuation checkpoint to `529b844`, `529b848`, `6dd52e8` and `593b470`, recording rollback phase, thread and instruction attribution. Existing `debug_watch` configures four-byte watches despite reading eight-byte values; a watch at `529b840` misses the producer counter at `529b844`. It covers existing threads only and caps output at 160 events. Retain an uninstrumented control because watch installation and logging affect scheduling. Implement explicit phase attribution before using this facility as replay evidence.
