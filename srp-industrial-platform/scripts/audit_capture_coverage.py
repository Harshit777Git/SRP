"""Count independent runs and complete cards from preserved capture records."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/generated/fault_training_candidate_3129_each'

def main():
    manifest = json.loads((DATA / 'manifest.json').read_text())
    cards = [json.loads(line) for line in (DATA / 'surface_downhole_cards.jsonl').read_text().splitlines()]
    truth = [json.loads(line) for line in (DATA / 'simulation_truth_labels.jsonl').read_text().splitlines()]
    coverage = {}
    for mechanism in sorted({r['fault_mechanism'] for r in truth}):
        rows = [r for r in truth if r['fault_mechanism'] == mechanism]
        selected = [r for r in cards if r['synthetic_fault_mechanism'] == mechanism]
        ids = {(r['run_id'], r['stroke_id']) for r in selected}
        coverage[mechanism] = dict(
            telemetry_samples=len(rows), independent_runs=len({r['run_id'] for r in rows}),
            virtual_wells=len({r['asset_id'] for r in rows}),
            actual_severities=sorted({r['severity'] for r in rows}),
            distinct_cards=len(ids), duplicate_card_rows=len(selected)-len(ids),
            solved_cards=sum(r['downhole']['status']=='SOLVED' for r in selected))
    output = dict(origin='SYNTHETIC_ONLY', coverage=coverage,
                  explanation='Telemetry rows are not independent labeled strokes. No field validation follows from these counts.')
    path = ROOT / 'reports/PHASE3_2/CAPTURE_COVERAGE_AUDIT.json'
    path.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
