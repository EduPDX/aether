"""Aether sync client library (protocol v1).

The same logic the launcher implements: fetch a signed manifest, verify
the Ed25519 signature, diff against a local directory and apply the plan
(download changed/missing files, retire files no longer in the manifest).
"""

from aether_sync.protocol import SyncPlan, build_plan, verify_manifest

__all__ = ["SyncPlan", "build_plan", "verify_manifest"]
