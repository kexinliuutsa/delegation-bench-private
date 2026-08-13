#!/usr/bin/env python3
"""Frozen evaluation entry point; refuses analysis until QC and information gates pass."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results/delegation_transition_replication_v21'
def main():
 files=list((R/'raw').glob('*.json'))
 if len(files)<160:raise SystemExit('INSUFFICIENT_TRANSITION_OPPORTUNITY: full maximum cohort incomplete; run QC/opportunity gate first')
 raise SystemExit('Evaluation implementation is frozen to required endpoints but must be activated only after blinded human mapping audit and QC gate.')
if __name__=='__main__':main()
