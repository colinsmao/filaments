"""Persist human visual judgments; validate coverage, never infer visual success.

Run after inspecting the native images. Adding a ledger requirement makes an
old review incomplete until a person/agent explicitly evaluates that criterion.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/scaffold-stars/correction'

DESIGN = {
    'D01': ('pass', 'Explicit graph grown before population; no density input.'),
    'D02': ('pass', 'Frozen graph contains integer cells; population occupies unit cells.'),
    'D03': ('pass', 'Uniform roots and local stochastic growth; no guidance field.'),
    'D04': ('pass', 'Graph NPZ, line buffer and star buffer remain independently inspectable.'),
    'D05': ('pass', 'No predetermined blob pairs, spanning tree or fixed destinations.'),
    'D06': ('fail', 'The historical report used labels such as gentler without explaining the bundled before/after changes in the response, and did not clearly distinguish that trial from the displayed bending-42 candidate. The core reporting rule and README now document this correction; that does not retroactively make the earlier report adequate.'),
    'D07': ('pass', 'Separate experiment; prior generators and user presets preserved.'),
}

# These are explicit assessments of inspected images, not threshold-based scores.
REVIEWS = {
 'rejected-42': {
    'V01': ('fail', 'Dense close-view interior merges into a blob; individual routes are not adequately resolved.'),
    'V02': ('fail', 'Frequent large corners and orthogonal runs dominate visible paths.'),
    'V03': ('partial', 'Forks and short offshoots exist, but crowding hides their hierarchy.'),
    'V04': ('fail', 'Regular bead chains coexist with diffuse crowded areas; the reference has more legible irregular fine strands.'),
    'V05': ('fail', 'Dense patches exist, but their interiors fail the required resolved-curve condition.'),
    'V06': ('fail', 'Some routes connect nearby branches; no convincing hierarchy of thin links between resolved dense patches.'),
    'V07': ('partial', 'Large voids exist; patch interiors are too uniformly thick.'),
    'V08': ('fail', 'Bush-like accumulations have abrupt transitions and insufficient variation in internal structure.'),
    'V09': ('partial', 'Oblique view confirms shallow extent with vertical excursions; reference depth distribution is not matched.'),
    'V10': ('fail', 'Multi-candle groups are solid cuboids, missing separate narrow silhouettes and height variation.'),
    'V11': ('partial', '574 rods versus 7336 candles; rods are visible, but close branch readability is poor.'),
    'V12': ('fail', '56 full-block centers in the wide frame versus the user estimate of roughly five.'),
    'V13': ('partial', 'Bright and faint objects and lavender/cream colors exist; excess sources alter local illumination and generated marks appear warmer than the close reference.'),
    'V14': ('partial', 'Short strands attach to scaffold branches, but star gaps create detached-looking bits; not resolved by graph connectivity.'),
    'V15': ('partial', 'Bounds fit the approximate build-size range; apparent object sizes and reference camera remain uncalibrated.'),
    'V16': ('not_evaluated', 'Whole views inspected, but no dedicated endpoint/boundary crop review yet.'),
 },
 'placement-42': {
    'V01': ('fail', 'Narrower placement reveals more marks but preserves crowded unresolved branch groups.'),
    'V02': ('fail', 'Identical graph retains the rejected corners and axis runs.'),
    'V03': ('partial', 'Same forks and length distribution; lower fill makes some short branches hard to trace.'),
    'V04': ('fail', 'Narrower chains remain too regularly aligned; random thinning is not varied coherent curvature.'),
    'V05': ('fail', 'Patches remain but still fail to resolve their fine curves convincingly.'),
    'V06': ('fail', 'No scaffold routes changed; thinning cannot supply missing thin connections.'),
    'V07': ('partial', 'Voids preserved and less filled, but patch-to-corridor contrast is not reference-like.'),
    'V08': ('fail', 'Same bush structure and abrupt transition pattern as rejected graph.'),
    'V09': ('partial', 'Shallow shape and local vertical variation retained in oblique view; no depth match established.'),
    'V10': ('fail', 'Same solid group proxies lack individual candle silhouettes.'),
    'V11': ('partial', '379 rods versus 4753 candles; visible rods retained, but short-star continuity still inconsistent.'),
    'V12': ('partial', 'Six full-block centers in the wide frame fixes the obvious excess on this seed; not yet robust across seeds/views.'),
    'V13': ('partial', 'Fainter neighborhoods after removing sources; palette hierarchy survives, but no calibrated appearance match.'),
    'V14': ('partial', 'No new isolated scaffold components; lower occupancy can make short pieces appear detached.'),
    'V15': ('partial', 'Same physical bounds and cameras; apparent-size calibration still absent.'),
    'V16': ('not_evaluated', 'No dedicated endpoint/boundary crop review yet.'),
 },
 'gentler-42': {
    'V01': ('partial', 'Separate strands are much more readable, but dense regions were removed to obtain this.'),
    'V02': ('fail', 'Fewer hard turns, but mostly straight strings replace the sustained curved paths needed.'),
    'V03': ('fail', 'Too few short offshoots and local branch groups; long sparse strings dominate.'),
    'V04': ('fail', 'Single-file bead rows remain repetitive and overly regular.'),
    'V05': ('fail', 'Dense areas largely disappear. This regresses an older explicit requirement.'),
    'V06': ('fail', 'Long strands exist, but not as narrow links between adequately dense patches.'),
    'V07': ('fail', 'Dark space exists, but weak density variation makes a sparse web instead of patch/corridor/void hierarchy.'),
    'V08': ('fail', 'No convincing range of patch sizes or transitions because patches are too weak.'),
    'V09': ('partial', 'Shallow domain and local height variation retained; visual depth distribution is not matched.'),
    'V10': ('fail', 'Cuboid candle-group silhouettes unchanged.'),
    'V11': ('partial', '250 rods versus 3261 candles; rods visible but cannot compensate for missing short candle strands.'),
    'V12': ('fail', 'Zero full blocks on this seed; removed the occasional accents rather than balancing them.'),
    'V13': ('partial', 'Cream/lavender hierarchy retained; missing full-block sources changes illumination and sparse scene remains unlike reference.'),
    'V14': ('partial', 'Many sparse endpoints and disconnected-looking chains; no systematic crop-level isolation review yet.'),
    'V15': ('partial', 'Actual graph bounds 255 x 54 x 274 blocks fit the estimate; camera/apparent sizes remain uncalibrated.'),
    'V16': ('not_evaluated', 'No dedicated endpoint/boundary crop review yet.'),
 },
}

# Inherited entries describe inspected unchanged failures, not assumed passes.
REVIEWS['independent-42'] = dict(REVIEWS['placement-42'], **{
    'V01': ('fail', 'More single strands are visible, but dense interior groups still crowd together.'),
    'V02': ('fail', 'Lower independent turn angles reduce hard corners but leave straight bead strings and occasional sharp forks.'),
    'V03': ('partial', 'Dense branching and short offshoots retained; branch groups are not adequately resolved.'),
    'V11': ('partial', '405 rods and 4758 candles; rods remain visible, but group silhouettes and crowding still impair strands.'),
    'V12': ('partial', 'Two full blocks in wide frame; excess removed but no multi-seed balance demonstrated.'),
    'V15': ('partial', 'Recorded bounds and fixed cameras; revised close_scale55 uses two reference cubes, not complete camera calibration.'),
})
REVIEWS['bending-42'] = dict(REVIEWS['independent-42'], **{
    'V01': ('fail', 'Some separate curved strands are easier to trace; busy groups still fail the close-reference arrangement.'),
    'V02': ('partial', 'Several broader bends replace independent wandering. Straight bead rows and hard branch departures remain.'),
    'V04': ('fail', 'Turn continuation does not remove regular bead spacing or monotonous solid group marks.'),
    'V05': ('fail', 'Dense patches retained, but not as sufficiently resolved fine curves.'),
    'V06': ('fail', 'Visible local links exist; dense-knot/thin-bridge hierarchy still weak.'),
    'V08': ('fail', 'Bending changes patch outlines; does not sufficiently vary internal structure or transitions.'),
    'V11': ('partial', '390 rods and 4676 candles; mixed short branches retained, but no reference-like material distribution established.'),
})
REVIEWS['bending-long-42'] = dict(REVIEWS['bending-42'], **{
    'V01': ('fail', 'Close view still contains crowded branch groups mixed with regular rows.'),
    'V03': ('partial', 'Longer reach and short branches present; local branch hierarchy remains unlike the reference.'),
    'V06': ('partial', 'More longer apparent links in wide view; they still do not join reference-like resolved dense patches.'),
    'V08': ('fail', 'Longer reach still changes local branch scale; patch transitions are not convincingly reproduced.'),
    'V11': ('partial', '455 rods and 5156 candles; visible material hierarchy, unresolved strand distribution.'),
    'V12': ('partial', 'Three full-block centers in wide frame, four overall; rare accents only checked on this seed.'),
})
REVIEWS['continuous-42'] = dict(REVIEWS['bending-42'], **{
    'V01': ('fail', 'Long trunks with capped children still form dense unresolved clumps.'),
    'V02': ('partial', 'Broad bends exist, but straight runs and hard fork departures remain prominent.'),
    'V03': ('partial', 'Plenty of branches and short paths, but their overlap hides coherent organization.'),
    'V05': ('fail', 'Dense regions merge many fine strands into a blob.'),
    'V06': ('fail', 'Two graph components is not success: wide view is dominated by one clump rather than a resolved patch/bridge network.'),
    'V07': ('fail', 'Large empty areas surround a disproportionately concentrated cloud; internal voids are weak.'),
    'V08': ('fail', 'Large main accumulation and separate smaller bush; weak hierarchy within patches.'),
    'V11': ('partial', '658 rods and 8534 candles; rods remain visible but cannot resolve geometry.'),
    'V12': ('partial', 'Two full blocks in wide frame; count excess fixed, scene still fails.'),
})
REVIEWS['periods-42'] = dict(REVIEWS['continuous-42'], **{
    'V01': ('fail', 'Active/quiet periods retain crowded clumps at original and revised close camera.'),
    'V03': ('fail', 'Children restarting active produces locally excessive descendant branching; hierarchy remains unreadable.'),
    'V05': ('fail', 'Dense areas present but remain unresolved accumulations.'),
    'V06': ('fail', 'Some thin peripheral paths appear; central clumps still prevent the desired patch/bridge arrangement.'),
    'V07': ('fail', 'Large voids and concentrated masses persist; local periods do not fix their balance.'),
    'V08': ('fail', 'Period variation does not prevent descendant cascades in the same region.'),
    'V11': ('partial', '643 rods and 7566 candles; material counts alone do not match their arrangement.'),
    'V12': ('partial', 'Five full blocks in wide frame, but matching this one count is not a full visual match or a robust material test.'),
})
REVIEWS['periods-short-42'] = dict(REVIEWS['periods-42'], **{
    'V01': ('fail', 'Shortening quiet spans still leaves crowded regions in close view.'),
    'V05': ('fail', 'More frequent active branching does not produce resolved dense curves.'),
    'V08': ('fail', 'The same concentration/descendant-cascade failure persists with shorter quiet periods.'),
    'V11': ('partial', '682 rods and 8029 candles; visible rods, but repeated group marks and crowded paths remain.'),
    'V12': ('partial', 'Four full blocks in wide frame; no multi-seed balance demonstrated.'),
})


def save_review(name, visual, summary):
    ledger_path = ROOT / 'reference-match-requirements.json'
    ledger = json.loads(ledger_path.read_text())
    required = {r['id'] for group in ('design_requirements', 'visual_requirements') for r in ledger[group]}
    judgments = dict(DESIGN, **visual)
    metrics = json.loads((OUT / f'{name}-metrics.json').read_text())
    bounds = [int(v)+1 for v in metrics['scaffold']['bounds']]
    judgments['V15'] = ('partial', f'Scaffold occupied-cell footprint spans {bounds} blocks (coordinate spans plus one). '
                        'All candidates also use the revised distance55 close camera, based on two reference cube sizes. '
                        'Broader apparent-size/depth distribution and reference camera remain uncalibrated; no physical density match established.')
    if set(judgments) != required:
        raise ValueError(f'{name}: missing {required-set(judgments)}; unexpected {set(judgments)-required}')
    evidence = [f'{name}-{view}.png' for view in ('close_match', 'wide_match', 'whole', 'oblique')]
    evidence.append(f'{name}-close_scale55.png')
    evidence += [f'{name}-request.json', f'{name}-metrics.json', f'{name}-diagnostics.json', f'{name}-graph.npz']
    hashes = {p: hashlib.sha256((OUT / p).read_bytes()).hexdigest() for p in evidence}
    checks = {}
    for rid, (status, reason) in judgments.items():
        if status not in ('pass', 'partial', 'fail', 'not_evaluated') or not reason.strip():
            raise ValueError(f'{rid}: invalid review')
        checks[rid] = dict(status=status, reason=reason,
                          evidence=evidence[:5] if rid.startswith('V') else evidence[5:])
    report = dict(candidate=name, verdict='rejected; not a screenshot match', summary=summary,
                  assessment_type='explicit visual review plus code/geometry evidence; not an automated similarity metric',
                  requirements_version=ledger['version'], requirements_sha256=hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
                  checks=checks, evidence_sha256=hashes, new_findings=ledger['review_findings'])
    report['evidence_base'] = str(OUT.relative_to(ROOT)).replace('\\', '/')
    (OUT / f'{name}-review.json').write_text(json.dumps(report, indent=2))
    return report


def main():
    if '--check' in sys.argv[1:]:
        ledger = json.loads((ROOT / 'reference-match-requirements.json').read_text())
        expected = {r['id'] for group in ('design_requirements', 'visual_requirements') for r in ledger[group]}
        reports = json.loads((ROOT / 'reference-match-review.json').read_text())['candidates']
        for report in reports:
            if set(report['checks']) != expected:
                raise ValueError(f"Incomplete requirement coverage: {report['candidate']}")
            if report['requirements_sha256'] != hashlib.sha256((ROOT / 'reference-match-requirements.json').read_bytes()).hexdigest():
                raise ValueError(f"Stale requirements: {report['candidate']}")
            for path, digest in report['evidence_sha256'].items():
                if hashlib.sha256((OUT / path).read_bytes()).hexdigest() != digest:
                    raise ValueError(f'Changed evidence: {path}')
        requests = {p.name.removesuffix('-request.json') for p in OUT.glob('*-request.json')}
        if requests != {r['candidate'] for r in reports}:
            raise ValueError('Candidate inventory differs from reviewed candidates')
        print(f'{len(reports)} candidates: all {len(expected)} requirements present; ledger and evidence hashes current. Visual success is not implied.')
        return
    summaries = {
        'rejected-42': 'User rejection confirmed: unresolved dense regions, excessive full blocks and hard corners.',
        'placement-42': 'Material/count correction only; geometric failures remain.',
        'gentler-42': 'Rejected regression: clearer strands at the cost of dense regions, branching and curved shape.',
        'independent-42': 'Lower turn angle alone retains straight strings and crowded branch groups.',
        'bending-42': 'Some broader bends, but regular rows and unresolved branch groups remain.',
        'bending-long-42': 'Longer apparent connections, still insufficiently resolved dense regions and weak transitions.',
        'continuous-42': 'Long reach and child lifetime cap still produce concentrated clumps.',
        'periods-42': 'Five full blocks does not rescue crowded clumps; children restart active and proliferate locally.',
        'periods-short-42': 'Shorter quiet periods do not fix the clump failure.',
    }
    results = []
    for name, review in REVIEWS.items():
        result = save_review(name, review, summaries[name])
        results.append(result)
        print(name, len(result['checks']), 'requirements explicitly reviewed')
    references = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((ROOT / 'scar').glob('*2026-10-10*.png'))}
    (ROOT / 'reference-match-review.json').write_text(json.dumps(dict(date='2026-10-14',
        verdict='No candidate is a screenshot match; none promoted.',
        references_sha256=references,
        reference_review='All21 inventoried in three contact sheets; primary close/wide plus23h46m31 inspected at larger resolution. Contact sheets are overview evidence, not detailed inspection of every object.',
        explicit_remaining_review_gaps=['Endpoint/boundary crops', 'Multi-seed validation of new growth and rare-block settings', 'Broader apparent-size and depth calibration'],
        candidates=results), indent=2))
    path = ROOT / 'build/scaffold-stars/assessment.json'
    old = json.loads(path.read_text())
    old['superseded_by_user_rejection'] = dict(date='2026-10-14', verdict='rejected, not a match',
        requirements='../../reference-match-requirements.json',
        review='correction/rejected-42-review.json',
        reason=summaries['rejected-42'])
    path.write_text(json.dumps(old, indent=2))


if __name__ == '__main__':
    main()
