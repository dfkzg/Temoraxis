"""Render the project's simple SVG mark into PNG using only Python's standard library.

Supports the rounded rectangle and round-stroked polyline used by web-source/icon.svg.
No downloaded raster images, icon fonts or third-party icon renderer are used.
"""
import argparse,re,struct,zlib,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)

def color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError('Only RGB colors are supported')
    return tuple(int(value[i:i+2],16) for i in (1,3,5))

def render(size):
    svg=ET.parse(ROOT/'web-source/icon.svg').getroot()
    rect,path=list(svg)
    assert rect.tag.endswith('rect') and path.tag.endswith('path') and len(svg)==2
    view=tuple(map(float,svg.attrib['viewBox'].split()));assert view==(0,0,108,108)
    assert path.attrib['stroke-linecap']=='round' and path.attrib['stroke-linejoin']=='round'
    numbers=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+)',path.attrib['d'])))
    assert len(numbers)==6 and not re.search(r'[A-KN-Za-kn-z]',path.attrib['d'])
    points=list(zip(numbers[::2],numbers[1::2]));radius=float(rect.attrib['rx'])
    bg=color(rect.attrib['fill']);ink=color(path.attrib['stroke']);half=float(path.attrib['stroke-width'])/2
    samples=4;rows=[]
    for row in range(size):
        out=bytearray([0])
        for col in range(size):
            total=[0,0,0];covered=0
            for sy in range(samples):
                y=(row+(sy+.5)/samples)*108/size
                for sx in range(samples):
                    x=(col+(sx+.5)/samples)*108/size
                    dx=max(radius-x,0,x-(108-radius));dy=max(radius-y,0,y-(108-radius))
                    if dx*dx+dy*dy>radius*radius:continue
                    pixel=bg
                    for (ax,ay),(bx,by) in zip(points,points[1:]):
                        vx,vy=bx-ax,by-ay;t=max(0,min(1,((x-ax)*vx+(y-ay)*vy)/(vx*vx+vy*vy)))
                        if (x-ax-t*vx)**2+(y-ay-t*vy)**2<=half*half:pixel=ink;break
                    covered+=1
                    for i in range(3):total[i]+=pixel[i]
            out.extend([round(v/covered) if covered else 0 for v in total]+[round(255*covered/(samples*samples))])
        rows.append(out)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for size in (180,192,512):
        target=ROOT/'web-source'/('icon-'+str(size)+'.png');data=render(size)
        if args.check:
            if target.read_bytes()!=data:raise SystemExit('Regenerate '+str(target))
        else:target.write_bytes(data)
    print('PNG icons verified from project SVG' if args.check else 'PNG icons generated from project SVG')
