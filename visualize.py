#!/usr/bin/env python3
# -*- coding: utf-8 -*-



import numpy as np
import pandas as pd
import json
import sys

scheme = {'green': {
            1: '#70DFFF',  # Cyan
            2: '#70DFFF',  
            3: '#70DFCC',  
            4: '#70DFAA',  
            5: '#70DF99',  
            6: '#70DF88',  
            7: '#70DF77',  
            8: '#70DF66',  
            9: '#70DF55',  
            'shadow': 'rgba(50, 255, 155, 0.3)',
            'title': '#00FFFF'
        },
        'purple': {
            1: '#A03FFF',
            2: '#903FFF',  
            3: '#803FCC',  
            4: '#703FAA',  
            5: '#603F88',  
            6: '#503F66',  
            7: '#403F55',  
            8: '#303F44',  
            9: '#203F33',  
            'shadow': 'rgba(150, 55, 255, 0.3)',
            'title': '#A01FFF'
        }
}

def generate_sample_knot_data(n_per_crossing=100):
    """Generate sample knot data - reduced for performance"""
    np.random.seed(42)
    
    knots = []
    knot_id = 0
    
    for cn in range(3, 20):
        n_samples = n_per_crossing
        
        for _ in range(n_samples):
            if cn <= 6:
                class_probs = [0.3, 0.25, 0.2, 0.1, 0.08, 0.04, 0.02, 0.01, 0.0]
            elif cn <= 10:
                class_probs = [0.15, 0.18, 0.18, 0.15, 0.12, 0.1, 0.07, 0.03, 0.02]
            elif cn <= 14:
                class_probs = [0.08, 0.12, 0.15, 0.15, 0.14, 0.13, 0.1, 0.08, 0.05]
            else:
                class_probs = [0.03, 0.06, 0.09, 0.12, 0.14, 0.15, 0.15, 0.14, 0.12]
            
            cls = np.random.choice(range(1, 10), p=class_probs)
            
            knots.append({
                'knot_id': f'K_{knot_id:08d}',
                'crossing_number': cn,
                'class': cls,
                'chunk_size': 100
            })
            knot_id += 1
    
    return pd.DataFrame(knots)

def load_knot_data(filenames: list):

    knots = []
    max_cn = 0

    for filename in filenames:
        with open(filename, "r") as file:
            data = json.load(file)
        
        for m, knot_list in data.items():
            for cn, kid0, kid1, label in knot_list: 
                knots.append({
                    'knot_id': label,
                    'crossing_number': int(cn),
                    'class': int(m),
                    'chunk_size': kid1-kid0+1 
                })

                max_cn = max(int(cn), max_cn)

    return pd.DataFrame(knots), max_cn


def bezier_curve_points(p0, p1, p2, n_points=8):
    """Generate Bezier curve points"""
    t = np.linspace(0, 1, n_points)
    x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
    y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
    return list(zip(x.tolist(), y.tolist()))


def prepare_visualization_data(df, color, max_chunks=2000):
    """Prepare data structure for visualization"""
    
    if len(df) > max_chunks:
        df = df.sample(n=max_chunks, random_state=42)
    
    print(f"Visualizing {len(df):,} chunks")
    
    min_cn = 3 #df['crossing_number'].min()
    max_cn = 19 #df['crossing_number'].max()
    
    def get_radius(cn):
        return 150 + (cn - min_cn) * 20
    
    # Brighter neon colors
    class_colors = scheme[color]
    
    viz_data = {
        'classes': {},
        'config': {
            'min_cn': int(min_cn),
            'max_cn': int(max_cn),
            'inner_radius': 100,
            'colors': class_colors
        }
    }
    
    class_angles = {cls: (cls-1) * 360/9 + 180/9 for cls in range(1, 10)}
    
    for cls in range(1, 10):
        df_class = df[df['class'] == cls]
        
        knots_data = []
        curves_data = []
        
        for _, knot in df_class.iterrows():
            cn = knot['crossing_number']
            radius = get_radius(cn)
            
            n_at_cn = len(df[df['crossing_number'] == cn])
            knot_idx = len(df[(df['crossing_number'] == cn) & (df.index <= knot.name)])
            angle = (knot_idx / n_at_cn) * 360
            angle_rad = np.radians(angle)
            
            knot_x = radius * np.cos(angle_rad)
            knot_y = radius * np.sin(angle_rad)
            
            chunk_size = knot.get('chunk_size', 1)
            representative_id = knot.get('representative_id', knot.get('knot_id', f'K_{knot.name}'))
            
            knots_data.append({
                'x': float(knot_x),
                'y': float(knot_y),
                'id': representative_id,
                'cn': int(cn),
                'chunk_size': int(chunk_size)
            })
            
            class_angle_rad = np.radians(class_angles[cls])
            class_x = 100 * np.cos(class_angle_rad)
            class_y = 100 * np.sin(class_angle_rad)
            
            control_radius = radius * 0.4
            control_x = control_radius * np.cos(angle_rad)
            control_y = control_radius * np.sin(angle_rad)
            
            curve = bezier_curve_points(
                (knot_x, knot_y),
                (control_x, control_y),
                (class_x, class_y),
                n_points=8
            )
            
            curves_data.append(curve)
        
        viz_data['classes'][cls] = {
            'knots': knots_data,
            'curves': curves_data,
            'color': class_colors[cls],
            'angle': class_angles[cls]
        }
    
    return viz_data


def create_fixed_visualization_html(viz_data, color, max_cn, output_file):
    """Create HTML with truly dynamic paths and high visibility"""
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Triviality index of prime knots</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            background: #000000;
            font-family: 'Courier New', monospace;
            color: #00FFFF;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        
        #container {{
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            padding: 20px;
        }}
        
        #title {{
            font-size: 24px;
            color: {scheme[color]['title']};
            text-align: center;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.8);
            letter-spacing: 2px;
        }}
        
        #instructions {{
            font-size: 12px;
            color: #00FFAA;
            text-align: center;
            opacity: 0.6;
        }}
        
        #viz-container {{
            position: relative;
            background: #000000;
            border-radius: 50%;
            box-shadow: 0 0 50px {scheme[color]['shadow']};
        }}
        
        svg {{
            display: block;
        }}
        
        /* Points - always visible */
        .knot-point {{
            opacity: 0.3;
        }}
        
        /* Curves - completely hidden by default */
        .knot-curve {{
            display: none;
            opacity: 0.01;
        }}
        
        /* When a class is active, its curves are shown and bright */
        .knot-curve.active {{
            display: block;
            opacity: 0.1;
        }}
        
        /* Dimmed points */
        .knot-point.dimmed {{
            opacity: 0.05;
        }}
        
        .class-sector {{
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .class-sector:hover {{
            filter: brightness(0.1);
        }}
        
        .crossing-circle {{
            opacity: 0.4;
        }}
        
        .crossing-circle.active {{
            opacity: 0.8;
        }}
        
        #hover-info {{
            position: fixed;
            background: rgba(0, 0, 0, 0.95);
            border: 1px solid #00FFFF;
            border-radius: 8px;
            padding: 12px 16px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.6);
        }}
        
        .info-label {{
            font-size: 10px;
            color: #00FFAA;
            opacity: 0.7;
            text-transform: uppercase;
        }}
        
        .info-value {{
            font-size: 14px;
            color: #00FFFF;
            font-weight: bold;
            text-shadow: 0 0 10px rgba(0, 255, 255, 0.8);
            margin-bottom: 8px;
        }}
        
        #stats {{
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 20px;
            padding: 15px 25px;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
        }}
        
        .stat-box {{
            text-align: center;
            padding: 0 15px;
            border-right: 1px solid rgba(0, 255, 255, 0.2);
        }}
        
        .stat-box:last-child {{
            border-right: none;
        }}
        
        .stat-title {{
            font-size: 10px;
            color: #00FFAA;
            opacity: 0.6;
            margin-bottom: 5px;
            text-transform: uppercase;
        }}
        
        .stat-value {{
            font-size: 20px;
            color: #00FFFF;
            font-weight: bold;
            text-shadow: 0 0 15px rgba(0, 255, 255, 0.8);
        }}
    </style>
</head>
<body>
    <div id="container">
        <div id="title">Triviality index of prime knots up to {max_cn} crossings</div>
        <div id="instructions">
            Hover over triviality index to reveal connections
        </div>
        
        <div id="viz-container">
            <svg id="visualization" width="1000" height="1000" viewBox="-500 -500 1000 1000">
            </svg>
            <div id="hover-info"></div>
        </div>
        
        <div id="stats"></div>
    </div>
    
    <script>
        const data = {json.dumps(viz_data)};
        const svg = document.getElementById('visualization');
        const hoverInfo = document.getElementById('hover-info');
        let currentHighlightedClass = null;
        
        function drawCrossingCircles() {{
            const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            group.id = 'crossing-circles';
            
            for (let cn = data.config.min_cn; cn <= data.config.max_cn; cn++) {{
                const radius = 150 + (cn - data.config.min_cn) * 20;
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', 0);
                circle.setAttribute('cy', 0);
                circle.setAttribute('r', radius);
                circle.setAttribute('fill', 'none');
                circle.setAttribute('stroke', '#00FFFF');
                circle.setAttribute('stroke-width', 0.8);
                circle.setAttribute('stroke-opacity', 0.4);
                circle.setAttribute('class', 'crossing-circle');
                circle.setAttribute('data-cn', cn);
                group.appendChild(circle);

                const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                label.setAttribute('x', 0);  // Centered horizontally
                label.setAttribute('y', -radius - 8);  // Above the circle
                label.setAttribute('text-anchor', 'middle');
                label.setAttribute('fill', '#00FFFF');
                label.setAttribute('font-size', '12');
                label.setAttribute('font-family', 'Courier New, monospace');
                label.setAttribute('opacity', '0.6');
                label.textContent = cn;
                group.appendChild(label);
            }}
            
            svg.appendChild(group);
        }}
        
        function drawClassSectors() {{
            const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            group.id = 'class-sectors';
            
            for (let cls = 1; cls <= 9; cls++) {{
                const classData = data.classes[cls];
                if (!classData) continue;
                
                const angleStart = (cls - 1) * 40;
                const angleEnd = cls * 40;
                
                const startRad = angleStart * Math.PI / 180;
                const endRad = angleEnd * Math.PI / 180;
                
                const x1 = data.config.inner_radius * Math.cos(startRad);
                const y1 = data.config.inner_radius * Math.sin(startRad);
                const x2 = data.config.inner_radius * Math.cos(endRad);
                const y2 = data.config.inner_radius * Math.sin(endRad);
                
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                const d = `M 0 0 L ${{x1}} ${{y1}} A ${{data.config.inner_radius}} ${{data.config.inner_radius}} 0 0 1 ${{x2}} ${{y2}} Z`;
                path.setAttribute('d', d);
                path.setAttribute('fill', classData.color);
                path.setAttribute('fill-opacity', 0.5);
                path.setAttribute('stroke', classData.color);
                path.setAttribute('stroke-width', 2);
                path.setAttribute('class', 'class-sector');
                path.setAttribute('data-class', cls);
                path.style.filter = `drop-shadow(0 0 8px ${{classData.color}})`;
                
                path.addEventListener('mouseenter', () => highlightClass(cls));
                path.addEventListener('mouseleave', () => unhighlightAll());
                
                group.appendChild(path);
                
                // Class label
                const labelAngle = (angleStart + angleEnd) / 2 * Math.PI / 180;
                const labelRadius = data.config.inner_radius * 0.7;
                const labelX = labelRadius * Math.cos(labelAngle);
                const labelY = labelRadius * Math.sin(labelAngle);
                
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', labelX);
                text.setAttribute('y', labelY);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('dominant-baseline', 'middle');
                text.setAttribute('fill', 'black');
                text.setAttribute('font-size', '24');
                text.setAttribute('font-weight', 'bold');
                text.setAttribute('pointer-events', 'none');
                text.style.filter = `drop-shadow(0 0 10px ${{classData.color}})`;
                text.textContent = cls;
                group.appendChild(text);
            }}
            
            svg.appendChild(group);
        }}

        function drawCenterDisk() {{
            const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            group.id = 'center-disk';
            
            // Blank disk (covers the center)
            const disk = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            disk.setAttribute('cx', 0);
            disk.setAttribute('cy', 0);
            disk.setAttribute('r', 50);  // Adjust size as needed (smaller than inner_radius of 100)
            disk.setAttribute('fill', '#000000');  // Black disk
            disk.setAttribute('stroke', '#00FFFF');  // Neon blue border
            disk.setAttribute('stroke-width', 2);
            disk.style.filter = 'drop-shadow(0 0 8px #00FFFF)';  // Neon glow
            group.appendChild(disk);
            
            // "Triviality index" text
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', 0);
            text.setAttribute('y', 0);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('dominant-baseline', 'middle');
            text.setAttribute('fill', '#00FFFF');  // Neon blue
            text.setAttribute('font-size', '10');
            text.setAttribute('font-weight', 'bold');
            text.setAttribute('letter-spacing', '1');
            text.style.filter = 'drop-shadow(0 0 20px #00FFFF)';  // Neon glow
            text.textContent = 'Jm-triviality';
            group.appendChild(text);
            
            svg.appendChild(group);
        }}
        
        function drawClassData() {{
            for (let cls = 1; cls <= 9; cls++) {{
                const classData = data.classes[cls];
                if (!classData) continue;
                
                // Draw curves - HIDDEN by default with display:none
                const curveGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                curveGroup.id = `class-${{cls}}-curves`;
                
                classData.curves.forEach((curve, idx) => {{
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    let d = `M ${{curve[0][0]}} ${{curve[0][1]}}`;
                    for (let i = 1; i < curve.length; i++) {{
                        d += ` L ${{curve[i][0]}} ${{curve[i][1]}}`;
                    }}
                    path.setAttribute('d', d);
                    path.setAttribute('stroke', classData.color);
                    path.setAttribute('stroke-width', 2.0);  // THICK
                    path.setAttribute('fill', 'none');
                    path.setAttribute('class', 'knot-curve');
                    path.setAttribute('data-class', cls);
                    // Add strong glow
                    path.style.filter = `drop-shadow(0 0 3px ${{classData.color}}) drop-shadow(0 0 6px ${{classData.color}}) drop-shadow(0 0 10px ${{classData.color}})`;
                    curveGroup.appendChild(path);
                }});
                
                svg.appendChild(curveGroup);
                
                // Draw points
                const pointGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                pointGroup.id = `class-${{cls}}-points`;
                
                classData.knots.forEach(knot => {{
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', knot.x);
                    circle.setAttribute('cy', knot.y);
                    circle.setAttribute('r', 2);
                    circle.setAttribute('fill', classData.color);
                    circle.setAttribute('class', 'knot-point');
                    circle.setAttribute('data-knot-id', knot.id);
                    circle.setAttribute('data-cn', knot.cn);
                    circle.setAttribute('data-class', cls);
                    circle.setAttribute('data-chunk-size', knot.chunk_size);
                    circle.style.filter = `drop-shadow(0 0 2px ${{classData.color}})`;
                    
                    circle.addEventListener('mouseenter', (e) => showKnotInfo(e, knot, cls));
                    circle.addEventListener('mouseleave', () => hideKnotInfo());
                    
                    pointGroup.appendChild(circle);
                }});
                
                svg.appendChild(pointGroup);
            }}
        }}
        
        function highlightClass(cls) {{
            console.log('Highlighting class:', cls);
            currentHighlightedClass = cls;
            
            // First, hide ALL curves and dim ALL points
            document.querySelectorAll('.knot-curve').forEach(el => {{
                el.classList.remove('active');
            }});
            
            document.querySelectorAll('.knot-point').forEach(el => {{
                el.classList.add('dimmed');
            }});
            
            document.querySelectorAll('.crossing-circle').forEach(el => {{
                el.classList.remove('active');
            }});
            
            // Now show ONLY the selected class curves and points
            document.querySelectorAll(`[data-class="${{cls}}"]`).forEach(el => {{
                if (el.classList.contains('knot-curve')) {{
                    el.classList.add('active');  // This makes it visible
                }}
                if (el.classList.contains('knot-point')) {{
                    el.classList.remove('dimmed');
                }}
            }});
            
            // Highlight relevant crossing circles
            const classKnots = data.classes[cls].knots;
            const crossingNumbers = new Set(classKnots.map(k => k.cn));
            crossingNumbers.forEach(cn => {{
                document.querySelectorAll(`[data-cn="${{cn}}"]`).forEach(el => {{
                    if (el.classList.contains('crossing-circle')) {{
                        el.classList.add('active');
                    }}
                }});
            }});
            
            updateStats(cls);
        }}
        
        function unhighlightAll() {{
            console.log('Unhighlighting all');
            currentHighlightedClass = null;
            
            // Hide all curves
            document.querySelectorAll('.knot-curve').forEach(el => {{
                el.classList.remove('active');
            }});
            
            // Restore all points
            document.querySelectorAll('.knot-point').forEach(el => {{
                el.classList.remove('dimmed');
            }});
            
            // Reset crossing circles
            document.querySelectorAll('.crossing-circle').forEach(el => {{
                el.classList.remove('active');
            }});
            
            updateStats(null);
        }}
        
        function showKnotInfo(event, knot, cls) {{
            const color = data.classes[cls].color;
            const chunkText = knot.chunk_size > 1 ? 
                `<div class="info-label">Chunk Size</div>
                 <div class="info-value">${{knot.chunk_size.toLocaleString()}} knots</div>` : '';
            
            hoverInfo.innerHTML = `
                <div class="info-label">ID</div>
                <div class="info-value">${{knot.id}}</div>
                <div class="info-label">Crossings</div>
                <div class="info-value">${{knot.cn}}</div>
                <div class="info-label">Class</div>
                <div class="info-value" style="color: ${{color}}; text-shadow: 0 0 15px ${{color}};">${{cls}}</div>
                ${{chunkText}}
            `;
            hoverInfo.style.display = 'block';
            hoverInfo.style.left = event.pageX + 20 + 'px';
            hoverInfo.style.top = event.pageY + 20 + 'px';
        }}
        
        function hideKnotInfo() {{
            hoverInfo.style.display = 'none';
        }}
        
        function updateStats(highlightedClass) {{
            const statsDiv = document.getElementById('stats');
            
            if (highlightedClass === null) {{
                let totalKnots = 0;
                let totalChunks = 0;
                for (let cls in data.classes) {{
                    data.classes[cls].knots.forEach(k => {{
                        totalChunks++;
                        totalKnots += k.chunk_size;
                    }});
                }}
                
                statsDiv.innerHTML = `
                    <div class="stat-box">
                        <div class="stat-title">Total Chunks</div>
                        <div class="stat-value">${{totalChunks.toLocaleString()}}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Represented Knots</div>
                        <div class="stat-value">${{totalKnots.toLocaleString()}}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Classes</div>
                        <div class="stat-value">9</div>
                    </div>
                `;
            }} else {{
                const classData = data.classes[highlightedClass];
                const chunkCount = classData.knots.length;
                const knotCount = classData.knots.reduce((sum, k) => sum + k.chunk_size, 0);
                
                let minCn = Infinity, maxCn = -Infinity;
                classData.knots.forEach(knot => {{
                    minCn = Math.min(minCn, knot.cn);
                    maxCn = Math.max(maxCn, knot.cn);
                }});
                
                const color = classData.color;
                statsDiv.innerHTML = `
                    <div class="stat-box">
                        <div class="stat-title">Class ${{highlightedClass}}</div>
                        <div class="stat-value" style="color: ${{color}}; text-shadow: 0 0 20px ${{color}};">${{chunkCount.toLocaleString()}} chunks</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Knots</div>
                        <div class="stat-value">${{knotCount.toLocaleString()}}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Crossings</div>
                        <div class="stat-value">${{minCn}}-${{maxCn}}</div>
                    </div>
                `;
            }}
        }}
        
        svg.addEventListener('click', (e) => {{
            if (e.target === svg) {{
                unhighlightAll();
            }}
        }});
        
        function init() {{
            drawCrossingCircles();
            drawClassData();
            drawClassSectors();
            drawCenterDisk();
            updateStats(null);
            
            console.log('Visualization initialized');
            console.log('Chunks:', Object.values(data.classes).reduce((sum, c) => sum + c.knots.length, 0));
        }}
        
        init();
    </script>
</body>
</html>'''
    
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"✨ Visualization saved to: {output_file}")


def main(knot_id_files, color='green', max_chunks=20000, output_file="knots_Jm_visualizer.html"):
    print("=" * 70)
    print("Generating visualization")
    print("=" * 70)
    
    # Generate minimal data
    #df = generate_sample_knot_data(n_per_crossing=100)
    df, max_cn = load_knot_data(knot_id_files)
    print(f"\nLoaded {len(df):,} knot chunks.")
    
    # Prepare visualization
    viz_data = prepare_visualization_data(df, color, max_chunks=max_chunks)
    
    # Create HTML
    create_fixed_visualization_html(viz_data, color, max_cn, output_file)
    
    print("\n" + "=" * 70)
    print("✨ Done.")
    print("=" * 70)


if __name__ == "__main__":

    from pathlib import Path

    if len(sys.argv) < 2:
        print("Knot Jm-triviality index visualizer.\n\n" \
              f"Usage: {sys.argv[0]} --c <purple/green> --o <output.html> <knot_id json files>\n\n"
              "--c      color scheme (default: green)\n"
              "--o      output html file (default: Jm_visualizer.html)"
        )
        sys.exit(0)

    
    options = {
        '--c': ['green', str, lambda s: s in scheme],
        '--o': ['Jm_visualizer.html', str, lambda s: True]
        }


    for option, field in options.items():
        try:
            i = sys.argv.index(option)
            if field[-1](sys.argv[i+1]):
                options.update({option: [field[-2](sys.argv[i+1])]})
            else:
                print(f"Unsupported value {sys.argv[i+1]} for option {option}.")
        except Exception as e:
            pass
    
    color_scheme = options['--c'][0]
    knot_id_files = [f for f in sys.argv[1:] if Path(f).exists() and Path(f).name.endswith('.json')]

    if not knot_id_files:
        print('One or more files were not found.')
        sys.exit(1)

    print("Using knot id files: "+', '.join(knot_id_files))
    main(knot_id_files=knot_id_files, color=color_scheme, output_file=options['--o'][0])
