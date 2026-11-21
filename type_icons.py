"""Simple source-controlled vector-like type symbols; no external assets."""
from PIL import ImageDraw

# Shapes are drawn from semantic type families and a distinct three-letter mark.
FAMILY={'afs':'air','avi':'air','fgt':'air','stk':'air','ada':'ground','art':'ground','asu':'ground','def':'ground','fpv':'air','inf':'ground','mbt':'ground','mob':'ground','frt':'ground','aas':'air','lan':'space','par':'air','sct':'space','ses':'space','ssu':'space','mis':'missile','car':'naval','cbt':'naval','esc':'naval','sub':'naval','tsb':'naval','tsp':'naval'}

def draw_icon(draw: ImageDraw.ImageDraw, code: str, rect, ink='#ffffff'):
    x0,y0,x1,y1=rect; cx=(x0+x1)//2; cy=(y0+y1)//2
    white=ink; family=FAMILY.get(code,'ground')
    draw.rounded_rectangle(rect,radius=20,outline=white,width=5)
    if family=='air':
        draw.polygon([(cx,y0+21),(cx+19,cy-5),(x1-21,cy+20),(x1-21,cy+34),(cx+14,cy+22),(cx+10,y1-47),(cx,y1-34),(cx-10,y1-47),(cx-14,cy+22),(x0+21,cy+34),(x0+21,cy+20),(cx-19,cy-5)],fill=white)
    elif family=='naval':
        draw.polygon([(x0+22,cy-8),(x1-22,cy-8),(x1-39,cy+36),(x0+39,cy+36)],outline=white)
        draw.line([(x0+32,cy+48),(cx-20,cy+54),(cx+22,cy+48),(x1-32,cy+54)],fill=white,width=5)
    elif family=='space':
        draw.ellipse((cx-31,cy-31,cx+31,cy+31),outline=white,width=5)
        draw.arc((x0+20,y0+53,x1-20,y1-53),15,165,fill=white,width=5)
        draw.arc((x0+20,y0+53,x1-20,y1-53),195,345,fill=white,width=5)
    elif family=='missile':
        draw.polygon([(cx,y0+21),(cx+20,cy+12),(cx+20,y1-44),(cx,y1-29),(cx-20,y1-44),(cx-20,cy+12)],outline=white)
        draw.line((cx-20,cy+20,cx+20,cy+20),fill=white,width=5)
    else:
        draw.rectangle((x0+28,cy-32,x1-28,cy+25),outline=white,width=5)
        draw.ellipse((x0+39,cy+22,x0+67,cy+50),outline=white,width=5)
        draw.ellipse((x1-67,cy+22,x1-39,cy+50),outline=white,width=5)
