#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import os
import re
import sys
import tarfile
import time
from collections import defaultdict
from urllib.parse import urljoin
from urllib.request import urlopen, Request
import tempfile

DARTMOUTH_BASE = "https://knots.dartmouth.edu/~rmaguire/knot_data/jones/"
DARTMOUTH_INDEX = "https://knots.dartmouth.edu/jones_polynomial/"
KATLAS_BASE = "https://katlas.org/Data/"

DARTMOUTH_ARCHIVES = [
    ("03a_torus_jones.tar.xz",   "3a torus"),
    ("04a_hyp_jones.tar.xz",     "4a hyp"),
    ("05a_hyp_jones.tar.xz",     "5a hyp"),
    ("05a_torus_jones.tar.xz",   "5a torus"),
    ("06a_hyp_jones.tar.xz",     "6a hyp"),
    ("07a_hyp_jones.tar.xz",     "7a hyp"),
    ("07a_torus_jones.tar.xz",   "7a torus"),
    ("08a_hyp_jones.tar.xz",     "8a hyp"),
    ("08n_hyp_jones.tar.xz",     "8n hyp"),
    ("08n_torus_jones.tar.xz",   "8n torus"),
    ("09a_hyp_jones.tar.xz",     "9a hyp"),
    ("09a_torus_jones.tar.xz",   "9a torus"),
    ("09n_hyp_jones.tar.xz",     "9n hyp"),
    ("10a_hyp_jones.tar.xz",     "10a hyp"),
    ("10n_hyp_jones.tar.xz",     "10n hyp"),
    ("10n_torus_jones.tar.xz",   "10n torus"),
    ("11a_hyp_jones.tar.xz",     "11a hyp"),
    ("11a_torus_jones.tar.xz",   "11a torus"),
    ("11n_hyp_jones.tar.xz",     "11n hyp"),
    ("12a_hyp_jones.tar.xz",     "12a hyp"),
    ("12n_hyp_jones.tar.xz",     "12n hyp"),
    ("13a_hyp_jones.tar.xz",     "13a hyp"),
    ("13a_torus_jones.tar.xz",   "13a torus"),
    ("13n_hyp_jones.tar.xz",     "13n hyp"),
    ("13n_satellite_jones.tar.xz","13n satellite"),
    ("14a_hyp_jones.tar.xz",     "14a hyp"),
    ("14n_hyp_jones.tar.xz",     "14n hyp"),
    ("14n_satellite_jones.tar.xz","14n satellite"),
    ("14n_torus_jones.tar.xz",   "14n torus"),
    ("15a_hyp_jones.tar.xz",     "15a hyp"),
    ("15a_torus_jones.tar.xz",   "15a torus"),
    ("15n_hyp_jones.tar.xz",     "15n hyp"),
    ("15n_satellite_jones.tar.xz","15n satellite"),
    ("15n_torus_jones.tar.xz",   "15n torus"),
    ("16a_hyp_jones.tar.xz",     "16a hyp"),
    ("16n_hyp_jones.tar.xz",     "16n hyp"),
    ("16n_satellite_jones.tar.xz","16n satellite"),
    ("16n_torus_jones.tar.xz",   "16n torus"),
    ("17a_hyp_jones.tar.xz",     "17a hyp"),
    ("17a_torus_jones.tar.xz",   "17a torus"),
    ("17n_hyp_jones.tar.xz",     "17n hyp"),
    ("17n_satellite_jones.tar.xz","17n satellite"),
    ("18a_hyp_jones.tar.xz",     "18a hyp"),
    ("18n_hyp_jones.tar.xz",     "18n hyp"),
    ("18n_satellite_jones.tar.xz","18n satellite"),
    ("19a_hyp_jones.tar.xz",     "19a hyp"),
    ("19a_torus_jones.tar.xz",   "19a torus"),
    #("19n_hyp_jones.tar.xz",     "19n hyp"),
    #("19n_satellite_jones.tar.xz","19n satellite"),
]

KATLAS_RDF = [
    ("Rolfsen.rdf.gz", "Rolfsen table (<=10 crossings)"),
    ("Knots11.rdf.gz", "11 crossings"),
    ("Knots12.rdf.gz", "12 crossings"),
    ("Knots13.rdf.gz", "13 crossings"),
    ("Knots14.rdf.gz", "14 crossings"),
    ("Knots15.rdf.gz", "15 crossings"),
]

def http_get_streaming(url, target_path, retry=3, chunk=1<<16):
    """Download directly to disk with progress reporting."""
    hdrs = {"User-Agent": "JonesScraper/0.5 (+https://knots.dartmouth.edu/)"}
    last_exc = None
    for attempt in range(retry):
        try:
            with urlopen(Request(url, headers=hdrs)) as r:
                total = r.headers.get('Content-Length')
                total_mb = int(total) / (1024*1024) if total else None
                
                with open(target_path, 'wb') as f:
                    downloaded = 0
                    last_report = time.time()
                    while True:
                        b = r.read(chunk)
                        if not b:
                            break
                        f.write(b)
                        downloaded += len(b)
                        
                        # Progress report every 2 seconds
                        now = time.time()
                        if now - last_report > 2:
                            if total_mb:
                                print(f"  [{downloaded/(1024*1024):.1f}/{total_mb:.1f} MB]", 
                                      file=sys.stderr, end='\r')
                            else:
                                print(f"  [{downloaded/(1024*1024):.1f} MB]", 
                                      file=sys.stderr, end='\r')
                            last_report = now
                
                if total_mb:
                    print(f"  [{total_mb:.1f}/{total_mb:.1f} MB] ✓", file=sys.stderr)
                return target_path
        except Exception as e:
            last_exc = e
            if attempt < retry - 1:
                print(f"  Retry {attempt+1}/{retry}...", file=sys.stderr)
                time.sleep(2)
    raise RuntimeError(f"Failed to download {url}: {last_exc}")

# -------- Polynomial parsing --------
from fractions import Fraction

_HALFPOW_PATTERNS = [
    (r'1\s*/\s*\\?sqrt\s*\{\s*q\s*\}', 'q^(-1/2)'),
    (r'\\frac\s*\{\s*1\s*\}\s*\{\s*\\?sqrt\s*\{\s*q\s*\}\s*\}', 'q^(-1/2)'),
    (r'\\?sqrt\s*\{\s*q\s*\}', 'q^(1/2)'),
    (r'1\s*/\s*\\?sqrt\s*\{\s*x\s*\}', 'x^(-1/2)'),
    (r'\\frac\s*\{\s*1\s*\}\s*\{\s*\\?sqrt\s*\{\s*x\s*\}\s*\}', 'x^(-1/2)'),
    (r'\\?sqrt\s*\{\s*x\s*\}', 'x^(1/2)'),
]

def _preprocess_half_powers(s: str) -> str:
    s = s.replace("\n", " ")
    for pat, rep in _HALFPOW_PATTERNS:
        s = re.sub(pat, rep, s)
    s = re.sub(r'([qx])\^\{\s*([+\-]?\d+)\s*/\s*(\d+)\s*\}', r'\1^(\2/\3)', s)
    s = re.sub(r'([qx])\^\{\s*([+\-]?\d+)\s*\}', r'\1^\2', s)
    return s

def parse_poly_string_to_dict(s: str):
    """Parse Jones polynomial allowing integer or rational exponents."""
    s = s.strip()
    if "," in s:
        for cand in reversed(s.split(",")):
            if re.search(r"[qQxX]", cand):
                s = cand.strip()
                break

    s = _preprocess_half_powers(s)
    for tok in ("<math>", "</math>", "\\left", "\\right"):
        s = s.replace(tok, "")
    s = (s.replace("\\", "")
           .replace("{", "").replace("}", "")
           .replace("(", "").replace(")", "")
           .replace("âˆ'", "-").replace("Â·", "*")
           .replace(" ", ""))
    if s and s[0] not in "+-":
        s = "+" + s

    TERM_RE = re.compile(r"""
        (?P<sgn>[+\-])
        (?:
          (?:(?P<coef>\d*)\*?(?P<var>[qQxX])(?:\^(?P<exp>([+\-]?\d+)(?:/\d+)?))?)
          | (?P<const>\d+)
        )
    """, re.VERBOSE)

    acc = defaultdict(int)
    denoms = set([1])
    i = 0
    while i < len(s):
        m = TERM_RE.match(s, i)
        if not m:
            i += 1
            continue
        sgn = -1 if m.group("sgn") == "-" else 1
        if m.group("const") is not None:
            c, e = int(m.group("const")), Fraction(0, 1)
        else:
            coef = m.group("coef")
            c = 1 if coef in (None, "") else int(coef)
            exp = m.group("exp")
            if exp in (None, ""):
                e = Fraction(1, 1)
            else:
                e = Fraction(int(exp.split("/")[0]), int(exp.split("/")[1])) if "/" in exp else Fraction(int(exp), 1)
            denoms.add(e.denominator)
        acc[e] += sgn * c
        i = m.end()

    from math import gcd
    def lcm(a,b): return a*b // gcd(a,b)
    L = 1
    for d in denoms: L = lcm(L,d)

    out = {}
    for e_frac, c in acc.items():
        if c == 0: continue
        e_int = int(e_frac * L)
        out[e_int] = out.get(e_int, 0) + c
    return {int(e): int(c) for e,c in out.items() if c != 0}

# -------- Line-by-line streaming parser --------
_LABEL_RX = re.compile(r'^\s*([Kk]?\d+[an]?[_-]\d+)\s*[,:]?\s*(.+)$')

class LineReader:
    """Wrapper to read tar member line-by-line with buffering."""
    def __init__(self, fileobj, buffer_size=1<<16):
        self.fileobj = fileobj
        self.buffer_size = buffer_size
        self.buffer = b''
        self.finished = False
    
    def __iter__(self):
        return self
    
    def __next__(self):
        while True:
            # Look for newline in buffer
            idx = self.buffer.find(b'\n')
            if idx >= 0:
                line = self.buffer[:idx]
                self.buffer = self.buffer[idx+1:]
                try:
                    return line.decode('utf-8', 'replace')
                except:
                    continue  # Skip bad lines
            
            # Need more data
            if self.finished:
                if self.buffer:
                    line = self.buffer
                    self.buffer = b''
                    try:
                        return line.decode('utf-8', 'replace')
                    except:
                        pass
                raise StopIteration
            
            chunk = self.fileobj.read(self.buffer_size)
            if not chunk:
                self.finished = True
            else:
                self.buffer += chunk

def parse_dartmouth_tarxz_streaming(tar_path, output_file):
    """
    Stream-parse tar.xz line-by-line without loading full members into memory.
    Returns count of knots processed.
    """
    count = 0
    last_report = time.time()
    member_count = 0
    member_idx = 0
    
    print(f"  [Opening tar archive and streaming members...]", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        with tarfile.open(tar_path, mode="r|xz") as tf:  # Note: "r|xz" for streaming!
            # Process members one-by-one as they're extracted
            for m in tf:
                if not m.isfile():
                    continue
                    
                member_idx += 1
                f = tf.extractfile(m)
                if f is None: 
                    continue
                
                stem = os.path.splitext(os.path.basename(m.name))[0]
                member_count = 0
                
                # Show which member we're processing (no total count since streaming)
                print(f"  [File #{member_idx}: {stem[:50]}... | Total: {count:,} knots]", 
                      file=sys.stderr, end='\r')
                sys.stderr.flush()
                
                # Process line-by-line using streaming reader
                reader = LineReader(f, buffer_size=1<<17)  # 128KB buffer
                for idx, line in enumerate(reader, start=1):
                    line = line.strip()
                    if not line or not re.search(r"[qQxX]", line):
                        continue
                    
                    mo = _LABEL_RX.match(line)
                    if mo:
                        label, poly_s = mo.group(1), mo.group(2).strip()
                    else:
                        if "," in line:
                            left, right = line.split(",", 1)
                            if re.match(r'^[Kk]?\d+[an]?[_-]\d+$', left.strip()):
                                label = left.strip()
                                poly_s = right.strip()
                            else:
                                label = f"{stem}:{idx}"
                                poly_s = right.strip()
                        else:
                            label = f"{stem}:{idx}"
                            poly_s = line
                    
                    try:
                        coeffs = parse_poly_string_to_dict(poly_s)
                        if coeffs:
                            # Write entry immediately
                            entry = {
                                "coeffs": {str(int(e)): int(c) 
                                         for e, c in sorted(coeffs.items())}
                            }
                            output_file.write(f'  "{label}": {json.dumps(entry)},\n')
                            count += 1
                            member_count += 1
                            
                            # Progress indicator every 5k knots or 2 seconds
                            now = time.time()
                            if count % 5000 == 0 or now - last_report > 2:
                                print(f"  [File #{member_idx}: {stem[:50]}... | Total: {count:,} knots]", 
                                      file=sys.stderr, end='\r')
                                sys.stderr.flush()
                                last_report = now
                    except Exception as e:
                        # Skip unparseable entries silently
                        pass
                
                # Report member completion
                if member_count > 0:
                    print(f"  [File #{member_idx}: {stem[:50]}... | +{member_count:,} knots | Total: {count:,}]", 
                          file=sys.stderr)
                    sys.stderr.flush()
    
    except Exception as e:
        print(f"\n  [ERROR: {e}]", file=sys.stderr)
        raise
    
    return count

# -------- Katlas parser --------
def parse_katlas_rdf_gz(buf):
    import gzip
    data = gzip.GzipFile(fileobj=buf, mode="rb").read().decode("utf-8", "replace")
    triple_re = re.compile(
        r'<knot:([^>]+)>\s+<invariant:([^>]+)>\s+"(.*?)"\s*(?:\^\^[^@.]*)?(?:@[a-zA-Z\-]+)?\s*\.',
        re.IGNORECASE | re.DOTALL
    )
    for mk in triple_re.finditer(data):
        label, prop, val = mk.group(1), mk.group(2), mk.group(3)
        pl = prop.lower()
        if "jones" not in pl or "polynomial" not in pl: 
            continue
        if "colored" in pl or "coloured" in pl:
            continue
        coeffs = parse_poly_string_to_dict(val)
        yield label, coeffs

# -------- Main scraping functions --------
def within_crossing_range(label, lo, hi):
    m = re.match(r'^[Kk]?(\d+)[a-z]?[_-]', label)
    if not m:
        m = re.match(r'^(\d+)[_-]', label)
    if not m:
        return True
    n = int(m.group(1))
    return (lo is None or n >= lo) and (hi is None or n <= hi)

def scrape_dartmouth_streaming(output_file, crossings, verbose=True):
    """Download and stream-parse Dartmouth archives."""
    lo, hi = crossings
    total_count = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, desc in DARTMOUTH_ARCHIVES:
            m = re.match(r'^(\d+)', fname)
            if not m: 
                continue
            n = int(m.group(1))
            if (lo is not None and n < lo) or (hi is not None and n > hi):
                continue
            
            url = urljoin(DARTMOUTH_BASE, fname)
            if verbose:
                print(f"\n[download] {fname} ({desc})", file=sys.stderr)
            
            # Download to temp file
            tar_path = os.path.join(tmpdir, fname)
            http_get_streaming(url, tar_path)
            
            if verbose:
                print(f"[parsing ] {fname}", file=sys.stderr)
            
            # Stream parse and write
            count = parse_dartmouth_tarxz_streaming(tar_path, output_file)
            total_count += count
            
            if verbose:
                print(f"[done    ] {fname}: {count:,} knots total\n", file=sys.stderr)
            
            # Clean up immediately
            os.remove(tar_path)
    
    return total_count

def scrape_katlas(output_file, crossings, verbose=True):
    """Scrape Katlas (smaller files, use in-memory)."""
    lo, hi = crossings
    count = 0
    
    for fname, desc in KATLAS_RDF:
        url = urljoin(KATLAS_BASE, fname)
        if verbose:
            print(f"\n[download] {fname} ({desc})", file=sys.stderr)
        
        buf = http_get_streaming_to_memory(url)
        
        for label, coeffs in parse_katlas_rdf_gz(buf):
            if within_crossing_range(label, lo, hi):
                entry = {
                    "coeffs": {str(int(e)): int(c) 
                             for e, c in sorted(coeffs.items())}
                }
                output_file.write(f'  "{label}": {json.dumps(entry)},\n')
                count += 1
        
        if verbose:
            print(f"[parsed  ] {fname}: {count:,} knots", file=sys.stderr)
    
    return count

def http_get_streaming_to_memory(url, retry=3, chunk=1<<20):
    """For smaller files that fit in memory."""
    hdrs = {"User-Agent": "JonesScraper/0.5 (+https://knots.dartmouth.edu/)"}
    last_exc = None
    for _ in range(retry):
        try:
            with urlopen(Request(url, headers=hdrs)) as r:
                buf = io.BytesIO()
                while True:
                    b = r.read(chunk)
                    if not b:
                        break
                    buf.write(b)
                buf.seek(0)
                return buf
        except Exception as e:
            last_exc = e
            time.sleep(1.5)
    raise RuntimeError(f"Failed to download {url}: {last_exc}")

def parse_crossings_arg(s):
    if s is None:
        return (None, None)
    if "-" in s:
        lo, hi = s.split("-", 1)
        lo = int(lo) if lo else None
        hi = int(hi) if hi else None
    else:
        lo = hi = int(s)
    return (lo, hi)

def main():
    ap = argparse.ArgumentParser(description="Build a Jones-polynomial JSON from public datasets (streaming version).")
    ap.add_argument("--out", required=True, help="Path to output JSON file.")
    ap.add_argument("--source", choices=["dartmouth", "katlas", "both"], default="both",
                    help="Which source(s) to pull from.")
    ap.add_argument("--crossings", default="0-19",
                    help="Crossing range to include, e.g., '0-10', '11-19', '12'.")
    args = ap.parse_args()

    lo, hi = parse_crossings_arg(args.crossings)

    # Write JSON structure incrementally
    with open(args.out, 'w', encoding='utf-8') as f:
        # Write metadata
        meta = {
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sources": [
                {"name": "Knots at Dartmouth", "index": DARTMOUTH_INDEX, "base": DARTMOUTH_BASE},
                {"name": "Knot Atlas Take-Home DB", "base": KATLAS_BASE},
            ],
            "normalization": "V_unknot = 1",
            "variable": "q (integer-power)",
        }
        
        f.write('{\n')
        f.write(f'  "meta": {json.dumps(meta, indent=2).replace(chr(10), chr(10) + "  ")},\n')
        f.write('  "data": {\n')
        
        total = 0
        
        if args.source in ("dartmouth", "both"):
            total += scrape_dartmouth_streaming(f, (lo, hi), verbose=True)
        
        if args.source in ("katlas", "both"):
            total += scrape_katlas(f, (lo, hi), verbose=True)
        
        # Remove trailing comma and close
        f.seek(f.tell() - 2)  # Back up over last ",\n"
        f.write('\n')
        f.write('  }\n')
        f.write('}\n')
    
    print(f"\n[complete] Wrote {args.out} with {total:,} knots", file=sys.stderr)

if __name__ == "__main__":
    main()