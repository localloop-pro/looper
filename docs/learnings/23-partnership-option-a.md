# #23 — A "no" from the owner is still a decision to record (2026-10-05)

Option A means Looper writes no code: HybridCard stops sending partnership
events, and the existing 422 guard keeps pinning that a signed partnership
payload writes nothing. The work on Looper's side is to make every document
say the same thing (the decision file, the cross-repo contract table, STATUS)
so that no later agent reads "awaiting decision" and builds a receiver or
replays dead letters. Keep the guard test even after HybridCard stops: it is
the cheap proof that a stray event still cannot write.
