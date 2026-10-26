"""Cheap audiovisual proposals, with conservative title-card avoidance (no remote AI)."""
from __future__ import annotations
import math
from bisect import bisect_left, bisect_right
import wave
from pathlib import Path
import numpy as np


def title_intervals(frames, fps=1):
    """Uniform, still graphic cards; do not mistake a whole static video for an intro."""
    if len(frames)<4:return []
    frames=np.asarray(frames,dtype=np.float32)
    motion=np.r_[0,np.abs(np.diff(frames,axis=0)).mean(axis=(1,2))]
    border=np.concatenate([frames[:,:4,:].reshape(len(frames),-1),frames[:,-4:,:].reshape(len(frames),-1),frames[:,:, :4].reshape(len(frames),-1),frames[:,:,-4:].reshape(len(frames),-1)],axis=1)
    flat=np.maximum((frames<30).mean(axis=(1,2)),(frames>225).mean(axis=(1,2)))
    detail=(np.abs(np.diff(frames,axis=2))>28).mean(axis=(1,2))
    cards=(motion<1.5)&((flat>.8)|((border.std(axis=1)<7)&(detail<.1)))
    if cards.mean()>.45:return []  # Posters and static performances can be valid footage.
    intervals=[];start=None
    for i,card in enumerate(np.r_[cards,False]):
        if card and start is None:start=i
        if not card and start is not None:
            if (i-start)/fps>=2:intervals.append([max(0,start/fps-.25),min(len(frames)/fps,i/fps+.25)])
            start=None
    return intervals


def musical_grid(path):
    """Find repeatable pulses and low-energy phrase breaks from 50 ms RMS frames."""
    with wave.open(str(path)) as audio:
        rate=audio.getframerate();energy=[]
        while block:=audio.readframes(round(rate*.05)):
            samples=np.frombuffer(block,dtype='<i2').astype(np.float32)
            energy.append(float(np.sqrt(np.mean(samples*samples))))
    if len(energy)<40:return {'boundaries':[],'tempo':None}
    levels=np.asarray(energy);smooth=np.convolve(levels,np.ones(5)/5,mode='same')
    # Analyse up to 120 seconds around the loudest part, avoiding long silent leaders.
    peak=int(np.argmax(smooth));lo=max(0,min(peak-600,len(levels)-2400));sample=levels[lo:lo+2400]
    onset=np.maximum(0,np.diff(np.log1p(sample),prepend=0));onset-=onset.mean()
    scores=[float(np.dot(onset[lag:],onset[:-lag]))/max(1,len(onset)-lag) for lag in range(6,21)]
    period=(6+int(np.argmax(scores)))*.05 if max(scores,default=0)>.0001 else None
    boundaries=[]
    if period:
        lag=round(period/.05);phase=max(range(lag),key=lambda p:float(np.maximum(onset[p::lag],0).sum()))
        # Four-bar group boundaries; whole groups are preferred over arbitrary seconds.
        origin=lo*.05+phase*.05;bar=period*16
        boundaries.extend(round(origin+k*bar,3) for k in range(math.floor(-origin/bar),math.ceil((len(levels)*.05-origin)/bar)+1) if 0<=origin+k*bar<len(levels)*.05)
    threshold=float(np.percentile(smooth,25))
    for i in range(10,len(smooth)-10):
        if smooth[i]<=threshold and smooth[i]<=smooth[i-10:i+11].min() and (not boundaries or all(abs(i*.05-b)>1 for b in boundaries[-4:])):boundaries.append(round(i*.05,3))
    return {'boundaries':sorted(set(boundaries)),'tempo':round(60/period,1) if period else None}


def safe_intervals(duration, excluded):
    result=[];cursor=0
    for a,b in sorted(excluded):
        a=max(0,min(duration,a));b=max(a,min(duration,b))
        if a>cursor:result.append((cursor,a))
        cursor=max(cursor,b)
    if cursor<duration:result.append((cursor,duration))
    return result


def choose_regions(duration,target,energies,excluded=(),boundaries=()):
    safe=safe_intervals(duration,excluded)
    total=sum(b-a for a,b in safe)
    if total<4: safe=[(0,duration)];total=duration
    prefix=np.r_[0,np.cumsum(energies)]
    peak=max(energies,default=1) or 1
    proposals=[]
    for index in range(4):
        qlo,qhi=index*total/4,(index+1)*total/4;cursor=0;spans=[]
        for a,b in safe:
            left=max(qlo,cursor);right=min(qhi,cursor+b-a)
            if right-left>=1:spans.append((a+left-cursor,a+right-cursor))
            cursor+=b-a
        if not spans:spans=[max(safe,key=lambda s:s[1]-s[0])]
        best=None
        for low,high in spans:
            wanted=min(target,high-low,90);minimum=max(1,wanted*.7)
            points=sorted({low,high,*[t for t in boundaries if low<=t<=high]})
            starts=sorted({low,*[float(t) for t in range(math.ceil(low),math.floor(high-minimum)+1)],*[p for p in points if p<=high-minimum]})
            for start in starts:
                ideal=min(high,start+wanted)
                ends={ideal,*points[bisect_left(points,start+minimum):bisect_right(points,min(high,start+wanted*1.3,start+90))]}
                for end in ends:
                    if end-start<1:continue
                    i,j=max(0,int(start)),min(len(energies),math.ceil(end))
                    power=float(prefix[j]-prefix[i])/max(1,j-i)/peak if i<len(energies) else 0
                    aligned=sum((lambda i:i<len(points) and points[i]<=t+.08)(bisect_left(points,t-.08)) for t in (start,end))
                    score=power+.13*aligned-.2*abs(end-start-wanted)/max(1,wanted)
                    # Stable ordering makes repeated imports reproducible.
                    candidate=(score,-start,start,end,low,high)
                    if best is None or candidate>best:best=candidate
        if best is None:
            low,high=max(safe,key=lambda s:s[1]-s[0]);a,b=low,high
        else:
            _,_,a,b,low,high=best
        proposals.append({'start':round(a,3),'end':round(b,3),'suggested_bounds':[round(low,3),round(high,3)]})
    return proposals


def refine_vocal_boundaries(data):
    words=sorted([w for c in data.get('cues',[]) for w in c.get('words',[])],key=lambda w:w['start'])
    if not words:return
    starts=[w['start']-.08 for i,w in enumerate(words) if i==0 or w['start']-words[i-1]['end']>.32]
    ends=[w['end']+.12 for i,w in enumerate(words) if i==len(words)-1 or words[i+1]['start']-w['end']>.32]
    for reel in data['reels']:
        if reel.get('cuts_edited') or reel.get('caption_edits') is not None or reel['render']['status']!='idle':continue
        low,high=reel.get('suggested_bounds',[0,data['duration']]);a,b=reel['start'],reel['end']
        for side,candidates in [('start',starts),('end',ends)]:
            current=a if side=='start' else b
            options=[t for t in candidates if low<=t<=high and abs(t-current)<=4 and (1<=b-t<=90 if side=='start' else 1<=t-a<=90)]
            if options:chosen=min(options,key=lambda t:abs(t-current))
            else:
                word=next((w for w in words if w['start']<current<w['end']),None)
                chosen=(word['start']-.08 if side=='start' else word['end']+.12) if word else current
            chosen=max(low,min(high,chosen))
            if side=='start':a=chosen
            else:b=chosen
        if 1<=b-a<=90 and not any(a<y and b>x for x,y in data.get('selection',{}).get('excluded',[])):
            reel.update(start=round(a,3),end=round(b,3),revision=reel['revision']+1)
