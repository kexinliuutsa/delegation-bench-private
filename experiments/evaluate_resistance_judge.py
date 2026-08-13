#!/usr/bin/env python3
"""Gatekeeper/evaluator scaffold. It never calls a judge without human agreement and gold."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_v1/resistance';R=ROOT/'results/delegation_bench_v1/resistance_judge_validation'
def main():
 h=R/'human_agreement.json';gold=B/'human_gold_labels.csv'
 if not h.exists():raise SystemExit('WAITING_FOR_HUMAN_ANNOTATIONS')
 if json.loads(h.read_text())['cohen_kappa']<.7:raise SystemExit('TAXONOMY_NOT_RELIABLE_ENOUGH')
 if not gold.exists():raise SystemExit('WAITING_FOR_HUMAN_ADJUDICATION')
 raise SystemExit('Judge execution requires explicit later authorization; no model call made by this validation-package build.')
if __name__=='__main__':main()
