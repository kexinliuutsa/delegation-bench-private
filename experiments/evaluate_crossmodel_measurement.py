#!/usr/bin/env python3
"""Frozen evaluator skeleton. It refuses access until the controlled sealed-open marker exists."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];RESULTS=ROOT/'results/delegation_bench_crossmodel_v1'
if not (RESULTS/'FRESH_SEALED_OPENED').exists():raise SystemExit('FRESH SEALED FIREWALL: evaluator cannot inspect performance before controlled opening')
raise SystemExit('collection/evaluator opening workflow not invoked in Experiment 81 smoke phase')
