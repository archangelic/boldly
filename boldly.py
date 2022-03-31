#!/usr/bin/env python3
import json
import os
import random
from pprint import pprint

import click
import flickrapi
import numpy as np
import requests
import tweepy
from mastodon import Mastodon
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import halftone

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
        extras='url_o,o_dims,tags'
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


def crop_circle(pic):
    h, w = pic.size
    lum_img = Image.new('L', [h, w], 0)
    draw = ImageDraw.Draw(lum_img)
    draw.pieslice([(0, 0), (h, w)], 0, 360, fill=255)
    img_arr = np.array(pic)
    lum_img_arr = np.array(lum_img)
    final_img_arr = np.dstack((img_arr, lum_img_arr))
    return Image.fromarray(final_img_arr)


def add_filter(pic, color):
    layer = Image.new('RGBA', pic.size, color)
    # pic.paste(layer, (0, 0), layer)
    pic = Image.blend(layer, pic.convert('RGBA'), 0.25)
    return pic


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
@click.option('--avatar', default=False)
@click.option('--text', '-t', default='')
@click.option('--search', '-z', default='')
def main(palette, width, height, social, avatar, text, search):
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
        'rage': {
            'colorstr': '#901312',
            'txtcolor': (20, 1, 1),
            'filter': '341312'
        }
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
        color = palettes[random.choice(['classic', 'white', 'barbara', 'town'])]

    if height <= width:
        b_width = height // 40
        f_margin = width // 8
    elif width < height:
        b_width = width // 40
        f_margin = height // 8

    b_double = b_width * 2

    h = halftone.Halftone('fimage.jpg')
    h.make(style='grayscale', angles=[random.randrange(360)], sample=20)
    pic = Image.open('fimage_halftoned.jpg')
    if palette:
        if palette == 'rage':
            r, g, b = bytes.fromhex(color['filter'])
            ctuple = (r, g, b, 255)
            pic = add_filter(pic, ctuple)
    pic = pic.filter(ImageFilter.DETAIL)
    pic = pic.filter(ImageFilter.SHARPEN)
    pic = select_section(pic, width, height, b_width)
    if avatar:
        pic = crop_circle(pic)
    empty_layer = Image.new('RGBA', (width, height))
    empty_layer.paste(pic, (b_width, b_width))
    pic = empty_layer
    border = Image.new('RGB', (width, height), color=color['colorstr'])
    if avatar:
        border = crop_circle(border)
    pic = Image.alpha_composite(border.convert('RGBA'), pic)
    font = get_font_size(word, width, height, f_margin)
    x, y = font.getsize_multiline(word)
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
