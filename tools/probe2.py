import re, os, sys
h = open(os.path.expanduser('~/probe/' + sys.argv[1] + '.html')).read()
def seg(start_pat, n):
    m = re.search(start_pat, h)
    if not m: print('NENALEZENO', start_pat); return
    print('=====', start_pat, '@', m.start()); print(re.sub(r'\s+', ' ', h[m.start():m.start()+n]))
for pat in [a for a in sys.argv[3:] if not a.startswith("--")][:sys.argv.index("--before")-3 if "--before" in sys.argv else None]:
    seg(pat, int(sys.argv[2]))
if '--before' in sys.argv:
    i = sys.argv.index('--before'); pat, n = sys.argv[i + 1], int(sys.argv[i + 2])
    m = re.search(pat, h)
    print('=== BEFORE', pat); print(re.sub(r'\s+', ' ', h[max(0, m.start() - n):m.start() + 100]) if m else 'NENALEZENO')
