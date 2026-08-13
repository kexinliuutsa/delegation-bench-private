#!/usr/bin/env python3
"""Create the immutable Experiment-81.10 opening marker before the first model call."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'benchmarks/delegation_bench_crossmodel_v13/fresh_sealed_v13';R=ROOT/'results/delegation_bench_crossmodel_v13/fresh_sealed'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 hashes=json.load(open(D/'FROZEN_PROTOCOL_SHA256.json'))
 assert all(sha(D/k)==v for k,v in hashes.items())
 marker=R/'FRESH_SEALED_OPENED';R.mkdir(parents=True,exist_ok=True)
 if marker.exists():print(marker.read_text());return
 marker.write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'protocol_SHA256':sha(D/'FROZEN_PROTOCOL.md'),'protocol_hash_manifest_SHA256':sha(D/'FROZEN_PROTOCOL_SHA256.json'),'manifest_SHA256':sha(D/'collection_manifest.json'),'model_identifiers':['gpt-5','gpt-4.1'],'statement':'Fresh-sealed collection has begun. Protocol, methods, thresholds, success criteria, timing, allocation, and representation configurations are now immutable.'},indent=2)+'\n');print(marker.read_text())
if __name__=='__main__':main()
