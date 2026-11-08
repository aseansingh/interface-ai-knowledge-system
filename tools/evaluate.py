"""Run the supplied, unmodified scorer from a separately unpacked participant kit."""
import argparse
import subprocess
import sys
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--kit',required=True,type=Path,help='Unpacked participant kit folder')
p.add_argument('--out',type=Path,default=Path('results'))
a=p.parse_args()
kit=a.kit.resolve()
root=Path(__file__).resolve().parents[1]
if not (kit/'harness/run_eval.py').is_file():p.error('Expected KIT/harness/run_eval.py')
subprocess.run([sys.executable,str(kit/'harness/run_eval.py'),'--submission',str(root/'submission'),'--snapshots',str(kit/'snapshots'),'--eval',str(kit/'eval/public_eval.jsonl'),'--out',str(a.out.resolve())],cwd=kit,check=True)
