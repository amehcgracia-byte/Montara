#!/usr/bin/env python3
"""Snapshot of the latest Montara session on this server, to paste to Claude when something looks stuck.

    python3 deploy/vm/diagnose.py      (the Mac command montara-diagnose runs it as jm)
"""
import json, glob, os, subprocess, time
home = os.path.expanduser('~')
rev = subprocess.run(['git', '-C', f'{home}/montara', 'log', '--oneline', '-1'], capture_output=True, text=True).stdout.strip()
print('montara:', rev)
path = max(glob.glob(f'{home}/montara-data/Sessions/*/session.json'), key=os.path.getmtime)
work = os.path.dirname(path); d = json.load(open(path))
print('session:', os.path.basename(work), '| status:', d.get('status'), '| error:', d.get('error'))
print('progress:', d.get('progress'))
sel = [s for s in d.get('songs', []) if s.get('selected')]
print(f"songs selected: {len(sel)} | results: {len(d.get('results', []))} | previews: {bool(d.get('previews'))}")
print('original ranges received (files):', len(glob.glob(f'{work}/originals/*.json')), '| legacy:', len(d.get('originals') or {}))
print('results dir:', sorted(os.listdir(f'{work}/results')) if os.path.isdir(f'{work}/results') else '-')
print('session.json age (s):', int(time.time() - os.path.getmtime(path)))
print('--- processes')
print(subprocess.run("ps -eo pid,etimes,pcpu,rss,args --sort=-pcpu | grep -E 'mixer_adapter|ffmpeg|gunicorn' | grep -v grep | head -12 | cut -c1-160", shell=True, capture_output=True, text=True).stdout)
print('--- worker.log (last 25)')
print(subprocess.run(f"tail -25 {work}/worker.log | cut -c1-220", shell=True, capture_output=True, text=True).stdout)
print('--- web log (last 8 requests)')
print(subprocess.run("XDG_RUNTIME_DIR=/run/user/$(id -u) journalctl --user -u montara --since '-15 min' --no-pager | grep -E 'GET|POST|PUT' | tail -8 | cut -c60-220", shell=True, capture_output=True, text=True).stdout)
print('uptime:', subprocess.run('uptime', capture_output=True, text=True).stdout.strip())
