"""I26 trusted-controller-only local Unix client (never from Owner web)."""
import argparse
import json
import socket

SOCKET="/run/montara-i26-broker/control.sock"

def request(message):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(38)
        sock.connect(SOCKET)
        sock.sendall(json.dumps(message,separators=(",",":")).encode())
        received=sock.recv(8192)
    if not received:raise RuntimeError("Broker unavailable")
    return json.loads(received)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("op",choices=["ping","demo_start","stop"])
    parser.add_argument("--job-id")
    parser.add_argument("--generation",type=int)
    args=parser.parse_args()
    body={"op":args.op}
    if args.op=="stop":
        if args.job_id is None or args.generation is None:
            parser.error("stop requires job id and generation")
        body.update(job_id=args.job_id,generation=args.generation)
    print(json.dumps(request(body),sort_keys=True))

if __name__=="__main__":
    main()

