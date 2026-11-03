#!/usr/bin/python3
"""Reproducibly author the original Woodland River foreground, without downloads."""
import json
import math
from pathlib import Path
import random
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent / 'woodland'
W,H = 2560,1440
rng = random.Random(572004)
image = Image.new('RGBA',(W,H))
draw = ImageDraw.Draw(image)

def ridge(base, amplitude, phase, fill):
    points=[(x,round(H*(base+math.sin(x/W*8+phase)*amplitude+math.sin(x/W*18+phase)*amplitude*.23))) for x in range(-10,W+11,8)]
    draw.polygon(points+[(W+10,H+10),(-10,H+10)],fill=fill)

# Low layered contours; all sky is truly transparent.
ridge(.724,.027,.4,(115,145,141,255))
ridge(.771,.022,2.9,(86,119,112,255))
# A delicate distant woodland follows the far contour rather than filling the sky.
for x in range(15,W,23):
    y=H*(.754+math.sin(x/W*8+.7)*.018)
    height=rng.uniform(17,45)
    draw.line((x,y,x,y-height),fill=(71,107,103,255),width=2)
    draw.polygon([(x,y-height),(x-height*.30,y-6),(x+height*.30,y-6)],fill=(80,115,109,255))
ridge(.82,.032,.5,(66,105,87,255))
ridge(.895,.045,3.0,(47,83,69,255))
# Open water threads through the meadow; outlined banks remain gentle and flat.
river=[(1553,1102),(1510,1120),(1380,1147),(1350,1165),(1460,1190),(1535,1224),(1485,1260),(1270,1321),(1130,1440),(1755,1440),(1705,1337),(1624,1281),(1692,1232),(1620,1192),(1482,1159),(1470,1148),(1560,1111)]
draw.polygon(river,fill=(92,133,139,255))
draw.line(river[:10],fill=(148,161,132,255),width=5)
water = Image.new('RGBA',(W,H))
water_draw = ImageDraw.Draw(water)
for y in range(1160,H,13):
    left=1370+math.sin(y*.023)*120
    width=55+(y-1160)*.42
    water_draw.line((left,y,left+width,y),fill=(123,155,154,180),width=2)
water_mask = Image.new('L',(W,H))
ImageDraw.Draw(water_mask).polygon(river,fill=255)
water.putalpha(Image.composite(water.getchannel('A'),Image.new('L',(W,H)),water_mask))
image.alpha_composite(water)
# Slow arcing meadow strokes and discreet seed heads give the foreground texture.
for _ in range(490):
    x=rng.randrange(W);y=rng.randrange(1240,H)
    if 1150<x<1760:continue
    length=rng.randrange(5,28)
    color=rng.choice([(91,119,78,200),(105,125,81,200),(57,95,74,230),(135,137,87,180)])
    draw.line((x,y,x+length*.22,y-length),fill=color,width=2)
    if rng.random()<.13:draw.ellipse((x-2,y-length-3,x+2,y-length+2),fill=(171,157,104,220))

# A pine grove anchors the left side, with independently shaped bough tiers.
def pine(x,y,height):
    draw.line((x,y,x+height*.012,y-height),fill=(40,59,50,255),width=max(3,int(height*.025)))
    for j in range(10):
        down=j*.091
        half=height*(.018+j*.026)
        tip=y-height+height*down
        fill=(34+j*2,66+j*2,57+j)
        draw.polygon([(x,tip),(x-half,tip+height*.18),(x-half*.38,tip+height*.15),(x,tip+height*.23),(x+half,tip+height*.18)],fill=(*fill,255))
for x,y,h in [(95,1340,426),(300,1290,300),(412,1330,388),(566,1300,237),(645,1338,196)]:
    pine(x,y,h)
# One sprawling deciduous tree on the right: visible branching, open leaf clusters.
base=(2295,1370)
trunk=[(2268,1385),(2284,1190),(2266,1110),(2294,990),(2312,990),(2296,1130),(2323,1220),(2325,1385)]
draw.polygon(trunk,fill=(68,64,48,255))
branches=[(2297,1135,2170,1052,17),(2296,1090,2398,991,15),(2289,1178,2428,1120,12),(2293,1050,2242,965,12),(2288,1154,2118,1132,11)]
for x,y,ex,ey,width in branches:
    draw.line((x,y,ex,ey),fill=(68,64,48,255),width=width)
    draw.line((ex,ey,ex+(ex-x)*.22,ey-42),fill=(68,64,48,255),width=max(3,width//2))
for cx,cy,rx,ry in [(2165,1020,120,75),(2260,953,123,88),(2395,977,134,80),(2460,1080,105,74),(2125,1113,105,70),(2310,1050,110,72)]:
    for _ in range(23):
        angle=rng.random()*math.tau
        radius=rng.random()**.5
        x=cx+math.cos(angle)*rx*radius;y=cy+math.sin(angle)*ry*radius
        size=rng.randrange(22,52)
        color=rng.choice([(94,116,65,255),(114,130,70,255),(130,139,75,255),(145,145,80,255),(79,105,63,255)])
        draw.ellipse((x-size,y-size*.72,x+size,y+size*.72),fill=color)
# Foreground stones and grasses frame the bottom without busy ornament.
for x,y,r in [(894,1390,35),(967,1424,49),(2015,1406,37),(1870,1436,26)]:
    draw.ellipse((x-r,y-r*.45,x+r,y+r*.45),fill=(94,110,100,255))
    draw.arc((x-r,y-r*.45,x+r,y+r*.45),185,320,fill=(143,153,132,255),width=3)
ROOT.mkdir(parents=True,exist_ok=True)
image.save(ROOT/'foreground.png',optimize=True)
manifest={'schemaVersion':1,'id':'woodland','name':'Woodland River','horizon':.72,'foreground':'foreground.png',
          'description':'An original illustrated river meadow, layered hills, pine grove and open-canopy oak. Transparent sky for native weather animation.',
          'author':'DynWall local illustration','license':'CC0-1.0'}
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(ROOT/'foreground.png')
