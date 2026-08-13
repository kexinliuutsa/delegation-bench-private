#!/usr/bin/env python3
"""Summarize exposure, uptake, and drift without inflating accuracy claims."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();base=root/'results/authority_source_collection';p.add_argument('--audit',type=Path,default=base/'audit.json');p.add_argument('--labels',type=Path,default=root/'results/authority_source_labels.csv');p.add_argument('--output',type=Path,default=base/'pilot_summary.json');a=p.parse_args();audit=json.loads(a.audit.read_text());rows=list(csv.DictReader(a.labels.open())) if a.labels.exists() else [];counts=Counter(x['source_label'] for x in rows);treatment=[x for x in rows if x['condition']=='treatment'];pairs={x['pair_id'] for x in treatment};drift_pairs={x['pair_id'] for x in treatment if x['source_label']=='ENVIRONMENT'};uptake_pairs={x['pair_id'] for x in treatment if x['source_label'] in {'ENVIRONMENT','MIXED'}};exposed={x['pair_id'] for x in audit['pair_audits'] if x['D_injection_observed']};summary={'number_of_pairs':audit['pairs'],'number_of_drift_events':counts['ENVIRONMENT'],'UNKNOWN':counts['UNKNOWN'],'ENVIRONMENT':counts['ENVIRONMENT'],'MIXED':counts['MIXED'],'USER':counts['USER'],'exposure_rate':len(exposed)/audit['pairs'] if audit['pairs'] else 0,'uptake_rate_given_exposure':len(uptake_pairs&exposed)/len(exposed) if exposed else 0,'drift_rate':len(drift_pairs)/audit['pairs'] if audit['pairs'] else 0,'accuracy_reported':False if audit['pairs']<10 else 'see authority_source_evaluation.csv'};a.output.write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
