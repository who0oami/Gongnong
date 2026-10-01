"""Create a self-contained local comparison page and provenance summary."""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    items=json.loads((ROOT/'inputs.json').read_text(encoding='utf-8'))
    entries=[]
    for item in items:
        assert sha(Path(item['video']))==item['sha256'], 'Original video changed'
        folder=ROOT/'runs'/item['word_id']
        report=json.loads((folder/'result_v4.json').read_text())
        entries.append({**item,'source':os.path.relpath(item['video'],ROOT).replace('\\','/'),
                        'preview':f"runs/{item['word_id']}/preview_v4/",'report':report,
                        'files':{k:f"runs/{item['word_id']}/{v}" for k,v in report['output_files'].items()}})
    summary={'clips':len(entries),'total_frames':sum(e['report']['frames'] for e in entries),'source_video_hashes_unchanged':True,
             'sources':json.loads((ROOT/'sources.json').read_text()),
             'mean_per_clip_direction_error_deg':{v:sum(e['report']['metrics'][v]['mean_source_segment_error_deg'] for e in entries)/len(entries) for v in ('baseline','knn','knn_jihyeon')},
             'max_final_frame_rotation_deg':max(e['report']['metrics']['knn_jihyeon']['max_frame_rotation_change_deg'] for e in entries),
             'source_consistency_improved_vs_knn':sum(e['report']['metrics']['knn_jihyeon']['mean_source_segment_error_deg']<e['report']['metrics']['knn']['mean_source_segment_error_deg'] for e in entries),
             'source_consistency_improved_vs_baseline':sum(e['report']['metrics']['knn_jihyeon']['mean_source_segment_error_deg']<e['report']['metrics']['baseline']['mean_source_segment_error_deg'] for e in entries),
             'prior_sha256':sha(ROOT.parents[1]/'extractor/hand_shape_prior.npz'),
             'avatar_sha256':sha(Path(json.loads((ROOT/'profile.json').read_text())['model_file'])),
             'profile_sha256':sha(ROOT/'profile.json')}
    html=(ROOT/'review_template.html').read_text(encoding='utf-8').replace('__DATA__',json.dumps(entries,ensure_ascii=False).replace('<','\\u003c'))
    with (ROOT/'index.html').open('x',encoding='utf-8') as f:
        f.write(html)
    with (ROOT/'summary.json').open('x',encoding='utf-8') as f:
        json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()

