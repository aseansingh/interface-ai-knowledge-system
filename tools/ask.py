"""Inspect an answer or conflict report using a local participant kit."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--kit', required=True, type=Path)
parser.add_argument('--question')
parser.add_argument('--as-of')
parser.add_argument('--conflicts', action='store_true')
args = parser.parse_args()
kit = args.kit.resolve()
if not (kit / 'harness/run_eval.py').is_file():
    parser.error('Expected KIT/harness/run_eval.py')
if not args.question and not args.conflicts:
    parser.error('Supply --question or --conflicts')
sys.path.insert(0, str(kit / 'harness'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'submission'))
from run_eval import load_snapshots
from solution import build

system = build()
for snapshot in load_snapshots(kit / 'snapshots'):
    system.ingest(snapshot)
result = ([asdict(c) for c in system.conflicts()] if args.conflicts else
          asdict(system.answer(args.question, as_of=args.as_of)))
print(json.dumps(result, indent=2, ensure_ascii=False))
