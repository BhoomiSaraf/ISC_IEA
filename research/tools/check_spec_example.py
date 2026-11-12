# Independent check of algorithm_design.md §12.1 (toy S-box; not project code)
def bounded(words, s):
    it = iter(words)
    w = next(it); m = w*s; l = m % 2**32
    if l < s:
        t = (2**32 - s) % s
        while l < t:
            w = next(it); m = w*s; l = m % 2**32
    return m >> 32
S = lambda v: (5*v + 3) % 256
Si = lambda w: (205*(w - 3)) % 256
assert all(Si(S(v)) == v for v in range(256))
p = [10, 20, 30]; n = 3; ivf, ivb = 7, 9; a = [1, 2, 3]; b = [4, 5, 6]
words = [0x80000000, 0xC0000000]
pi = list(range(n)); wi = 0
for i in range(n-1, 0, -1):
    j = bounded([words[wi]], i+1); wi += 1
    pi[i], pi[j] = pi[j], pi[i]
q = [p[pi[k]] for k in range(n)]
u = []; prev = ivf
for k in range(n): prev = S((q[k] + prev + a[k]) % 256); u.append(prev)
c = [0]*n; nxt = ivb
for k in range(n-1, -1, -1): c[k] = S((u[k] + nxt + b[k]) % 256); nxt = c[k]
print("pi", pi, "q", q, "u", u, "c", c)
cc = c + [ivb]; ud = [(Si(cc[k]) - cc[k+1] - b[k]) % 256 for k in range(n)]
uu = [ivf] + ud; qd = [(Si(uu[k+1]) - uu[k] - a[k]) % 256 for k in range(n)]
pd = [None]*n
for k in range(n): pd[pi[k]] = qd[k]
print("decrypted u", ud, "q", qd, "p", pd, "OK", pd == p)
# rejection example
s=3; t=(2**32-s)%s; print("t for s=3:", t, "; w=0 rejected:", (0*s)%2**32 < t)
