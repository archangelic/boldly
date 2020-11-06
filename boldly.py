#!/usr/bin/env python3
import json
import os
from pprint import pprint
import random

import click
import flickrapi
import halftone
from mastodon import Mastodon
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
import tweepy

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

twconf = config['twitter']

twauth = tweepy.OAuthHandler(twconf['consumer_key'], twconf['consumer_secret'])
twauth.set_access_token(twconf['access_token'], twconf['access_secret'])

twapi = tweepy.API(twauth)

def get_image(width, height, word=''):
    if not word:
        with open('words.txt') as f:
            word = random.choice(f.readlines()).strip()
        print(word)
    p = flickr.photos.search(
        text=word,
        per_page=500,
        extras='url_o,o_dims,tags',
        safesearch=2,
    )
    print(len(p['photos']['photo']))
    photos = []
    for i in p['photos']['photo']:
        try:
            if int(i['width_o']) >= width-20 and int(i['height_o']) >= height-20:
                photos.append(i)
        except:
            continue
    print(len(photos))
    photo = random.choice(photos)
    purl = photo['url_o']
    if 'food' in photo['tags']:
        print('contains food')
        return None, None
    pprint(photo)
    r = requests.get(purl)
    with open('fimage.jpg', 'wb') as f:
        f.write(r.content)
    pic = Image.open('fimage.jpg')
    return pic, word

def select_section(pic, width, height, b_width):
    w = width - (b_width * 2)
    h = height - (b_width * 2)
    x = [i for i in range(pic.size[0] - w)]
    y = [i for i in range(pic.size[1] - h)]
    left = random.choice(x)
    right = left + w
    top = random.choice(y)
    bottom = top + h
    pic = pic.crop((left, top, right, bottom))
    return pic

def get_font_size(word, width, height, margin):
    margin = margin * 2
    size_w = width - margin
    size_h = height - margin
    x = 16
    font = ImageFont.truetype('couture-bldit.ttf', x)
    w, h = font.getsize_multiline(word)
    while w <= size_w and h <= size_h:
        x += 1
        font = ImageFont.truetype('couture-bldit.ttf', x)
        w, h = font.getsize_multiline(word)
    if w > size_w or h > size_h:
        x -= 1
    return ImageFont.truetype('couture-bldit.ttf', x)

def post_to_mastodon(pic_path, text):
    desc = "generated black and white image with the word {} in bold font overlaid".format(text)
    pic = mastodon.media_post(pic_path, description=desc)
    mastodon.status_post(text, media_ids=[pic])

def post_to_twitter(pic_path, text):
    twapi.update_with_media(pic_path, text)

def cleanup():
    images = [i for i in os.listdir() if i.endswith(('.jpg', '.png', '.gif'))]
    for i in images:
        os.remove(i)

@click.command()
@click.option('--palette', '-p', default=None)
@click.option('--width', '-w', default=1920)
@click.option('--height', '-h', default=1080)
@click.option('--social/--nosocial', default=True)
@click.option('--text', '-t', default='')
@click.option('--search', '-z', default='')
def main(palette, width, height, social, text, search):
    palettes = {
        'classic': {
            'colorstr': '#000000',
            'txtcolor': (255, 255, 255)
        },
        'white': {
            'colorstr': '#ffffff',
            'txtcolor': (0, 0, 0)
        },
        'barbara': {
            'colorstr': '#e34234',
            'txtcolor': (255, 255, 255)
        },
        'town': {
            'colorstr': '#e0B0ff',
            'txtcolor': (0, 0, 0)
        },
    }
    pic = None
    while not pic:
        try:
            pic, word = get_image(width, height, search)
        except Exception as e:
            print(e)
            continue
    if text:
        word = text.upper()
    else:
        word = word.upper()
    if palette:
        color = palettes[palette]
    else:
        color = palettes[random.choice(list(palettes.keys()))]


    if height <= width:
        b_width = height // 40
        f_margin = width // 8
    elif width < height:
        b_width = width // 40
        f_margin = height // 8

    b_double = b_width * 2

    h = halftone.Halftone('fimage.jpg')
    h.make(style='grayscale', angles=[random.randrange(360)])
    pic = Image.open('fimage_halftoned.jpg')
    pic = pic.filter(ImageFilter.DETAIL)
    pic = pic.filter(ImageFilter.SHARPEN)
    pic = select_section(pic, width, height, b_width)


    border = Image.new('RGB', (width, height), color=color['colorstr'])
    border.paste(pic, (b_width, b_width))
    pic = border
    font = get_font_size(word, width, height, f_margin)
    x,y = font.getsize_multiline(word)
    inset = Image.new('RGB', (x+b_double, y+b_double), color=color['colorstr'])
    draw = ImageDraw.Draw(inset)
    draw.text((b_width, b_width), word, color['txtcolor'], font=font)
    pic.paste(inset, ((width - (x+b_double))//2, (height - (y+b_double))//2))
    pic.save('output.png')
    if social:
        try:
            post_to_mastodon('output.png', word)
        except Exception as e:
            print(e)
        try:
            post_to_twitter('output.png', word)
        except Exception as e:
            print(e)
        cleanup()

if __name__ == '__main__':
    main()
