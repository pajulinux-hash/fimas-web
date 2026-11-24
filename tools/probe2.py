import re, os, sys
h = open(os.path.expanduser('~/probe/' + sys.argv[1] + '.html')).read()
def seg(start_pat, n):
    m = re.search(start_pat, h)
    if not m: print('NENALEZENO', start_pat); return
    print('=====', start_pat, '@', m.start()); print(re.sub(r'\s+', ' ', h[m.start():m.start()+n]))
for pat in sys.argv[3:]:
    seg(pat, int(sys.argv[2]))
