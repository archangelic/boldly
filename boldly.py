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
    word_lines = [l.strip() for l in word.split('\n')]
    margin = margin * 2
    size_w = width - margin
    size_h = height - (margin + ((len(word_lines) - 1) * 10))
    x = 16
    font = ImageFont.truetype('couture-bldit.ttf', x)
    w, h = font.getsize_multiline(word)
    while w <= size_w and h <= size_h:
        x += 1
        font = ImageFont.truetype('couture-bldit.ttf', x)
        w, h = font.getsize_multiline(word)
    if w > size_w or h > size_h:
        x -= 1
    return x


def crop_circle(pic):
    h, w = pic.size
    lum_img = Image.new('L', [h, w], 0)
    draw = ImageDraw.Draw(lum_img)
    draw.pieslice([(0, 0), (h, w)], 0, 360, fill=255)
    img_arr = np.array(pic)
    lum_img_arr = np.array(lum_img)
    final_img_arr = np.dstack((img_arr, lum_img_arr))
    return Image.fromarray(final_img_arr)


def add_filter(pic, color, width, height, b_width, trans, ireland, watermelon):
    if trans:
        layer = make_trans_flag((width, height))
        layer = layer.crop((b_width, b_width, width-b_width, height-b_width))
    elif ireland:
        layer = make_irish_flag((width, height))
        layer = layer.crop((b_width, b_width, width-b_width, height-b_width))
    elif watermelon:
        layer = make_watermelon((width, height))
        layer = layer.crop((b_width, b_width, width-b_width, height-b_width))
    else:
        layer = Image.new('RGBA', pic.size, color)
    # pic.paste(layer, (0, 0), layer)
    pic = Image.blend(layer, pic.convert('RGBA'), 0.5)
    return pic


def make_trans_flag(size):
    width, height = size
    bands = height // 5
    fl = Image.new('RGBA', (width, height), '#55CDFC')
    pink = Image.new('RGBA', (width, bands*3), '#F7A8B8')
    white = Image.new('RGBA', (width, bands), '#FFFFFF')
    fl.paste(pink, (0, bands))
    fl.paste(white, (0, bands*2))
    return fl


def make_irish_flag(size):
    width, height = size
    bands = width // 3
    fl = Image.new('RGBA', (width, height), '#FFFFFF')
    green = Image.new('RGBA', (bands, height), '#169B62')
    orange = Image.new('RGBA', (bands, height), '#FF883E')
    fl.paste(green, (0, 0))
    fl.paste(orange, (bands*2, 0))
    return fl

def make_watermelon(size):
    width, height = size
    bands = height // 3
    fl = Image.new('RGBA', (width, height), '#FFFFFF')
    black = Image.new('RGBA', (width, bands), '#000000')
    green = Image.new('RGBA', (width, bands), '#009736')
    fl.paste(black, (0, 0))
    fl.paste(green, (0, bands*2))
    draw = ImageDraw.Draw(fl)
    draw.polygon([(0,0), (0,height), (width//3,height//2)], fill='#EE2A35')
    return fl

def post_to_mastodon(pic_path, text, alt_text):
    pic = mastodon.media_post(pic_path, description=alt_text)
    mastodon.status_post(text, media_ids=[pic])


def post_to_twitter(pic_path, text, alt_text):
    media = twapi.media_upload(pic_path)
    twapi.create_media_metadata(media.media_id, alt_text)
    twapi.update_status(text, media_ids=[media.media_id])


def cleanup():
    images = [i for i in os.listdir() if i.endswith(('.jpg', '.png', '.gif'))]
    for i in images:
        os.remove(i)


@click.command()
@click.option('--palette', '-p', default=None)
@click.option('--width', '-w', default=1920)
@click.option('--height', '-h', default=1080)
@click.option('--social/--nosocial', default=True)
@click.option('--avatar', is_flag=True)
@click.option('--text', '-t', default='')
@click.option('--search', '-z', default='')
@click.option('--post', '-o', default='')
@click.option('--clean', is_flag=True)
@click.option('--flag', is_flag=True)
@click.option('--photo', default=None)
def main(palette, width, height, social, avatar, text, search, post, clean, flag, photo):
    if clean:
        cleanup()
        quit()

    if flag:
        f = make_trans_flag((width, height))
        f.save('flag.png')
        quit()

    palettes = {
        'classic': {
            'colorstr': '#000000',
            'txtcolor': (255, 255, 255),
            'a11y': 'image composed of black and white circles with a black border. a black rectangle inset with "WORD" in bold white text is in the center'
        },
        'white': {
            'colorstr': '#ffffff',
            'txtcolor': (0, 0, 0),
            'a11y': 'image composed of black and white circles with a white border. a white rectangle inset with "WORD" in bold black text is in the center'
        },
        'barbara': {
            'colorstr': '#e34234',
            'txtcolor': (255, 255, 255),
            'a11y': 'image composed of black and white circles with a red border. a red rectangle inset with "WORD" in bold white text is in the center'
        },
        'town': {
            'colorstr': '#e0B0ff',
            'txtcolor': (0, 0, 0),
            'a11y': 'image composed of black and white circles with a pink border. a pink rectangle inset with "WORD" in bold black text is in the center'
        },
        'rage': {
            'exclusive': True,
            'colorstr': '#901312',
            'txtcolor': (20, 1, 1),
            'filter': '341312',
            'a11y': 'image composed of black and dark red circles with a red border. a red rectangle inset with "WORD" in bold black text is in the center'
        },
        'trans': {
            'exclusive': True,
            'trans': True,
            'colorstr': '#F7A8B8',
            'txtcolor': (255, 255, 255),
            'border': '#55CDFC',
            'filter': 'F7A8B8',
            'a11y': 'image composed of various circles with a blue, pink, and white trangender pride flag superimposed. The image is surrounded with a blue border. a pink rectangle inset with "WORD" in bold white text is in the center'
        },
        'ireland': {
            'exclusive': True,
            'ireland': True,
            'colorstr': '#FF883E',
            'txtcolor': (255, 255, 255),
            'border': '#FF883E',
            'filter': 'FF883E',
            'a11y': 'image composed of various circles with green, white, and orange irish flag superimposed. The image is surrounded with an irish flag border. an orange rectangle inset with "WORD" in bold white text is in the center'
        },
        'watermelon': {
            'exclusive': True,
            'watermelon': True,
            'colorstr': '#009736',
            'txtcolor': (255, 255, 255),
            'border': '#009736',
            'filter': '009736',
            'a11y': 'image composed of various circles with black, white, and green horizontal stripes and a red triangle on the left side. It is the flag of palestine. A green rectangle inset with "WORD" in bold white text is in the center'
        },
        'twitch': {
            'exclusive': True,
            'colorstr': '#523d5f',
            'filter': '523d5f',
            'txtcolor': (237, 175, 235)
        }
    }

    # make an avatar for boldly
    if avatar:
        if not text:
            text = 'boldly'
        width = 720
        height = 720

    # finds a pic from flickr to start off
    pic = None
    while not pic:
        try:
            pic, word = get_image(width, height, search)
        except Exception as e:
            print(e)
            continue
    if photo:
        pic = Image.open(photo)
        pic.save('fimage.jpg')
    if text:
        word = text.upper()
    else:
        word = word.upper()
    if palette:
        color = palettes[palette]
    else:
        palette = random.choice([p for p in palettes if not palettes[p].get('exclusive')])
        color = palettes[palette]

    # sets borders and margins
    if height <= width:
        b_width = height // 40
        f_margin = width // 8
    elif width < height:
        b_width = width // 40
        f_margin = height // 8
    b_double = b_width * 2

    # halftone the image
    h = halftone.Halftone('fimage.jpg')
    h.make(style='grayscale', angles=[random.randrange(360)], sample=20)

    # crop the image
    pic = Image.open('fimage_halftoned.jpg')
    pic = select_section(pic, width, height, b_width)

    # add a filter if necessary
    if color.get('filter'):
        r, g, b = bytes.fromhex(color['filter'])
        ctuple = (r, g, b, 255)
        pic = add_filter(pic, ctuple, width, height, b_width, trans=color.get('trans'), ireland=color.get('ireland'), watermelon=color.get('watermelon'))

    # make an avatar
    if avatar:
        pic = crop_circle(pic.convert('RGB'))

    # paste it together
    empty_layer = Image.new('RGBA', (width, height))
    empty_layer.paste(pic, (b_width, b_width))
    pic = empty_layer

    # make the border layer
    if color.get('border'):
        border_color = color['border']
    else:
        border_color = color['colorstr']
    if color.get('trans'):
        border = make_trans_flag((width, height)).convert('RGB')
    elif color.get('ireland'):
        border = make_irish_flag((width, height)).convert('RGB')
    elif color.get('watermelon'):
        border = make_watermelon((width, height)).convert('RGB')
    else:
        border = Image.new('RGB', (width, height), color=border_color)
    if avatar:
        border = crop_circle(border)

    # paste the pic and border
    pic = Image.alpha_composite(border.convert('RGBA'), pic)

    # add the text
    font_size = get_font_size(word, width, height, f_margin)
    font = ImageFont.truetype('couture-bldit.ttf', font_size)
    _, box_height = font.getsize_multiline(word)
    line_cnt = len(word.split('\n'))
    box_zero = (height - (b_double * line_cnt) - box_height)//2
    z = 0
    for l in word.split('\n'):
        l = l.strip()
        x, y = font.getsize_multiline(l)
        print(x, y, box_zero + z + b_double)
        inset = Image.new('RGB', (x+b_double, y+b_double), color=color['colorstr'])
        draw = ImageDraw.Draw(inset)
        draw.text((b_width, b_width), l, color['txtcolor'], font=font)
        pic.paste(inset, ((width - (x+b_double))//2, box_zero + z))
        z += y + b_double + 10

    # save to filesystem
    pic.save('output.png')

    # post it
    if social and not avatar:
        word = word.replace('\n', ' ')
        if post:
            post_text = post
        else:
            post_text = word
        alt_text = color['a11y'].replace('WORD', word)
        try:
            post_to_mastodon('output.png', post_text, alt_text)
        except Exception as e:
            print(e)
#        try:
#             post_to_twitter('output.png', post_text, alt_text)
#         except Exception as e:
#             print(e)
        cleanup()

    # update avatar
    if avatar and social:
        try:
            mastodon.account_update_credentials(avatar='output.png')
        except Exception as e:
            print(e)
#         try:
#             twapi.update_profile_image('output.png')
#         except Exception as e:
#             print(e)
        cleanup()


if __name__ == '__main__':
    main()
