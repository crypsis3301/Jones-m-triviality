#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultra-fast JSON splitting: Split by byte position, then fix boundaries.
Never reads the middle of chunks - only beginning/end to fix JSON formatting.
"""

import json
import sys
from pathlib import Path
from multiprocessing import Pool, cpu_count
from collections import defaultdict
import ijson
import time
from JVP import jones_to_Vxp
from BLexpansion import taylor_from_jones, Fraction

Jm_jvp = lambda A, B: [q for q, c in enumerate([A.get(i, 0) + B.get(i, 0) for i in range(max(A | B) + 1)][1:]) if c != 0][0] + 1
Jm_bl = lambda c: [k for k,i in enumerate(c[1:]) if i != Fraction(0,1)][0]+1    

Jtransform = {
    "JVP": lambda coeff: Jm_jvp(*jones_to_Vxp(coefs=coeff)),
    "BL": lambda coeff: Jm_bl(taylor_from_jones(coefs=coeff, n=11))
}

sample_interval = 1
min_m = 1


def find_record_boundary_forward(f, max_search=100000):
    """
    From current position, find the next complete record boundary.
    Returns position right after a record ends (after '},' or '}')
    
    Since we start in the middle of data, we don't know initial depth.
    Strategy: Track depth changes, look for when we return to baseline (complete record).
    """
    depth = 0
    in_string = False
    escape = False
    start_pos = f.tell()
    baseline_found = False

    while f.tell() - start_pos < max_search:
        byte = f.read(1)
        if byte.isalpha() or byte == b'_':
            while byte != b'"':
                f.seek(-2,1)
                byte = f.read(1)
            
            return f.tell()
    
    return None


def find_record_boundary_backward(f, max_search=100000):
    """
    From current position, find the previous complete record boundary.
    Returns position right after the previous record (after '},' or '}')
    """
    start_pos = f.tell()
    search_start = max(0, start_pos - max_search)
    f.seek(search_start)
    
    # Read chunk and find all '},' or '}' followed by '"'
    chunk = f.read(start_pos - search_start)
    
    # Find the last occurrence of record boundary
    last_boundary = -1
    i = len(chunk) - 1
    while i >= 0:
        if chunk[i:i+1] == b'}':
            # Check what follows
            if i + 1 < len(chunk):
                next_char = chunk[i+1:i+2]
                if next_char == b',':
                    last_boundary = search_start + i + 2  # After '},
                    break
                elif next_char == b'"' or next_char == b'}':
                    last_boundary = search_start + i + 1  # After '}'
                    break
        i -= 1
    
    return last_boundary if last_boundary > 0 else None


def ultra_fast_split(json_file, n_splits, output_dir="knot_splits"):
    """
    Ultra-fast splitting:
    1. Divide file into N equal byte chunks
    2. Adjust boundaries to record edges (only read boundaries)
    3. Extract and fix JSON formatting
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    file_size = Path(json_file).stat().st_size
    print(f"File size: {file_size / (1024**3):.2f} GB", file=sys.stderr)
    print(f"Splitting into {n_splits} chunks...\n", file=sys.stderr)
    
    # Find where actual data starts (skip {"data":{)
    with open(json_file, 'rb') as f:
        header = f.read(10000)
        data_start = header.find(b'"data"')
        data_start = header.find(b': {', data_start) + 3
        
        # Find where data ends
        f.seek(-10000, 2)  # Go to near end
        footer = f.read()
        data_end = file_size - len(footer) + footer.rfind(b'}')
    
    print(f"Data section: bytes {data_start} to {data_end}", file=sys.stderr)
    
    data_size = data_end - data_start
    chunk_size = data_size // n_splits
    
    # Calculate split points
    # First chunk always starts at data_start
    split_points = [data_start]
    
    with open(json_file, 'rb') as f:
        for i in range(1, n_splits):
            # Target position
            target_pos = data_start + i * chunk_size
            f.seek(target_pos)
            
            # Find next complete record boundary (start of next record)
            boundary = find_record_boundary_forward(f)
            if boundary:
                split_points.append(boundary)
                print(f"Split {i}: byte {boundary} ({boundary/(1024**3):.2f} GB)", file=sys.stderr)
            else:
                print(f"Warning: Could not find boundary for split {i}", file=sys.stderr)
                # Try to find it by going forward more
                f.seek(target_pos)
                boundary = find_record_boundary_forward(f, max_search=500000)
                if boundary:
                    split_points.append(boundary)
                    print(f"  Found at byte {boundary}", file=sys.stderr)
                else:
                    print(f"  Using target position (may be corrupted)", file=sys.stderr)
                    split_points.append(target_pos)
        
        split_points.append(data_end)
    
    print(f"\nCreating {len(split_points)-1} split files...\n", file=sys.stderr)
    
    # Now create split files by reading only the relevant chunks
    split_files = []
    with open(json_file, 'rb') as f:
        for i in range(len(split_points) - 1):
            split_file = output_path / f"knots_split_{i:03d}.json"
            split_files.append(split_file)
            
            start = split_points[i] - (i > 0)
            end = split_points[i + 1] - 1
            chunk_bytes = end - start
            
            print(f"Writing split {i}: {chunk_bytes/(1024**2):.1f} MB", file=sys.stderr, end='')
            
            # Read this chunk
            f.seek(start)
            chunk_data = f.read(chunk_bytes)
            
            # Clean up the chunk
            # For first chunk: data should start with a complete record (already at right position)
            # For other chunks: boundary finder should have positioned us at start of a complete record
            
            # Remove any leading whitespace or comma
            chunk_data = chunk_data.lstrip()
            if chunk_data.startswith(b','):
                chunk_data = chunk_data[1:].lstrip()
            
            # Remove trailing comma and whitespace
            chunk_data = chunk_data.rstrip()
            if chunk_data.endswith(b','):
                chunk_data = chunk_data[:-1].rstrip()
            
            # Verify chunk starts with a record (should start with ")
            if chunk_data and not chunk_data.startswith(b'"'):
                print(f" WARNING: chunk doesn't start with quote, starts with: {chunk_data[:50]}", file=sys.stderr)
            
            # Verify chunk ends with }
            if chunk_data and not chunk_data.endswith(b'}'):
                print(f" WARNING: chunk doesn't end with brace, ends with: {chunk_data[-50:]}", file=sys.stderr)
            
            # Write as valid JSON
            with open(split_file, 'wb') as out:
                out.write(b'{"data":{')
                out.write(chunk_data)
                #out.write(chunk_data if i==0 else chunk_data[2:])
                if (i < len(split_points)-2): out.write(b'}') 
                out.write(b'}')

            
            print(f" ✓", file=sys.stderr)
    
    print(f"\n✓ Split complete! {len(split_files)} files in {output_path}/", file=sys.stderr)
    
    return split_files


def process_split_file(args):
    """Process one split file"""
    split_file, rep, worker_id = args
    
    #Jm = lambda A, B: [q for q, c in enumerate([A.get(i, 0) + B.get(i, 0) for i in range(max(A | B) + 1)][1:]) if c != 0][0] + 1
    numerics = lambda s, l=-1: ''.join([c for c in s if c.isdigit()])[:l]
    
    local_Jm_table = {str(i): ['', 2, defaultdict(int)] for i in range(1, 20)}
    local_knot_ids = {m: [] for m in range(10)}
    count = 0
    
    print(f"Worker {worker_id}: Starting {split_file.name}", file=sys.stderr, flush=True)
    
    try:
        with open(split_file, 'rb') as f:
            parser = ijson.kvitems(f, 'data')
            
            for knot_label, knot_data in parser:
                count += 1
                if count % 10000 == 0:
                    print(f"Worker {worker_id}: {count} knots", file=sys.stderr, end='\r', flush=True)
                
                if knot_label == "0_1":
                    continue
                
                coefs = {int(k): int(v) for k, v in knot_data.get("coeffs", {}).items()}
                if not coefs:
                    continue
                

                crossings = knot_label.split('_')[0] if ('_' in knot_label and 'jones' not in knot_label) else numerics(knot_label, 2)
                
                knot_id = int(knot_label.split('_')[-1].split(':')[-1].split('a')[-1].split('n')[-1])
                
                try:
                    #A, B = jones_to_Vxp(coefs)
                    #m = Jm(A, B)

                    m = Jtransform[rep](coefs)

                    local_Jm_table[crossings][2][m] += 1
                    
                    if m > min_m:
                        if (local_knot_ids[m] == []) or (knot_id > local_knot_ids[m][-1][2]+sample_interval) or \
                                (crossings != local_knot_ids[m][-1][0]):
                            local_knot_ids[m].append([crossings, knot_id, knot_id, knot_label])
                        elif knot_id == local_knot_ids[m][-1][2]+1:
                                local_knot_ids[m][-1][2] += 1


                    if m > local_Jm_table[crossings][1]:
                        print(f"\nWorker {worker_id}: Knot {knot_label}: J{m}-trivial", file=sys.stderr, flush=True)
                        local_Jm_table[crossings][:2] = [knot_label, m]
                except Exception as e:
                    continue
    except Exception as e:
        print(f"\nWorker {worker_id}: Error parsing {split_file}: {e}", file=sys.stderr)
        print(f"Worker {worker_id}: Processed {count} knots before error", file=sys.stderr)
    
    print(f"\nWorker {worker_id}: Done - {count} knots processed", file=sys.stderr, flush=True)
    
    for c in local_Jm_table:
        local_Jm_table[c][2] = dict(local_Jm_table[c][2])
    
    return local_Jm_table, local_knot_ids


def merge_results(results):
    """Merge results from all workers"""
    merged_table = {str(i): ['', 2, {m: 0 for m in range(2,11)}] for i in range(1, 20)}
    merged_knot_ids = defaultdict(list)
    
    for Jm_table, knot_ids in results:
        for crossings, data in Jm_table.items():
            for m, count in data[2].items():
                merged_table[crossings][2][m] += count
            
            if data[1] > merged_table[crossings][1]:
                merged_table[crossings][:2] = data[:2]
        
        for m, knots in knot_ids.items():
            merged_knot_ids[m] = merged_knot_ids[m] + knots
    
    #for c in merged_table:
    #    merged_table[c][2] = dict(merged_table[c][2])
    
    return merged_table, dict(merged_knot_ids)

def format_elapsed_time(start_time):
    elapsed_seconds = time.time() - start_time
    minutes, seconds = divmod(int(elapsed_seconds), 60)
    return f"{minutes}:{seconds:02d}"

def main():

    prob_file = "Jm_probs.json"

    if len(sys.argv) < 2:
        print("Ultra-fast splitting and processing of massive Jones coefficient datasets.\n", file=sys.stderr)
        print("* Computes Jm-triviality index using finite-type expansion of the knot's Jones polynomial.\n" 
              "* Generates knot chunks data with knot ids and their Jm-triviality classes.\n"
              f"* Updates Jm-triviality probability distribution ({prob_file}).\n\n")
        print(f"Usage: {sys.argv[0]}  <json_file> [n_workers] --R <JVP> --S <n> --K <knot_id_file>", file=sys.stderr)
        print('\n\n--R'+20*' '+'JVP ring representation (default) or Birman-Lin expansion.')
        print('\n--S <n>'+16*' '+'skip every n knots when generating knot_id_file (defalut: n=1).')
        print('\n--K <knot_id_file>'+5*' '+'file containing knot chunks with their Jm-triviality index (default: knot_ids.json).')
        print('\n\n'+'>'*10+' Examples '+'<'*10)
        print(f'{sys.argv[0]} JonesData/jones_0_to_12.json 1 --K knot_ids.json')
        print(f'{sys.argv[0]} JonesData/jones_17.json 10 --S 10000 --K knot_ids_17.json')
        sys.exit(1)
    
    json_file = Path(sys.argv[1])

    n_workers = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdecimal() else cpu_count()

    print(f"Using {n_workers} workers.\n")
    
    # Process options

    options = {
        '--R': ['JVP', str, lambda s: s in ['Birman-Lin', 'JVP']],
        '--S': [1, int, lambda s: s.isdecimal()],
        '--K': ['knot_ids.json', str, lambda s: True]
        }

    if len(sys.argv) > 2:
        for option, field in options.items():
            try:
                i = sys.argv.index(option)
                if field[-1](sys.argv[i+1]):
                    options.update({option: [field[-2](sys.argv[i+1])]})
                else:
                    print(f"Unsupported value {sys.argv[i+1]} for option {option}.")
            except Exception as e:
                pass
        
    
    rep = options['--R'][0]
    knot_id_file = options['--K'][0]
    globals()['sample_interval'] = options['--S'][0]

    print(f">> Using {rep} representation <<\n")


    splits_dir = Path("knot_splits")
    split_files = []
    
    if not split_files:
        print("Split files not found. Starting ultra-fast split...\n", file=sys.stderr)
        split_files = ultra_fast_split(json_file, n_workers)
        #sys.exit(0)
    else:
        print(f"Using existing {len(split_files)} split files from {splits_dir}/\n", file=sys.stderr)
    
    print(f"Processing with {len(split_files)} workers...\n", file=sys.stderr)
    worker_args = [(split_file, rep, i) for i, split_file in enumerate(split_files)]
    
    start = time.time()

    with Pool(len(split_files)) as pool:
        results = pool.map(process_split_file, worker_args)
    
    print("\nMerging results...", file=sys.stderr)
    Jm_table, knot_ids = merge_results(results)
    
    outfile = Path(prob_file)
    data = json.load(open(outfile)) if outfile.exists() else {}
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    for c, d in Jm_table.items():
        if d[0]:
            print(f"\n{c} crossings. Maximally trivial m={d[1]}; Knot {d[0]}")
            n_knots = sum(d[2].values())
            if n_knots > 0:
                probs = [p/n_knots for i, p in d[2].items() if i <= d[1]]
                p = ' | '.join([f"J{2+k}: {pr:.2}" for k, pr in enumerate(probs)])
                print(f"{n_knots} knots. Jm-trivial probabilities: {p}")
                data[c] = probs
    
    with open(outfile, "w") as file:
        json.dump(data, file, indent=4)

    with open(knot_id_file, "w") as file:
        json.dump(knot_ids, file, indent=4)
    
    print(f"\nJm-triviality distribution saved to {outfile}")
    print(f"Knot chunks written to {knot_id_file}. To visualize use ./visualize {knot_id_file}.")
    print(f"Elapsed time {format_elapsed_time(start)}")


if __name__ == '__main__':
    main()