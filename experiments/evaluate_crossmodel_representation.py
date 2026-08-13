#!/usr/bin/env python3
"""Frozen representation evaluator entry point; sealed firewall is mandatory."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RESULTS=ROOT/'results/delegation_bench_crossmodel_v1'
if not (RESULTS/'FRESH_SEALED_OPENED').exists():raise SystemExit('FRESH SEALED FIREWALL: representation evaluation prohibited')
raise SystemExit('collection/evaluator opening workflow not invoked in Experiment 81 smoke phase')
