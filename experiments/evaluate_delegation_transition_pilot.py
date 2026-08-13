#!/usr/bin/env python3
"""Evaluation scaffold; refuses final claims until Phase-1 quality gates pass."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RESULTS=ROOT/'results/delegation_transition_pilot'
def main():
 status=json.loads((RESULTS/'status.json').read_text());coverage=status.get('mapper_coverage')
 if status.get('real_trajectories',0)<10 or coverage is None or coverage<.9:raise SystemExit('GROUND_TRUTH_OR_MAPPER_INSUFFICIENT: Phase-1 real trajectories/coverage gate incomplete')
 raise SystemExit('Phase-1 only: final detector claims are prohibited')
if __name__=='__main__':main()
