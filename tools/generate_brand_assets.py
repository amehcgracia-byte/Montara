"""Render the existing SVG brand symbol, without a wordmark, for video overlays."""
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def symbol(width=480,height=400):
    scale=4
    image=Image.new('RGBA',(width*scale,height*scale))
    draw=ImageDraw.Draw(image)
    sx,sy=width*scale/120,height*scale/100
    for rect in ElementTree.parse(ROOT/'web/mark.svg').getroot():
        x,y,w,h,rx=(float(rect.get(k,0)) for k in ('x','y','width','height','rx'))
        draw.rounded_rectangle((x*sx,y*sy,(x+w)*sx,(y+h)*sy),radius=rx*sx,fill=rect.get('fill'))
    return image.resize((width,height),Image.Resampling.LANCZOS)

if __name__=='__main__':
    output=ROOT/'web/brand'
    icon=symbol()
    icon.save(output/'montara-watermark.png')
    card=Image.new('RGB',(1920,1080),'black')
    logo=symbol(360,300)
    card.paste(logo,((1920-logo.width)//2,(1080-logo.height)//2),logo)
    card.save(output/'montara-logo.png')
