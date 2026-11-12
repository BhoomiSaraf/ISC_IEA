"""Read-only SHA-256 reconciliation of ISC_PBL, sine_chebyshev_ikeda_analysis and the GitHub repo checkout.
Usage: python reconcile.py --a ISC_PBL_DIR --b CIPHER_DIR --g REPO_DIR --out OUT_DIR
GitHub layout maps ISC_PBL/* -> isc_pbl/* ; everything else is same relative path as CIPHER_DIR."""
import argparse, hashlib, json, csv, pathlib, collections
SKIP={'.git','__pycache__','.pytest_cache','.venv','.mypy_cache','.ruff_cache'}
def idx(root):
    r={}
    for p in pathlib.Path(root).rglob('*'):
        if p.is_file() and not (set(p.relative_to(root).parts)&SKIP):
            r[p.relative_to(root).as_posix()]=p
    return r
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()
ap=argparse.ArgumentParser();[ap.add_argument('--'+k,required=True) for k in 'abgo' if k!='o'];ap.add_argument('--out',required=True);a=ap.parse_args()
A,B,G=idx(a.a),idx(a.b),idx(a.g)
G_pbl={k[len('isc_pbl/'):]:v for k,v in G.items() if k.startswith('isc_pbl/')}
G_main={k:v for k,v in G.items() if not k.startswith('isc_pbl/')}
rows=[]
def cls(path):
    if '__pycache__' in path or path.endswith('.pyc'):return 'CACHE'
    if 'backup' in path.lower():return 'HISTORICAL_BACKUP'
    return None
for k in sorted(set(A)|set(G_pbl)):
    ha=sha(A[k]) if k in A else None; hg=sha(G_pbl[k]) if k in G_pbl else None
    c='IDENTICAL' if ha and ha==hg else 'DIFFERENT' if ha and hg else 'PRESENT_ONLY_IN_ISC_PBL' if ha else 'PRESENT_ONLY_IN_GITHUB'
    rows.append(('ISC_PBL<->GitHub isc_pbl/',k,ha,hg,c))
for k in sorted(set(B)|set(G_main)):
    hb=sha(B[k]) if k in B else None; hg=sha(G_main[k]) if k in G_main else None
    c='IDENTICAL' if hb and hb==hg else 'DIFFERENT' if hb and hg else 'PRESENT_ONLY_IN_CIPHER_REPO' if hb else 'PRESENT_ONLY_IN_GITHUB'
    rows.append(('CipherRepo<->GitHub root',k,hb,hg,c))
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
with open(out/'reconciliation_matrix.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['comparison','path','sha256_source','sha256_github','classification']);w.writerows(rows)
print(collections.Counter((r[0],r[4]) for r in rows))
for r in rows:
    if r[4]!='IDENTICAL' and not r[1].startswith('third_party/'):print(r[0][:8],r[4],r[1])
print('third_party non-identical:',sum(1 for r in rows if r[4]!='IDENTICAL' and r[1].startswith('third_party/')))
