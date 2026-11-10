#!/bin/bash
# I15 opt-in lab ONLY. Never run on user or production project data.
set -euo pipefail
if [[ "${1-}" != --probe && "${1-}" != --worker ]] || [[ "$#" != 7 ]]; then
  echo 'I15 lab requires mode, root, workspace, repo, engine, venv, python-install-root' >&2; exit 64
fi
mode="$1"; root="$2"; workspace="$3"; repo="$4"; engine="$5"; venv="$6"; python_runtime="$7"
for directory in "$repo" "$engine" "$venv" "$python_runtime"; do
  [[ "$directory" == /* && -d "$directory" && ! -L "$directory" ]] || exit 66
done
case "$root" in /tmp/montara-i15-lab.*) ;; *) echo 'Unsafe temp root' >&2; exit 64;; esac
case "$workspace" in /tmp/montara-i15-workspace.*) ;; *) echo 'Unsafe fixture' >&2; exit 64;; esac
[[ -d "$root" && -d "$workspace" && ! -L "$root" && ! -L "$workspace" ]] || exit 65
mount --make-rprivate /
mount -t tmpfs -o size=96m,mode=0700,nosuid,nodev tmpfs "$root"
for name in usr opt tmp home dev etc workspace; do mkdir -p "$root/$name"; done
ln -s usr/bin "$root/bin"; ln -s usr/lib "$root/lib"; ln -s usr/lib64 "$root/lib64"
mount --bind /usr "$root/usr"
mount -o remount,bind,ro "$root/usr"
for item in "$repo" "$engine" "$venv" "$python_runtime" /etc/ssl/certs; do
  dest="$root$item"
  mkdir -p "$dest"
  mount --bind "$item" "$dest"
  mount -o remount,bind,ro "$dest"
done
for item in null urandom zero; do touch "$root/dev/$item"; mount --bind "/dev/$item" "$root/dev/$item"; done
mount --bind "$workspace" "$root/workspace"
mount -t tmpfs -o size=64m,mode=1777,nosuid,nodev tmpfs "$root/tmp"
# Simple, conservative laboratory limits. These are not cgroup CPU/RAM/PID quotas.
ulimit -n 256
ulimit -v 4194304
ulimit -t 60
export PYTHONPATH="$repo" HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
if [[ "$mode" == --worker ]]; then
  exec chroot "$root" /usr/bin/setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all "$venv/bin/python" -u -m urano.engine_worker_process --engine-dir "$engine" --data-root /workspace
fi
export MONTARA_I15_ENGINE="$engine"
exec chroot "$root" /usr/bin/setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all "$venv/bin/python" -c 'import sys,os,socket; sys.path.insert(0,os.environ["MONTARA_I15_ENGINE"]); from core.project import new_project_document; print("sandbox_python_ok",sys.version.split()[0]); print("host_home_hidden",not os.path.exists(os.environ.get("MONTARA_I15_HOST_HOME_TEST","/nonexistent-host-home-sentinel"))); print("foreign_owner_hidden",not os.path.exists(os.environ.get("MONTARA_I15_FOREIGN_OWNER_TEST","/nonexistent-foreign-owner-sentinel"))); print("proc_not_mounted",not os.path.exists("/proc/self/status")); print("real_engine_import",bool(new_project_document)); print("engine_read_only",bool(os.statvfs(os.environ["MONTARA_I15_ENGINE"]).f_flag & os.ST_RDONLY)); s=socket.socket(); s.settimeout(1); print("network_blocked",s.connect_ex(("1.1.1.1",443))!=0); s.close()'
