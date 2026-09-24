"""Generate a fresh, bounded synthetic workload; never ingests or fabricates metrics."""
import argparse
import csv
import hashlib
import json
import random
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Regenerate an interrupted output folder')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=args.resume)
    content = root / 'content'
    for kind in ('images', 'videos', 'documents', 'audio', 'tables'):
        (content / kind).mkdir(parents=True, exist_ok=args.resume)
    run = str(uuid.uuid4())
    rng = random.Random(run)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg is required')
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
    topics = ['warehouse inventory', 'solar energy', 'railway timetable', 'garden maintenance',
              'bakery production', 'vehicle inspection', 'library catalogue', 'weather observations',
              'sports equipment', 'water quality']

    def card(index, size):
        image = Image.new('RGB', size, tuple(rng.randrange(20, 110) for _ in range(3)))
        draw = ImageDraw.Draw(image)
        for _ in range(25):
            x, y = rng.randrange(size[0]), rng.randrange(size[1])
            draw.rectangle((x, y, min(x+80, size[0]), min(y+60, size[1])),
                           fill=tuple(rng.randrange(256) for _ in range(3)))
        draw.rectangle((0, 0, size[0], min(140, size[1])), fill='white')
        draw.text((10, 10), f'Synthetic monitoring sample {index}', fill='black', font=font)
        draw.text((10, 45), topics[index % len(topics)], fill='black', font=font)
        draw.text((10, 80), run, fill='black', font=font)
        return image

    for i in range(180):
        size = [(320,240), (640,480), (1280,720), (1920,1080), (2560,1440), (3840,2160)][i % 6]
        ext = ['png', 'jpg', 'webp'][i % 3]
        card(i, size).save(content / 'images' / f'image-{i+1:03d}.{ext}')
    print('180 images generated', flush=True)
    for i in range(40):
        topic = topics[i % len(topics)]
        if i < 10:
            card(1000+i, (1240,1754)).save(content / 'documents' / f'scanned-page-{i+1:02d}.pdf', 'PDF')
        else:
            lines = [f'SYNTHETIC MONITORING TEST: {topic}', f'Unique batch: {run}', f'Document: {i+1}', '']
            for j in range(20 + i * 5):
                lines.append(f'Record {j+1}: {topic}. Observed quantity {rng.randrange(1,1000)}. '
                             'This generated record is fictional and intended for ingestion and monitoring tests.')
            (content / 'documents' / f'report-{i+1:02d}.txt').write_text('\n'.join(lines), encoding='utf-8')
    for i in range(20):
        with (content / 'tables' / f'measurements-{i+1:02d}.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['batch','record','topic','measurement','unit'])
            writer.writerows([run,j,topics[i%10],round(rng.uniform(0,100),3),'units'] for j in range(100+i*50))
    print('40 documents and 20 tables generated', flush=True)
    with tempfile.TemporaryDirectory(prefix='monitoring-media-') as tmp:
        tmp = Path(tmp)
        speech = []
        for i in range(30):
            speech.append({'path':str(tmp / f'speech-{i:02d}.wav'), 'rate':i%5-2,
                           'text':f'This is synthetic monitoring batch {run[:8]}, test number {i+1}. The topic is {topics[i%10]}. '
                                  f'Today we checked {40+i} items and recorded {i+2} observations. '
                                  'The processing system should transcribe this recording and index the spoken words.'})
        (tmp/'speech.json').write_text(json.dumps(speech), encoding='utf-8')
        speech_command = '''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $speaker.SelectVoice('Microsoft David Desktop')
  foreach ($item in (Get-Content -LiteralPath $env:MONITORING_SPEECH_PLAN -Raw | ConvertFrom-Json)) {
    $speaker.Rate = $item.rate
    $speaker.SetOutputToWaveFile($item.path)
    $speaker.Speak($item.text)
    $speaker.SetOutputToNull()
  }
} finally { $speaker.Dispose() }
'''
        import os
        speech_env = {**os.environ, 'MONITORING_SPEECH_PLAN':str(tmp/'speech.json')}
        subprocess.run(['powershell.exe','-NoProfile','-Command',speech_command],env=speech_env,check=True)
        for i, item in enumerate(speech):
            ext = ['wav','mp3','flac'][i%3]
            target = content/'audio'/f'speech-{i+1:02d}.{ext}'
            if ext == 'wav':
                shutil.copyfile(item['path'],target)
            else:
                subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',item['path'],str(target)],check=True)
        print('30 spoken audio files generated', flush=True)
        for i in range(30):
            size = ['320x240','640x360','1280x720'][i%3]
            duration = [3,5,8][i%3]
            ext = 'mp4' if i%2 == 0 else 'mkv'
            subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i',
                f'testsrc2=size={size}:rate=12:duration={duration}', '-i',speech[i]['path'],
                '-t',str(duration),'-vf',f'hue=h={i*11},drawbox=x={i*3}:y=15:w=30:h=30:color=white:t=fill',
                '-c:v','libx264','-preset','ultrafast','-crf','28','-pix_fmt','yuv420p',
                '-c:a','aac','-metadata',f'comment=Synthetic batch {run}; video {i+1}',
                str(content/'videos'/f'video-{i+1:02d}.{ext}')],check=True)
    print('30 videos with audio generated', flush=True)
    rows = []
    for path in sorted(content.rglob('*')):
        if path.is_file():
            rows.append({'path':path.relative_to(content).as_posix(),'modality':path.parent.name,
                         'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assert len(rows) == 300 and len({r['sha256'] for r in rows}) == 300
    with (root/'manifest.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','modality','bytes','sha256'])
        writer.writeheader(); writer.writerows(rows)
    summary={'batch':run,'files':len(rows),'modalities':dict(Counter(r['modality'] for r in rows)),
             'bytes':sum(r['bytes'] for r in rows),'unique_checksums':len({r['sha256'] for r in rows})}
    (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (root/'README.txt').write_text('''FRESH SYNTHETIC MONITORING DATASET — 300 FILES

Use only the content folder as your ingestion source; the manifest and this guide are not input files.
180 images: PNG/JPEG/WebP, 320x240 through 3840x2160, geometric patterns and readable labels.
30 videos: MP4/MKV, 3/5/8 seconds, 240p/360p/720p test patterns with synthesized speech.
40 documents: 10 scanned one-page PDFs for OCR and 30 text reports of varied lengths.
30 audio files: WAV/MP3/FLAC, synthesized English speech with varied speaking rates.
20 tables: CSV, 100–1050 fictional measurement rows.

All files are synthetic, newly generated and checksum-distinct. They test throughput,
format handling, OCR, transcription, indexing and monitoring. They are not a benchmark
for natural-photo relevance, real-world transcription accuracy or demographic fairness.

1. Copy content to your existing NAS share or S3 test prefix, or choose it in your supported local-source setup.
2. Create a separate connector/dataset called Grafana fresh 300; point it ONLY at that folder/prefix.
3. Set the scan cap to at least 300 and enable recursive scanning for its modality subfolders.
4. Open Grafana with Last 1 hour (or Last 6 hours for a longer run), ending Now; refresh every 30s.
5. Trigger ingestion and watch Documents, AI outcomes, stage durations and pending deliveries.
6. Run searches and download selected results to exercise search/request/download panels.
7. Re-scan unchanged files to exercise duplicate handling. Not every outcome/status should be nonzero.

Saved model initialization checks are setup snapshots, not per-file processing counts.
Existing Grafana panels are platform-wide: record the baseline before starting this batch.
No ingestion was triggered by the generator; no database or monitoring values were fabricated.
''',encoding='utf-8')
    archive = root.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for path in sorted(root.rglob('*')):
            if path.is_file(): z.write(path,path.relative_to(root))
    print(json.dumps({**summary,'folder':str(root),'zip':str(archive)},indent=2),flush=True)


if __name__ == '__main__':
    main()
