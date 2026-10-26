"""Four editable reels from one upload or public link. No vendor modifications."""
from __future__ import annotations

import array
import copy
import hashlib
import json
import math
import logging
import os
import re
import shutil
import subprocess
import threading
import uuid
import wave
import time
import tempfile
from reel_selection import title_intervals, musical_grid, choose_regions, refine_vocal_boundaries
from pathlib import Path

from flask import jsonify, request, send_file

from reference_import import reference_url

ASR_LOCK = threading.Lock()
ASR_MODELS = {}
LOGGER = logging.getLogger(__name__)
FORMATS = {"9:16", "16:9", "mix", "mix_vertical_horizontal"}
STYLES = {"clean", "bold", "glow", "words"}
FFMPEG = os.environ.get('MONTARA_FFMPEG') or next((str(p) for p in [Path('/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg'), Path('/usr/local/opt/ffmpeg-full/bin/ffmpeg')] if p.is_file()), shutil.which('ffmpeg') or 'ffmpeg')


def run(command, timeout=300):
    if command[0] == 'ffmpeg':
        command = [FFMPEG, *command[1:]]
    try:
        return subprocess.run(command, check=True, capture_output=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as exc:
        detail = (getattr(exc, "stderr", b"") or b"").decode(errors="replace")[-1000:]
        raise ValueError("Could not process this media. " + detail) from exc


def preview_with_progress(command,duration,callback):
    """Report actual encoded media time, rather than an elapsed-time estimate."""
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen([FFMPEG,*command[1:-1],'-progress','pipe:1','-nostats',command[-1]],stdout=subprocess.PIPE,stderr=errors,text=True)
        timer=threading.Timer(900,process.kill);timer.daemon=True;timer.start();last=0
        try:
            for line in process.stdout:
                if line.startswith('out_time_us='):
                    try:value=min(99,max(0,int(float(line.split('=',1)[1])/1e6/max(duration,.1)*100)))
                    except ValueError:continue
                    if time.monotonic()-last>.7:callback(value);last=time.monotonic()
            if process.wait()!=0:raise ValueError('Could not prepare the preview. Retry this video.')
            callback(100)
        finally:
            timer.cancel()
            if process.poll() is None:process.kill();process.wait()


def layout_segments(data,reel):
    length=reel['end']-reel['start'];fmt=data['format']
    if fmt!='mix':return [{'start':0,'end':length,'layout':'horizontal' if fmt=='16:9' or fmt=='mix_vertical_horizontal' and int(reel['id'])%2==0 else 'vertical'}]
    ratio=data.get('mix_vertical_ratio',.5)
    if ratio=='auto':ratio=.5
    ratio=float(ratio);cycles=max(1,math.ceil(length/12));spans=[]
    for i in range(cycles):
        a,b=i*length/cycles,(i+1)*length/cycles;cut=a+(b-a)*ratio
        if cut>a:spans.append({'start':a,'end':cut,'layout':'vertical'})
        if b>cut:spans.append({'start':cut,'end':b,'layout':'horizontal'})
    return spans


def horizontal_filter(width,height,frame):
    zoom=frame.get('zoom',1);x=frame.get('x',.5);y=frame.get('y',.5)
    return f"split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20[back];[fg]scale={math.ceil(width*zoom/2)*2}:{math.ceil(height*zoom/2)*2}:force_original_aspect_ratio=decrease[front];[back][front]overlay=(W-w)*{x}:(H-h)*{y},setsar=1"


def probe(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]).stdout)
    if not any(s.get("codec_type") == "video" for s in data["streams"]):
        raise ValueError("Choose a video, with the song in its audio track.")
    duration = float(data["format"].get("duration", 0))
    if not math.isfinite(duration) or not 20 <= duration <= 7200:
        raise ValueError("For four reels, choose a video between 20 seconds and two hours.")
    return duration, any(s.get("codec_type") == "audio" for s in data["streams"])


def speech_model(name=None):
    from faster_whisper import WhisperModel
    name=name or os.environ.get('MONTARA_WHISPER_MODEL','small')
    if name not in ASR_MODELS:
        ASR_MODELS[name]=WhisperModel(name,device='cpu',compute_type='int8',cpu_threads=int(os.environ.get('MONTARA_WHISPER_THREADS','2')),download_root=os.environ.get('HF_HUB_CACHE'),local_files_only=bool(os.environ.get('MONTARA_SHARED_MODELS')))
    return ASR_MODELS[name]


def is_lyric_text(text):
    bare=''.join(c for c in text if c.isalnum()).casefold()
    return bool(bare) and bare not in {'music','instrumental','música','musica','musique','applause','silence'}


def align_text(audio, text, language, anchor_start=0, anchor_end=None):
    """Force-align the supplied words against acoustic features; never invent even spacing."""
    from faster_whisper.tokenizer import Tokenizer
    model = speech_model()
    tokenizer = Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task='transcribe', language=language or 'en')
    features = model.feature_extractor(audio)
    segment={'seek':0,'tokens':tokenizer.encode(' '+text.strip()),'start':anchor_start,'end':anchor_end if anchor_end is not None else len(audio)/16000}
    # Use Whisper's own boundary refinement: raw DTW anchors the first word at
    # the context-window start, which can be seconds before the voice enters.
    model.add_word_timestamps([[segment]],tokenizer,model.encode(features),len(audio)//model.feature_extractor.hop_length,'\"\'“¿([{-','\"\'.。,，!！?？:：”)]}、',anchor_start)
    return [{'start':float(w['start']),'end':float(w['end']),'text':w['word'].strip()} for w in segment.get('words',[]) if w['word'].strip() and w['end']>w['start']]


def framing_filter(width, height, framing):
    x,y,zoom=[framing.get(k,v) for k,v in [('x',.5),('y',.5),('zoom',1.)]]
    # Normalized centre over the available pan range, matching CSS object-position.
    return rf"scale={math.ceil(width*zoom/2)*2}:{math.ceil(height*zoom/2)*2}:force_original_aspect_ratio=increase,pad=max(iw\,{width}):max(ih\,{height}):(ow-iw)*{x}:(oh-ih)*{y},crop={width}:{height}:(iw-ow)*{x}:(ih-oh)*{y},setsar=1"


def suggest_regions(duration, target, energies):
    """One energetic window per quarter; independent trim handles remain editable."""
    length = min(target, duration / 4)
    regions = []
    for i in range(4):
        low, high = i * duration / 4, (i + 1) * duration / 4
        candidates = [low] + [float(t) for t in range(math.ceil(low), math.floor(high - length) + 1)]
        start = max(candidates, key=lambda t: sum(energies[int(t):min(len(energies), math.ceil(t + length))]) / max(1, math.ceil(length)))
        regions.append({"id": str(i + 1), "start": round(start, 3), "end": round(min(high, start + length), 3), "selected": True,
                        "captions_on": True, "caption_style": "clean", "caption_edits": None, "revision": 0,
                        "framing": {"x": .5, "y": .5, "zoom": 1.}, "alignment_status": "idle", "render": {"status": "idle"}})
    return regions


def clipped_cues(cues, start, end):
    result = []
    for cue in cues:
        if cue["end"] <= start or cue["start"] >= end or not cue["text"].strip():
            continue
        words = [{"start": max(start, w["start"])-start, "end": min(end, w["end"])-start, "text": w["text"]}
                 for w in cue.get("words", []) if w["end"] > start and w["start"] < end]
        result.append({"start": round(max(start, cue["start"])-start, 3), "end": round(min(end, cue["end"])-start, 3),
                       "text": " ".join(w["text"] for w in words) if words else cue["text"], "words": words})
    return result


def ass_time(seconds):
    centis = max(0, round(float(seconds) * 100))
    return f"{centis // 360000}:{centis // 6000 % 60:02}:{centis // 100 % 60:02}.{centis % 100:02}"


def ass_text(value):
    return str(value).replace("\\", "＼").replace("{", "(").replace("}", ")").replace("\r", "").replace("\n", "\\N")


def write_ass(path, cues, style, width, height):
    size = round(height * .045)
    colour = "&H004DE1FF" if style == "glow" else "&H00FFFFFF"
    font = "DejaVu Sans"
    header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
              f"Style: Default,{font},{size},{colour},{colour},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,{round(height*.12)},1\n"
              "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    events = []
    for cue in cues:
        if style == "words" and cue.get("words"):
            for word in cue["words"]:
                events.append(f"Dialogue: 0,{ass_time(word['start'])},{ass_time(word['end'])},Default,,0,0,0,,{ass_text(word['text'])}\n")
            continue
        parts = [cue["text"]]
        if not parts:
            continue
        for i, text in enumerate(parts):
            a = cue["start"] + (cue["end"] - cue["start"]) * i / len(parts)
            b = cue["start"] + (cue["end"] - cue["start"]) * (i + 1) / len(parts)
            effect = "{\\blur3}" if style == "glow" else "{\\bord3}" if style == "bold" else ""
            events.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{effect}{ass_text(text)}\n")
    path.write_text(header + "".join(events), encoding="utf-8")


class PushPacks:
    def __init__(self, data_root, fixtures):
        self.root = Path(data_root).resolve() / "PushPacks"
        self.root.mkdir(parents=True, exist_ok=True)
        self.allowed = [Path(data_root).resolve(), Path(fixtures).resolve()]
        self.lock = threading.RLock()
        self.render_lock = threading.Lock()
        for manifest in self.root.glob('*/pack.json'):
            try:
                data = json.loads(manifest.read_text())
                before=copy.deepcopy(data)
                if data.get('layout_version',1)<2:
                    data.update(layout_version=2,mix_vertical_ratio=data.get('mix_vertical_ratio',.5))
                    for reel in data['reels']:
                        reel['revision']+=1
                        if reel['render']['status']=='ready':reel['render']={'status':'idle'}
                if data['status'] == 'preparing':
                    data.update(status='failed', message='Preparation was interrupted by a restart. Import this video again.')
                for reel in data['reels']:
                    if reel.get('lyrics_status') == 'running':reel.update(lyrics_status='failed',lyrics_message='Reading was interrupted. Read this reel again.')
                    if reel.get('alignment_status') == 'running':reel.update(alignment_status='failed', alignment_message='Word sync was interrupted. Retry syncing the words.')
                if data['captions_status'] == 'running':
                    data.update(captions_status='failed', captions_message='Reading was interrupted. Retry the lyrics.')
                for reel in data['reels']:
                    if reel['render']['status'] in {'queued', 'running'}:
                        reel['render'] = {'status': 'failed', 'message': 'Rendering was interrupted. Retry this reel.'}
                if data!=before:self.save(data)
            except (ValueError, KeyError, OSError):
                continue

    def folder(self, pack_id):
        if not re.fullmatch(r"[0-9a-f]{32}", pack_id):
            raise ValueError("Choose an existing reel pack.")
        return self.root / pack_id

    def load(self, pack_id):
        try:
            data = json.loads((self.folder(pack_id) / "pack.json").read_text())
        except FileNotFoundError as exc:
            raise ValueError("This reel pack does not exist.") from exc
        return data

    def save(self, data):
        folder = self.folder(data["id"])
        folder.mkdir(parents=True, exist_ok=True)
        temporary = folder / "pack.json.tmp"
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(folder / "pack.json")

    def change(self, pack_id, callback):
        with self.lock:
            data = self.load(pack_id)
            callback(data)
            self.save(data)
            return data

    def public(self, pack_id):
        with self.lock:
            data = copy.deepcopy(self.load(pack_id))
        data.pop("source", None)
        data.pop("url", None)
        source_cues = data.pop("cues", [])
        data["source_url"] = f"/montara/push/packs/{pack_id}/media"
        for reel in data.get("reels", []):
            reel["layout_segments"]=layout_segments(data,reel)
            cues = reel.pop("caption_edits", None)
            reel["captions_edited"] = cues is not None
            reel["captions"] = clipped_cues(source_cues if cues is None else cues, reel["start"], reel["end"])
            if reel["render"].get("status") == "ready":
                reel["render"]["url"] = f"/montara/push/packs/{pack_id}/reels/{reel['id']}/file"
        return data

    def local_source(self, value):
        path = Path(str(value)).expanduser().resolve()
        if not any(path.is_relative_to(root) for root in self.allowed) or not path.is_file():
            raise ValueError("Upload the video or choose one of Montara's example videos first.")
        return path

    def create(self, body):
        if bool(body.get("url")) == bool(body.get("source")):
            raise ValueError("Choose one internet link or one uploaded video.")
        length = float(body.get("length", 30))
        if not math.isfinite(length) or not 5 <= length <= 90:
            raise ValueError("Choose a reel length between 5 and 90 seconds.")
        fmt = body.get("format", "9:16")
        if fmt not in FORMATS:
            raise ValueError("Choose a supported reel format.")
        source = str(self.local_source(body["source"])) if body.get("source") else ""
        url = reference_url(body["url"]) if body.get("url") else ""
        ratio=body.get('mix_vertical_ratio',.5)
        if ratio!='auto':
            ratio=float(ratio)
            if not math.isfinite(ratio) or not 0<=ratio<=1:raise ValueError('Choose a vertical share between 0 and 100 percent.')
        pack_id = uuid.uuid4().hex
        data = {"id": pack_id, "status": "preparing", "message": "Downloading the video…" if url else "Preparing your video…",
                "title": "Four reels", "source": source, "url": url, "duration": 0, "length": length, "format": fmt, "mix_vertical_ratio":ratio,"layout_version":2,"phase":"download" if url else "preview","progress":None,
                "reels": [], "cues": [], "captions_status": "pending", "captions_message": "", "revision": 0}
        with self.lock:
            self.save(data)
        threading.Thread(target=self.prepare, args=(pack_id,), daemon=True).start()
        return self.public(pack_id)

    def download(self, pack_id, url):
        from source_cache import find_source
        cached=find_source(self.allowed[0],self.allowed[1],url)
        if cached:
            source,title,origin=cached
            self.change(pack_id,lambda d:d.update(cached_source=origin=='included_original',source_origin=origin,message='Reusing the original video already available. Preparing new editable reels…'))
            return source,title
        from yt_dlp import YoutubeDL
        folder = self.folder(pack_id)
        def limit(info, *, incomplete=False):
            if (info.get("duration") or 0) > 7200:
                return "Choose a video shorter than two hours."
        options = {"format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", "noplaylist": True,
                   "outtmpl": str(folder / "download.%(ext)s"), "merge_output_format": "mp4", "quiet": True,
                   "no_warnings": True, "socket_timeout": 20, "retries": 1, "fragment_retries": 1,
                   "max_filesize": 1024**3, "match_filter": limit, "noprogress": True}
        try:
            last=[0.]
            def progress(update):
                if time.monotonic()-last[0]<1:return
                last[0]=time.monotonic();total=update.get('total_bytes') or update.get('total_bytes_estimate')
                percent=min(99,int(update.get('downloaded_bytes',0)/total*100)) if total else None
                self.change(pack_id,lambda d:d.update(phase='download',progress=percent,message='Downloading the video…'))
            options['progress_hooks']=[progress]
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
            if not info:
                raise ValueError("This video is too long or cannot be downloaded.")
            candidates = [p for p in folder.glob("download.*") if p.suffix not in {".part", ".ytdl", ".json"} and p.is_file()]
            source = next((p for p in candidates if p.suffix == ".mp4"), next(iter(candidates), None))
            if not source:
                raise ValueError("The link did not return a video.")
            return source, str(info.get("title") or "Internet video")
        except Exception as exc:
            LOGGER.warning("Internet import failed for pack %s: %s",pack_id,str(exc)[-500:])
            raise ValueError("Could not download this public video. If the service asks for sign-in or verification, upload the video file instead.") from exc

    def prepare(self, pack_id):
        try:
            data = self.load(pack_id)
            if data["url"]:
                source, title = self.download(pack_id, data["url"])
            else:
                source, title = Path(data["source"]), Path(data["source"]).stem
            duration, audio = probe(source)
            folder = self.folder(pack_id)
            self.change(pack_id, lambda d: d.update(message="Preparing your preview…", phase="preview",progress=0,source=str(source), title=title))
            preview_with_progress(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(source), "-vf", "scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(folder / "preview.mp4")],duration,lambda n:self.change(pack_id,lambda d:d.update(progress=n)))
            self.change(pack_id,lambda d:d.update(phase='analysis',progress=None,message='Finding musical phrases and checking title cards…'))
            import numpy as np
            raw=run(['ffmpeg','-v','error','-i',str(folder/'preview.mp4'),'-vf','fps=1,scale=96:54,format=gray','-f','rawvideo','-pix_fmt','gray','-'],timeout=300).stdout
            frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,54,96)
            excluded=title_intervals(frames)
            grid={'boundaries':[],'tempo':None}
            energies = []
            if audio:
                run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", str(folder / "analysis.wav")])
                with wave.open(str(folder / "analysis.wav")) as track:
                    while frames := track.readframes(8000):
                        samples = array.array("h", frames)
                        energies.append(math.sqrt(sum(v*v for v in samples) / max(1, len(samples))))
                grid=musical_grid(folder/'analysis.wav')
            reels=suggest_regions(duration,data['length'],energies)
            proposals=choose_regions(duration,data['length'],energies,excluded,grid['boundaries'])
            for reel,proposal in zip(reels,proposals):reel.update(proposal,cuts_edited=False)
            self.change(pack_id, lambda d: d.update(status="ready", phase='ready',progress=100,duration=duration,selection={'excluded':excluded,**grid},reels=reels,
                        message="Four suggested moments. Move or trim each region before exporting.", captions_status="running" if audio else "unavailable",
                        captions_message="Reading the song once for all four reels…" if audio else "This video has no audio. You can add captions manually."))
            if audio and not self.restore_transcript_cache(pack_id):
                self.transcribe(pack_id)
        except Exception as exc:
            self.change(pack_id, lambda d: d.update(status="failed", message=str(exc)))

    def restore_transcript_cache(self,pack_id):
        """Reuse verified analysis of the exact included source, never rendered reels."""
        data=self.load(pack_id);cache=self.allowed[1]/'push-links/captions-large-v3.json'
        if not data.get('cached_source') or not cache.is_file():return False
        try:
            saved=json.loads(cache.read_text())
            if saved['model'] not in {'small','medium','large-v3'} or saved['source_sha256']!=hashlib.sha256(Path(data['source']).read_bytes()).hexdigest():return False
            cues=[c for c in saved['cues'] if is_lyric_text(c['text'])]
            if not isinstance(cues,list) or not cues:return False
            for cue in cues:
                if not 0<=float(cue['start'])<float(cue['end'])<=data['duration']+.1:return False
                for word in cue.get('words',[]):
                    if not 0<=float(word['start'])<float(word['end'])<=data['duration']+.1:return False
            def done(d):
                d.update(cues=cues,language=saved['language'],captions_model=saved['model'],captions_sample_rate=16000,captions_status='ready',cached_captions=True,captions_message='Using saved Whisper analysis of this included original. Read lyrics again to run a fresh reading.')
                refine_vocal_boundaries(d)
                for reel in d['reels']:reel['revision']+=1
            self.change(pack_id,done)
            return True
        except (ValueError,KeyError,TypeError,OSError):
            LOGGER.warning('Could not reuse the included transcript; reading the source normally.')
            return False

    def transcription_audio(self, pack_id):
        folder=self.folder(pack_id)
        target=folder/'speech-16k.wav'
        if not target.is_file():
            run(['ffmpeg','-v','error','-nostdin','-y','-i',self.load(pack_id)['source'],'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(target)],timeout=900)
        return target

    def reread_reel(self, pack_id, reel_id):
        def queue(data):
            reel=next((r for r in data['reels'] if r['id']==reel_id),None)
            if not reel:raise ValueError('Choose an existing reel.')
            if data['captions_status']=='running' or reel.get('lyrics_status')=='running' or reel.get('alignment_status')=='running':raise ValueError('Wait for the current reading or word sync.')
            if reel['render']['status'] in {'running','queued'}:raise ValueError('Wait for this export before reading again.')
            if not (self.folder(pack_id)/'analysis.wav').is_file():raise ValueError('This video has no audio track.')
            reel.update(lyrics_status='running',lyrics_message='Listening to this reel again…')
        data=self.change(pack_id,queue)
        reel=next(r for r in data['reels'] if r['id']==reel_id)
        threading.Thread(target=self.transcribe,args=(pack_id,reel_id,(reel['start'],reel['end'])),daemon=True).start()
        return self.public(pack_id)

    def set_format(self,pack_id,body):
        def update(data):
            if body.get('format',data['format']) not in FORMATS:raise ValueError('Choose a supported reel format.')
            ratio=body.get('mix_vertical_ratio',data.get('mix_vertical_ratio',.5))
            if ratio!='auto':
                ratio=float(ratio)
                if not math.isfinite(ratio) or not 0<=ratio<=1:raise ValueError('Choose a vertical share between 0 and 100 percent.')
            if data.get('revision',0)!=body.get('revision'):raise ValueError('This pack changed. Retry with its latest settings.')
            if any(r['render']['status'] in {'running','queued'} for r in data['reels']):raise ValueError('Wait for exports before changing the layout.')
            data['format']=body.get('format',data['format']);data['mix_vertical_ratio']=ratio;data['revision']+=1
            for reel in data['reels']:reel['revision']+=1;reel['render']={'status':'idle'}
        self.change(pack_id,update)
        return self.public(pack_id)

    def transcribe(self, pack_id, reel_id=None, region=None):
        cropped=None
        try:
            audio=self.transcription_audio(pack_id)
            offset=region[0] if region else 0
            duration=region[1]-region[0] if region else self.load(pack_id)['duration']
            if region:
                cropped=self.folder(pack_id)/f'read-{reel_id}-{uuid.uuid4().hex}.wav'
                run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(offset),'-i',str(audio),'-t',str(duration),'-ac','1','-ar','16000',str(cropped)])
                audio=cropped
            with ASR_LOCK:
                configured=os.environ.get('MONTARA_WHISPER_MODEL','small')
                for model_name in ([configured,'medium'] if configured=='small' else [configured]):
                    model=speech_model(model_name)
                    segments, info=model.transcribe(str(audio),beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False,task='transcribe')
                    cues=[]
                    for segment in segments:
                        words=[{'start':max(offset,w.start+offset),'end':min(offset+duration,w.end+offset),'text':w.word.strip()} for w in (segment.words or []) if w.word.strip() and any(c.isalnum() for c in w.word) and w.end>w.start]
                        if not is_lyric_text(segment.text) or not words:continue
                        group=[]
                        for word in words:
                            group.append(word)
                            if len(group)>=6 or word['end']-group[0]['start']>=3 or re.search(r'[.!?,]$',word['text']):
                                cues.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['text'] for w in group),'words':group})
                                group=[]
                        if group:cues.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['text'] for w in group),'words':group})
                        progress=f"Listening… {min(99,int(segment.end/max(1,duration)*100))}%"
                        if reel_id:self.change(pack_id,lambda d:next(r for r in d['reels'] if r['id']==reel_id).update(lyrics_message=progress))
                        else:self.change(pack_id,lambda d:d.update(captions_message=progress))
                    if cues:break
            def done(data):
                if reel_id:
                    reel=next(r for r in data['reels'] if r['id']==reel_id)
                    if (reel['start'],reel['end'])!=region:
                        reel.update(lyrics_status='failed',lyrics_message='The reel moved while reading. Read its new position again.');return
                    reel.update(caption_edits=cues,lyrics_status='ready',lyrics_model=model_name,lyrics_region=list(region),lyrics_message='This reel was read again. Check the singing by ear.',alignment_status='ready',alignment_message='',revision=reel['revision']+1,render={'status':'idle'})
                    return
                data.update(cues=cues, language=info.language, captions_model=model_name, captions_sample_rate=16000, captions_status="ready", captions_message="Lyrics read. Check the words: singing can be misheard." if cues else "No words were detected in this audio. Add captions manually, or try reading the song again.")
                refine_vocal_boundaries(data)
                for reel in data["reels"]:
                    if reel["caption_edits"] is None and reel["captions_on"]:
                        reel["revision"] += 1
                        if reel["render"]["status"] == "ready":
                            reel["render"] = {"status": "idle"}
            self.change(pack_id, done)
        except Exception:
            LOGGER.exception("Push lyrics failed for %s",pack_id)
            if reel_id:self.change(pack_id,lambda d:next(r for r in d['reels'] if r['id']==reel_id).update(lyrics_status='failed',lyrics_message='Could not read this reel. Retry; your earlier text is preserved.'))
            else:self.change(pack_id, lambda d: d.update(captions_status="failed", captions_message="Could not read the lyrics. Retry or add your captions manually; the four clips are still editable."))
        finally:
            if cropped:cropped.unlink(missing_ok=True)

    def patch(self, pack_id, reel_id, body):
        def update(data):
            reel = next((r for r in data["reels"] if r["id"] == reel_id), None)
            if not reel:
                raise ValueError("Choose an existing reel.")
            if body.get("revision") != reel["revision"]:
                raise ValueError("This reel changed. Reload its latest settings.")
            if reel["render"]["status"] in {"queued", "running"}:
                raise ValueError("Wait for this reel's render before changing it.")
            start, end = float(body.get("start", reel["start"])), float(body.get("end", reel["end"]))
            if not all(map(math.isfinite, [start, end])) or start < 0 or end > data["duration"] + .001 or not 1 <= end-start <= 90:
                raise ValueError("Keep each reel inside the video, between 1 and 90 seconds long.")
            style = body.get("caption_style", reel["caption_style"])
            if style not in STYLES:
                raise ValueError("Choose a supported caption style.")
            if reel.get('lyrics_status')=='running' and any(k in body for k in ('captions','start','end','use_detected_captions')):raise ValueError('Wait until this reel has been read.')
            if 'captions' in body and reel.get('alignment_status')=='running':raise ValueError('Wait for word sync before changing the captions.')
            edits = reel["caption_edits"]
            if "captions" in body:
                visible=clipped_cues(reel['caption_edits'] if reel['caption_edits'] is not None else data['cues'],start,end)
                if not isinstance(body["captions"], list) or len(body["captions"]) > 200:
                    raise ValueError("Use at most 200 caption cues per reel.")
                edits = []
                for cue in body["captions"]:
                    a, b, text = float(cue["start"]), float(cue["end"]), str(cue["text"]).strip()
                    if not all(map(math.isfinite, [a,b])) or not 0 <= a < b <= end-start+.001 or len(text) > 500:
                        raise ValueError("Keep every caption inside its reel, with a start before its end.")
                    if text:
                        normalize=lambda value:re.sub(r'\W','',value).casefold()
                        old=next((c for c in visible if normalize(c['text'])==normalize(text) and abs(c['start']-a)<.005 and abs(c['end']-b)<.005),None)
                        parts=text.split();old_words=(old or {}).get('words',[])
                        words=[{**w,'text':part,'start':w['start']+start,'end':w['end']+start} for w,part in zip(old_words,parts)] if len(parts)==len(old_words) else []
                        edits.append({'start':a+start,'end':b+start,'text':text,'words':words})
            if body.get('use_detected_captions') is True:
                if data['captions_status']!='ready':raise ValueError('Wait until the new lyrics have been read.')
                edits=None
                reel.update(alignment_status='idle',alignment_message='')
            for name in ("selected", "captions_on"):
                if name in body and not isinstance(body[name], bool):
                    raise ValueError("Choose an on/off value.")
            framing=dict(reel.get('framing',{'x':.5,'y':.5,'zoom':1.}))
            if 'framing' in body:
                proposed=body['framing']
                if not isinstance(proposed,dict) or set(proposed)-{'x','y','zoom'}:raise ValueError('Choose a valid frame.')
                framing.update({k:float(v) for k,v in proposed.items()})
                if not all(math.isfinite(v) for v in framing.values()) or not 0<=framing['x']<=1 or not 0<=framing['y']<=1 or not .1<=framing['zoom']<=3:raise ValueError('Keep the frame inside the image, with zoom between 0.1 and 3.')
            if 'start' in body or 'end' in body:reel['cuts_edited']=True
            visual_change = any(key in body for key in ("start", "end", "captions", "captions_on", "caption_style", "framing", "use_detected_captions"))
            reel.update(start=start, end=end, caption_edits=edits, caption_style=style, framing=framing,
                        selected=body.get("selected", reel["selected"]), captions_on=body.get("captions_on", reel["captions_on"]), revision=reel["revision"]+1)
            if visual_change:
                reel["render"] = {"status": "idle"}
            data["revision"] += 1
        self.change(pack_id, update)
        reel=next(r for r in self.load(pack_id)['reels'] if r['id']==reel_id)
        if 'captions' in body and any(not c.get('words') for c in reel['caption_edits'] or []):self.start_alignment(pack_id,reel_id)
        return self.public(pack_id)

    def start_alignment(self,pack_id,reel_id,force=False):
        def queue(data):
            reel=next(r for r in data['reels'] if r['id']==reel_id)
            if reel.get('lyrics_status')=='running':raise ValueError('Wait for this reel to finish reading.')
            if reel.get('alignment_status')=='running':raise ValueError('Word sync is already running.')
            if reel['render']['status'] in {'running','queued'}:raise ValueError('Wait for this export before syncing words.')
            reel.update(alignment_status='running',alignment_message='Syncing your words to the voice…')
        self.change(pack_id,queue)
        threading.Thread(target=self.align_reel,args=(pack_id,reel_id,force),daemon=True).start()

    def align_reel(self,pack_id,reel_id,force=False):
        try:
            from faster_whisper.audio import decode_audio
            audio=decode_audio(str(self.transcription_audio(pack_id)),sampling_rate=16000)
            data=self.load(pack_id);reel=next(r for r in data['reels'] if r['id']==reel_id);revision=reel['revision']
            cues=copy.deepcopy(reel['caption_edits'] if reel['caption_edits'] is not None else [c for c in data['cues'] if c['end']>reel['start'] and c['start']<reel['end']])
            with ASR_LOCK:
                language=data.get('language')
                if not language:
                    _,info=speech_model().transcribe(audio[int(reel['start']*16000):int(min(reel['end'],reel['start']+30)*16000)],beam_size=1)
                    language=info.language
                for cue in cues:
                    if not force and cue.get('words') and re.sub(r'\W','',''.join(w['text'] for w in cue['words'])).casefold()==re.sub(r'\W','',cue['text']).casefold():continue
                    if cue['end']-cue['start']>30:raise ValueError('Use caption phrases shorter than 30 seconds for word sync.')
                    lo=max(0,cue['start']-2);hi=min(data['duration'],cue['end']+2)
                    if hi-lo>30:lo=cue['start'];hi=cue['end']
                    clip=audio[int(lo*16000):int(hi*16000)]
                    if not len(clip):raise ValueError('Place this caption over the voice before syncing.')
                    words=align_text(clip,cue['text'],language,max(0,cue['start']-lo),min(hi-lo,cue['end']-lo))
                    if not words or re.sub(r'\W','',''.join(w['text'] for w in words)).casefold()!=re.sub(r'\W','',cue['text']).casefold():raise ValueError('Some words could not be located in this audio. Move the caption over the sung phrase and sync again; your written text is preserved.')
                    cue['words']=[{'text':w['text'],'start':lo+w['start'],'end':min(hi,lo+w['end'])} for w in words]
                    cue['start']=cue['words'][0]['start'];cue['end']=cue['words'][-1]['end']
            def done(d):
                current=next(r for r in d['reels'] if r['id']==reel_id)
                if current['revision']!=revision:
                    current.update(alignment_status='failed',alignment_message='The captions changed during sync. Sync the latest words again.');return
                current.update(caption_edits=cues,alignment_status='ready',alignment_message='Words synced to the audio. Check the singing by ear.',revision=revision+1,render={'status':'idle'})
            self.change(pack_id,done)
        except Exception as exc:
            LOGGER.exception('Push alignment failed for %s/%s',pack_id,reel_id)
            self.change(pack_id,lambda d:next(r for r in d['reels'] if r['id']==reel_id).update(alignment_status='failed',alignment_message=str(exc)))

    def export(self, pack_id, ids):
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or any(i not in {"1", "2", "3", "4"} for i in ids):
            raise ValueError("Select one to four reels to export.")
        def queue(data):
            if data["status"] != "ready":
                raise ValueError("Wait until the video is ready.")
            if any(r["render"]["status"] in {"queued", "running"} for r in data["reels"]):
                raise ValueError("Wait for the current exports to finish.")
            for reel in data["reels"]:
                if reel["id"] in ids:
                    if reel.get('lyrics_status')=='running':raise ValueError('Wait for this reel to finish reading.')
                    if reel['captions_on'] and reel['caption_style']=='words' and (reel.get('alignment_status')=='running' or any(not c.get('words') for c in clipped_cues(data['cues'] if reel['caption_edits'] is None else reel['caption_edits'],reel['start'],reel['end']))):raise ValueError('Sync the words to the voice before exporting word-by-word captions.')
                    if reel["captions_on"] and reel["caption_edits"] is None and data["captions_status"] in {"pending", "running"}:
                        raise ValueError("Wait for the lyrics, add captions manually, or turn captions off for this reel.")
                    if reel["render"]["status"] != "ready":
                        reel["render"] = {"status": "queued", "progress": 0}
        self.change(pack_id, queue)
        threading.Thread(target=self.render_selected, args=(pack_id, ids), daemon=True).start()
        return self.public(pack_id)

    def render_selected(self, pack_id, ids):
        with self.render_lock:
            for reel_id in ids:
                data = self.load(pack_id)
                reel = next(r for r in data["reels"] if r["id"] == reel_id)
                if reel["render"]["status"] == "ready":
                    continue
                try:
                    self.change(pack_id, lambda d: next(r for r in d["reels"] if r["id"] == reel_id).update(render={"status": "running", "progress": 0}))
                    self.render_one(data, reel)
                    self.change(pack_id, lambda d: next(r for r in d["reels"] if r["id"] == reel_id).update(render={"status": "ready", "progress": 100}))
                except Exception as exc:
                    self.change(pack_id, lambda d: next(r for r in d["reels"] if r["id"] == reel_id).update(render={"status": "failed", "message": str(exc)}))

    def render_one(self, data, reel):
        folder = self.folder(data["id"])
        width,height=720,1280
        frame=reel.get('framing',{});spans=layout_segments(data,reel)
        if data['format']=='mix' and len({p['layout'] for p in spans})==2:
            enabled='+'.join(f"gte(t,{p['start']:.6f})*lt(t,{p['end']:.6f})" for p in spans if p['layout']=='vertical')
            fit=f"setpts=PTS-STARTPTS,split=2[vertical][horizontal];[vertical]{framing_filter(width,height,frame)}[cropped];[horizontal]{horizontal_filter(width,height,frame)}[framed];[framed][cropped]overlay=enable='{enabled}':shortest=1,setsar=1"
        elif spans[0]['layout']=='horizontal':fit=horizontal_filter(width,height,frame)
        else:fit=framing_filter(width,height,frame)
        cues = clipped_cues(data["cues"] if reel["caption_edits"] is None else reel["caption_edits"], reel["start"], reel["end"])
        if reel["captions_on"] and cues:
            ass = folder / f"reel-{reel['id']}.ass"
            write_ass(ass, cues, reel["caption_style"], width, height)
            # Only internally generated relative filenames enter the filter grammar.
            fit += f",ass=reel-{reel['id']}.ass"
        target = folder / f"reel-{reel['id']}.mp4"
        temporary = target.with_suffix(".part.mp4")
        command = [FFMPEG, "-v", "error", "-nostdin", "-y", "-ss", str(reel["start"]), "-i", data["source"], "-t", str(reel["end"]-reel["start"]), "-map", "0:v:0", "-map", "0:a:0?", "-vf", fit,
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(temporary)]
        try:
            subprocess.run(command, cwd=folder, check=True, capture_output=True, timeout=900)
            temporary.replace(target)
        except (subprocess.SubprocessError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise ValueError("This reel could not render. Your other reels and edits are preserved; retry this one.") from exc


def register_push_pack(app, data_root, fixtures):
    store = PushPacks(data_root, fixtures)
    app.extensions["montara_push_packs"] = store

    def respond(action):
        try:
            return jsonify(action())
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            return jsonify(error={"message": str(exc)}), 400

    @app.post("/montara/push/packs")
    def create_push_pack():
        return respond(lambda: store.create(request.get_json(silent=True) or {}))

    @app.get('/montara/push/packs/latest')
    def latest_push_pack():
        for path in sorted(store.root.glob('*/pack.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                data=store.load(path.parent.name)
                if data['status']=='ready':return jsonify(id=data['id'],url=data.get('url',''),source=data.get('source',''),name=data['title'])
            except (ValueError,KeyError,OSError):continue
        return jsonify({})

    @app.get("/montara/push/packs/<pack_id>")
    def read_push_pack(pack_id):
        return respond(lambda: store.public(pack_id))

    @app.patch("/montara/push/packs/<pack_id>/reels/<reel_id>")
    def patch_push_reel(pack_id, reel_id):
        return respond(lambda: store.patch(pack_id, reel_id, request.get_json(silent=True) or {}))

    @app.post("/montara/push/packs/<pack_id>/export")
    def export_push_pack(pack_id):
        return respond(lambda: store.export(pack_id, (request.get_json(silent=True) or {}).get("ids")))

    @app.post('/montara/push/packs/<pack_id>/reels/<reel_id>/align')
    def align_push_words(pack_id,reel_id):
        def align():
            if reel_id not in {'1','2','3','4'}:raise ValueError('Choose an existing reel.')
            store.start_alignment(pack_id,reel_id,force=True)
            return store.public(pack_id)
        return respond(align)

    @app.patch('/montara/push/packs/<pack_id>')
    def change_pack_format(pack_id):
        return respond(lambda:store.set_format(pack_id,request.get_json(silent=True) or {}))

    @app.post('/montara/push/packs/<pack_id>/reels/<reel_id>/lyrics')
    def reread_push_reel(pack_id,reel_id):
        return respond(lambda:store.reread_reel(pack_id,reel_id))

    @app.post("/montara/push/packs/<pack_id>/lyrics")
    def retry_push_lyrics(pack_id):
        def retry():
            with store.lock:
                data = store.load(pack_id)
                if data["captions_status"] == "running":
                    raise ValueError("The song is already being read.")
                if not (store.folder(pack_id) / "analysis.wav").is_file():
                    raise ValueError("This video has no audio track.")
                data["captions_status"] = "running"
                data["cached_captions"] = False
                data["captions_message"] = "Reading the song again with Whisper…"
                store.save(data)
            threading.Thread(target=store.transcribe, args=(pack_id,), daemon=True).start()
            return store.public(pack_id)
        return respond(retry)

    @app.get("/montara/push/packs/<pack_id>/media")
    def push_pack_media(pack_id):
        try:
            return send_file(store.folder(pack_id) / "preview.mp4", conditional=True)
        except (ValueError, FileNotFoundError):
            return "", 404

    @app.get("/montara/push/packs/<pack_id>/reels/<reel_id>/file")
    def push_reel_file(pack_id, reel_id):
        try:
            data = store.load(pack_id)
            reel = next((r for r in data["reels"] if r["id"] == reel_id), None)
            if not reel or reel["render"]["status"] != "ready":
                return "", 404
            return send_file(store.folder(pack_id) / f"reel-{reel_id}.mp4", conditional=True, as_attachment=True, download_name=f"Montara-reel-{reel_id}.mp4")
        except (ValueError, FileNotFoundError):
            return "", 404
