#!/usr/bin/env python3
"""Evaluate frozen rule/LLM/hybrid predictions only after human gold exists."""
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_v1/resistance';R=ROOT/'results/delegation_bench_v1/resistance_judge_validation'
def main():
 required=[B/'human_gold_labels.csv',R/'llm_vs_human.csv',R/'judge_stability.json']
 if not all(p.exists() for p in required):raise SystemExit('WAITING_FOR_HUMAN_ANNOTATIONS_OR_JUDGE_OUTPUTS')
 raise SystemExit('Inputs present; run the frozen evaluator implementation only under the separately authorized judge-validation stage.')
if __name__=='__main__':main()
