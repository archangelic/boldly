#!/usr/bin/env python3
import json
import os
from pprint import pprint
import random

import flickrapi
import halftone
from mastodon import Mastodon
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests

with open('config.json') as f:
    config = json.load(f)
apikey = config['flickrkey']
apisecret = config['flickrsecret']
flickr = flickrapi.FlickrAPI(apikey, apisecret, format='parsed-json')

mastodon = Mastodon(
    client_id=config['mast_client'],
    client_secret=config['mast_secret'],
    access_token=config['mast_key'],
    api_base_url=config['mast_base_url']
)

WIDTH = 640
HEIGHT = 360

def get_image():
    with open('words.txt') as f:
        rand_word = random.choice(f.read().split())
    print(rand_word)
    p = flickr.photos.search(
        text=rand_word,
        per_page=500,
        extras='url_l,tags',
        safesearch=2,
    )
    print(len(p['photos']['photo']))
    photos = []
    for i in p['photos']['photo']:
        try:
            if int(i['width_l']) >= WIDTH-20 and int(i['height_l']) >= HEIGHT-20:
                photos.append(i)
        except:
            continue
    photo = random.choice(photos)
    purl = photo['url_l']
    if 'food' in photo['tags']:
        print('contains food')
        return None, None
    pprint(photo)
    r = requests.get(purl)
    with open('fimage.jpg', 'wb') as f:
        f.write(r.content)
    pic = Image.open('fimage.jpg')
    return pic, rand_word

def select_section(pic):
    w = WIDTH - 20
    h = HEIGHT - 20
    x = [i for i in range(pic.size[0] - w)]
    y = [i for i in range(pic.size[1] - h)]
    left = random.choice(x)
    right = left + w
    top = random.choice(y)
    bottom = top + h
    pic = pic.crop((left, top, right, bottom))
    return pic

def get_font_size(word):
    size_w = WIDTH - 120
    size_h = HEIGHT - 120
    x = 16
    font = ImageFont.truetype('couture-bldit.ttf', x)
    w, h = font.getsize(word)
    while w <= size_w and h <= size_h:
        x += 1
        font = ImageFont.truetype('couture-bldit.ttf', x)
        w, h = font.getsize(word)
    if w > size_w or h > size_h:
        x -= 1
    return ImageFont.truetype('couture-bldit.ttf', x)

def post_to_mastodon(pic_path, text):
    desc = "generated black and white image with the word {} in bold font overlaid".format(text)
    pic = mastodon.media_post(pic_path, description=desc)
    mastodon.status_post(text, media_ids=[pic])

def cleanup():
    images = [i for i in os.listdir() if i.endswith(('.jpg', '.png', '.gif'))]
    for i in images:
        os.remove(i)

def main():
    pic = None
    while not pic:
        try:
            pic, word = get_image()
        except Exception as e:
            print(e)
            continue
    word = word.upper()
    h = halftone.Halftone('fimage.jpg')
    h.make(style='grayscale', angles=[random.randrange(360)])
    pic = Image.open('fimage_halftoned.jpg')
    pic = pic.filter(ImageFilter.DETAIL)
    pic = pic.filter(ImageFilter.SHARPEN)
    pic = select_section(pic)
    border = Image.new('RGB', (WIDTH, HEIGHT))
    border.paste(pic, (10, 10))
    pic = border
    font = get_font_size(word)
    x,y = font.getsize(word)
    inset = Image.new('RGB', (x+20, y+20))
    draw = ImageDraw.Draw(inset)
    draw.text((10, 10), word, (255, 255, 255), font=font)
    pic.paste(inset, ((WIDTH - (x+20))//2, (HEIGHT - (y+20))//2))
    pic.save('output.png')
    try:
        post_to_mastodon('output.png', word)
    except Exception as e:
        print(e)
    cleanup()

if __name__ == '__main__':
    main()
