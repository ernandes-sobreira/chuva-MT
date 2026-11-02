#!/usr/bin/env python3
"""Prancha cientifica baseada em 4 PNGs gerados diretamente do MapBiomas no Earth Engine."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import math
P=Path("pesquisa_pantanal/caceres/resultados")
D=Path("pesquisa_pantanal/cartografia")
D.mkdir(parents=True,exist_ok=True)
W,H=1870,2590
img=Image.new("RGB",(W,H),(248,250,249))
d=ImageDraw.Draw(img)
font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
bold_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(sz,bold=False):
 try:return ImageFont.truetype(bold_path if bold else font_path,sz)
 except:return ImageFont.load_default()
navy=(29,55,66);grey=(88,110,119);blue=(28,128,176);sand=(206,165,107)
def put(txt,x,y,size=26,col=navy,bold=False):
 d.text((x,y),txt,font=font(size,bold),fill=col)
def pill(text,x,y,color):
 bb=d.textbbox((x,y),text,font=font(21,True))
 d.rounded_rectangle([x-13,y-9,bb[2]+13,bb[3]+10],radius=14,fill=color)
 d.text((x,y),text,font=font(21,True),fill=(255,255,255))
put("Pantanal de Cáceres",70,45,57,navy,True)
put("Água e pastagens mapeadas por satélite | Comparação 1988 × 2024",71,120,29,grey)
d.line([(70,185),(1800,185)],fill=(190,207,210),width=2)
put("A · Superfície anual de água e pastagem plantada",70,215,31,navy,True)
pill("1988",99,282,(33,87,114));pill("2024",1025,282,(33,87,114))
data=[
 ("MAPA_REAL_CACERES_AGUA_PASTAGEM_1988.png",96,332),
 ("MAPA_REAL_CACERES_AGUA_PASTAGEM_2024.png",1018,332),
 ("MAPA_REAL_CACERES_MESES_INUNDADOS_1988.png",96,1468),
 ("MAPA_REAL_CACERES_MESES_INUNDADOS_2024.png",1018,1468)]
for file,x,y in data:
 if not (P/file).exists():raise RuntimeError("Raster ausente: "+file)
 im=Image.open(P/file).convert("RGBA")
 bw=738; bh=875
 im.thumbnail((bw,bh),Image.Resampling.LANCZOS)
 bg=Image.new("RGBA",im.size,(255,255,255,255))
 bg.alpha_composite(im)
 d.rounded_rectangle([x-9,y-8,x+bw+8,y+bh+8],radius=14,fill=(255,255,255),outline=(214,224,225),width=2)
 img.paste(bg.convert("RGB"),(x,y))
 # Marcador de Caceres: posicao geografica calculada para a malha original.
 px=( -57.681-(-58.63) )/( -57.44-(-58.63) )*760
 py=( -14.79-(-16.075) )/( -14.79-(-16.42) )*900
 px=x+px*(im.width/760)
 py=y+py*(im.height/900)
 if "AGUA_PASTAGEM" in file:
  d.ellipse((px-6,py-6,px+6,py+6),fill=(240,70,60),outline=(255,255,255),width=2)
  d.rounded_rectangle((px-86,py-40,px+30,py-11),radius=8,fill=(255,255,255))
  d.text((px-82,py-39),"Cáceres",font=font(20,True),fill=navy)
put("Legenda:",105,1260,25,navy,True)
d.rectangle((225,1265,250,1290),fill=blue);put("Água detectada",263,1261,25,grey)
d.rectangle((620,1265,645,1290),fill=sand);put("Pastagem plantada",657,1261,25,grey)
d.rectangle((1081,1265,1106,1290),fill=(237,241,237));put("Demais coberturas",1118,1261,25,grey)
put("B · Meses com presença de água em cada pixel",70,1360,31,navy,True)
pill("1988",99,1420,(33,87,114));pill("2024",1025,1420,(33,87,114))
# Barra de cores da frequencia da agua (valores mais altos = mais meses)
levels=[(237,244,237),(195,219,224),(136,199,223),(68,142,174),(17,76,134)]
d.rectangle((115,2401,1620,2415),fill=(237,244,237))
for i in range(1500):
 t=i/1499
 ind=min(3,int(t*4))
 u=t*4-ind
 a=levels[ind];b=levels[ind+1]
 c=tuple(round(a[k]*(1-u)+b[k]*u) for k in range(3))
 d.line((115+i,2397,115+i,2427),fill=c,width=1)
put("0 meses",115,2438,23,grey);put("3",490,2438,23,grey);put("6",860,2438,23,grey);put("9",1240,2438,23,grey);put("12 meses",1474,2438,23,grey)
d.line([(70,2512),(1800,2512)],fill=(195,210,214),width=2)
put("MapBiomas Água C5 e Cobertura C11; HydroBASINS nível 6. Extração via GEE em 02/11/2026.",70,2524,20,grey)
put("Recorte: unidade hidrográfica local de Cáceres. A comparação entre anos NÃO indica perda permanente.",70,2550,20,grey)
out=D/"PRANCHA_MAPAS_REAIS_CACERES_1988_2024.png"
img.save(out,optimize=True)
print("Prancha:",out,"bytes",out.stat().st_size)
