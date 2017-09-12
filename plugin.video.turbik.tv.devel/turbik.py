#!/usr/bin/python
# -*- coding: utf-8 -*-

import base64
import hashlib
import os
import random
import re
import requests
import simplejson as json
import urllib
import urlparse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from bs4 import BeautifulSoup
from elementtree import ElementTree

addon_id = 'plugin.video.turbik.tv.devel'
addon = xbmcaddon.Addon(id=addon_id)

def sign_out():
    xbmc.log('removing stuff')
    addon.setSetting('username', '')
    addon.setSetting('password', '')
    addon.setSetting('IAS_ID', '')

if sys.argv[1] == 'sign_out':
    sign_out()
    sys.exit()

string = addon.getLocalizedString

handle = int(sys.argv[1])
PLUGIN_NAME = 'turbik.tv'
SITE_HOSTNAME = addon.getSetting('site')
SITEPREF = 'https://%s' % SITE_HOSTNAME
SITE_URL = SITEPREF + '/'


class Player(xbmc.Player):
    pos = 0

    def __init__(self, info_dict, *args, **kwargs):
        self.episode = 'S%sE%s' % (info_dict['season'], info_dict['episode'])
        self.title = info_dict['show_title_en']
        self.playing = 1
        self.storage = Storage()
        self.sub_file = info_dict['sub_file']
        _, self.seek = self.storage.get(self.title, self.episode)
        super(Player, self).__init__(*args, **kwargs)

    def onPlayBackStarted(self):
        self.playing = 2
        if self.seek:
            self.seekTime(self.seek)
        if self.sub_file:
            self.setSubtitles(self.sub_file)
            self.showSubtitles(True)

    def onPlayBackEnded(self):
        self.playing = 0
        self.storage.set(self.title, self.episode, 1, 0)

    def onPlayBackStopped(self):
        self.playing = 0
        self.storage.set(self.title, self.episode, -1, self.pos)


class Storage():
    uri = 'special://userdata/addon_data/' + addon_id + '/storage.json'
    filename = xbmc.translatePath(uri)

    def __init__(self, uri=None):
        if uri:
            self.uri = uri
            self.filename = xbmc.translatePath(uri)

    def load_dict(self):
        try:
            with open(self.filename, 'r') as f:
                info = json.load(f)
        except IOError:
            info = {}
        return info

    def dump_dict(self, info):
        with open(self.filename, 'wb') as f:
            json.dump(info, f, sort_keys=True, indent=4 * ' ')

    def get(self, title, episode):
        info = self.load_dict()

        if info.get(title):
            if info[title].get(episode):
                return info[title][episode]
        return (0, 0)

    def set(self, title, episode, played, pos):
        info = self.load_dict()
        if not info.get(title):
            info.update(
                {
                    title: {
                        episode: (played, pos)
                    }
                }
            )
        elif not info[title].get(episode):
            info[title].update({episode: (played, pos)})
        else:
            info[title][episode] = (played, pos)
        self.dump_dict(info)


def show_notification(text, time=5000):
    xbmc.executebuiltin(
        'Notification(%s, %s, %d, %s)' % (
         PLUGIN_NAME,
         text,
         time,
         addon.getAddonInfo('icon'))
    )

def get_params():
    params = {'mode': None}
    params.update(urlparse.parse_qs(sys.argv[2][1:]))
    return params

def do_login():
    auth = {
        'login': addon.getSetting('username'),
        'passwd': addon.getSetting('password'),
        'remember': 'true'
    }
    url = SITE_URL + 'Signin'
    s = requests.Session()
    resp = s.post(url, data=auth)
    if resp.url == SITE_URL:
        addon.setSetting('IAS_ID', s.cookies['IAS_ID'])
        show_notification('Successfully logged in')
    else:
        xbmc.log('[%s] do_login() Error 1: Could not login with provided'
                 'credentials (User: %s, Pass: %s)' %
                 (PLUGIN_NAME, auth['login'], auth['passwd']))
        xbmcgui.Dialog().ok('turbik.tv', 'Could not login with '
                            'provided credentials')
        sign_out()
    return s

def first_run():
    if addon.getSetting('username') == '':
        user_keyboard = xbmc.Keyboard()
        user_keyboard.setHeading(string(30001))
        user_keyboard.doModal()
        if (user_keyboard.isConfirmed()):
            addon.setSetting('username', user_keyboard.getText())
    if addon.getSetting('password') == '':
        pass_keyboard = xbmc.Keyboard()
        pass_keyboard.setHeading(string(30002))
        pass_keyboard.setHiddenInput(True)
        pass_keyboard.doModal()
        if (pass_keyboard.isConfirmed()):
            addon.setSetting('password', pass_keyboard.getText())

def Get(url, ref=None):
    if addon.getSetting('IAS_ID') == '':
        s = do_login()
    else:
        s = requests.Session()
        cookie = {'IAS_ID': addon.getSetting('IAS_ID')}
    headers = {
        'User-Agent': 'Opera/9.80 (X11; Linux i686; U; ru) '
                      'Presto/2.6.30 Version/10.70',
        'Host': SITE_HOSTNAME,
        'Accept': 'text/html, application/xml, application/xhtml+xml, */*',
        'Accept-Language': 'ru,en;q=0.9'
    }
    if ref:
        headers.update({'Referer': ref})
    url = SITEPREF + url
    resp = s.get(url, headers=headers, cookies=cookie)
    return resp.text

def ShowSeries(url):
    http = Get(url)
    if http == None:
        xbmc.log('[%s] ShowSeries() Error 1: Not received '
                 'data when opening URL=%s' % (PLUGIN_NAME, url))
        show_notification('Could not fetch series list')
        return

    soup = BeautifulSoup(http, 'html.parser')
    div_series = soup.find(id='series')

    for show in div_series.find_all('a')[1:]:
        url = show.get('href')
        img = 'https:' + show.select_one('img').get('src')
        title_en = show.select_one('.serieslistboxen').text
        title_ru = show.select_one('.serieslistboxru').text
        data = '\n'.join(
            [x.text for x in show.select('.serieslistboxperstext')]
        )
        desc = show.select_one('.serieslistboxdesc').text.replace('\n', '')

        if addon.getSetting('language') == '0':
            title = '%s / %s' % (title_en, title_ru)
        else:
            title = '%s / %s' % (title_ru, title_en)

        icon = img.replace('s.jpg', '.png')
        large_img = img.replace('s.jpg', 'ts.jpg')
        listitem = xbmcgui.ListItem(title, iconImage=icon,
                                    thumbnailImage=large_img)
        listitem.setInfo(
            type='Video',
            infoLabels = {
                'Title': title,
                'Plot': desc,
                'FolderName': title_en,
            }
        )
        listitem.setProperty('Fanart_Image', large_img)

        params = {
            'mode': 'OpenSeries',
            'url': url,
            'title': title_en
        }
        url = sys.argv[0] + '?' + urllib.urlencode(params)
        xbmcplugin.addDirectoryItem(handle, url, listitem, True)

def OpenSeries(url, title):
    http = Get(url, ref=SITEPREF+'/Series/')
    if http == None:
        xbmc.log('[%s] OpenSeries() Error 1: Not received '
                 'data when opening URL=%s' % (PLUGIN_NAME, url))
        return
    soup = BeautifulSoup(http, 'html.parser')
    img = 'https:' + soup.select_one('.topimgseries').img.get('src')
    season_links = soup.select_one('.seasonnum').find_all('a')
    if len(season_links) == 1 or '/Season' in url:
        build_episodes_dir(soup)
    else:
        for link in season_links[::-1]:
            if addon.getSetting('language') == '0':
                season = link.text.replace(u'Сезон', 'Season')
            else:
                season = link.text
            listitem = xbmcgui.ListItem(season, thumbnailImage=img)
            listitem.setProperty('Fanart_Image', img)
            season_url = link.get('href')
            params = {
                'mode': 'OpenSeries',
                'url': season_url,
                'title': 'title'
            }
            url = sys.argv[0] + '?' + urllib.urlencode(params)
            xbmcplugin.addDirectoryItem(handle, url, listitem, True)

def build_episodes_dir(soup):
    storage = Storage()
    ep_links_div = soup.select_one('.sserieslistbox')
    show_title_en = soup.select_one('.sseriestitleten').text.encode('utf8')
    fanart = 'https:' + soup.select_one('.topimgseries').img.get('src')
    for link in ep_links_div.find_all('a')[::-1]:
        img = 'https:' + link.img.get('src')
        season = link.select_one('.sserieslistonetxtse').text\
                .replace(u'Сезон: ','').encode('utf8')
        episode = link.select_one('.sserieslistonetxtep').text\
                .replace(u'Эпизод: ','').encode('utf8')
        episode_full = 'S%sE%s' % (season, episode)
        playcount, seek = storage.get(show_title_en, episode_full)
        title_ru = episode + '. ' + link.select_one('.sserieslistonetxtru')\
                .text.encode('utf8')
        title_en = episode + '. ' + link.select_one('.sserieslistonetxten')\
                .text.encode('utf8')
        ep_url = link.get('href')
        listitem = xbmcgui.ListItem(title_en, thumbnailImage=img)
        listitem.setInfo(type='Video', infoLabels={'PlayCount': playcount})
        listitem.setProperty('Fanart_Image', fanart)
        url_data = {
            'mode': 'Watch',
            'url': ep_url,
            'img': img,
            'title': title_en,
        }
        url = sys.argv[0] + '?' + urllib.urlencode(url_data)
        xbmcplugin.addDirectoryItem(handle, url, listitem)

def get_meta(meta):
    TRANSFORM = [
        ('x', '2'),
        ('u', 'I'),
        ('Y', '0'),
        ('o', '='),
        ('k', '3'),
        ('n', 'Q'),
        ('g', '8'),
        ('r', 'V'),
        ('m', '7'),
        ('T', 'X'),
        ('w', 'G'),
        ('f', 'M'),
        ('d', 'R'),
        ('c', 'U'),
        ('e', 'H'),
        ('s', '4'),
        ('i', '1'),
        ('l', 'Z'),
        ('y', '5'),
        ('t', 'D'),
        ('p', 'N'),
        ('b', '6'),
        ('z', 'L'),
        ('a', '9'),
        ('J', 'B'),
        ('v', 'W')
    ]

    meta = meta.replace('%2b', '+')
    meta = meta.replace('%3d', '=')
    meta = meta.replace('%2f', '/')
    for pair in TRANSFORM:
        meta = meta.replace(pair[0], '___')
        meta = meta.replace(pair[1], pair[0])
        meta = meta.replace('___', pair[1])
    return base64.b64decode(meta)

def get_sub_timecode(seconds):
    try:
        sec, msec = seconds.split(',')
    except ValueError:
        sec, msec = seconds, '0'
    sec = int(sec)
    hr = sec // 3600
    mm = (sec % 3600) // 60
    ss = sec % 60
    return '%02d:%02d:%02d.%s' % (hr, mm, ss, msec)

def get_subtitles(url):
    sub_re = re.search(r'sub.turbik.tv\/(\ben\b|\bru\b)\/(\w+)$', url)
    lang, name = sub_re.groups()

    sub_storage = 'special://userdata/addon_data/' + addon_id
    sub_file = sub_storage + '/%s_%s.srt' % (lang, name)


    filename = xbmc.translatePath(sub_file)
    if not os.path.exists(filename):
        resp = requests.get(url)
        with open(filename, 'w') as f:
            et = ElementTree.fromstring(resp.text.encode('utf8'))
            for idx, sub in enumerate(et, 1):
                f.write(str(idx) + '\n')
                f.write(
                    '%s --> %s\n' %
                    (get_sub_timecode(sub[0].text),
                    get_sub_timecode(sub[1].text))
                )
                f.write(sub[2].text.encode('utf8'))
                f.write('\n\n')

    return sub_file

def process_meta(url):
    html = Get(url)

    if html == None:
        xbmc.log('[%s] Watch() Error 1: Not received data when opening URL=%s'
                 % (PLUGIN_NAME, url))
        show_notification('Could not open episode page')
        return

    soup = BeautifulSoup(html, 'html.parser')

    meta = soup.find(id='metadata')['value']
    plot = soup.select_one('.textdesc').text
    eid = soup.find(id='eid')['value']
    ep_hash = soup.find(id='hash')['value'][::-1]
    show_title_en = soup.select_one('.mains')\
            .select_one('.en').text.encode('utf8')
    show_title_ru = soup.select_one('.mains')\
            .select_one('.ru').text.encode('utf8')
    ep_title_en, ep_title_ru = \
        soup.select_one('.maine').contents[0].encode('utf8').split(' / ')
    episode, season = re.search(
        r'(\d+).*(\d+)',
        soup.select_one('.se').text.encode('utf8')).groups()

    quality = addon.getSetting('quality')
    language = addon.getSetting('language')
    subtitles = addon.getSetting('subtitles')

    et = ElementTree.fromstring(get_meta(meta).encode('utf-16-be'))

    if quality == '0' and et.find('hq').text == '1':
        source = et.find('sources2/hq').text
    elif quality == '1':
        source = et.find('sources2/default').text
    else:
        xbmc.log('[%s] Watch() Error 2: Not found HQ source for URL=%s'
                 ', Falling back to SQ' %
                 (PLUGIN_NAME, url))
        source = et.find('sources2/default').text
        show_notification('HQ video source not found,\n'
                          'falling back to SQ')

    if language == '1' and et.find('langs/ru').text == '1':
        lang = 'ru'
    elif language == '1' and et.find('langs/ru').text == '0':
        lang = 'en'
        xbmc.log(
            '[%s] Watch() Error 3: Not found ru audio source for URL=%s'
            ', Falling back to en audio' % (PLUGIN_NAME, url)
        )
        show_notification('Russian audio not found,\n'
                          'falling back to English audio')
    else:
        lang = 'en'

    sub_file = None
    if subtitles == '1' and et.find('subtitles/ru').text == '1':
        sub_file = get_subtitles(
            'https:' + et.find('subtitles/sources/ru').text
        )
    elif subtitles == '1' and et.find('subtitles/ru').text =='0':
        show_notification('Russian subtitles not found')
    elif subtitles == '0' and et.find('subtitles/en').text == '1':
        sub_file = get_subtitles(
            'https:' + et.find('subtitles/sources/en').text
        )

    screen = 'https:' + et.find('screen').text

    link = []
    link.append(hashlib.sha1(lang).hexdigest())
    link.append(eid)
    link.append(source)
    link.append('0') # Start time
    link.append(ep_hash)
    link.append(hashlib.sha1(ep_hash + str(random.random())).hexdigest())
    link.append(hashlib.sha1(link[-1] + eid + 'A2DC51DE0F8BC1E9').hexdigest())

    return {
        'url': 'http://cdn.turbik.tv/' + '/'.join(link),
        'plot': plot,
        'image': screen,
        'ep_title_en': ep_title_en,
        'ep_title_ru': ep_title_ru,
        'show_title_en': show_title_en,
        'show_title_ru': show_title_ru,
        'episode': episode,
        'season': season,
        'sub_file': sub_file
    }

def make_header_string(headers):
    header_list = []
    for header in headers.keys():
        header_list.append('%s=%s' %
                           (header, urllib.quote_plus(headers[header])))
    return '|' + '&'.join(header_list)

def PlayURL(info_dict):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.2'
                      ' (KHTML, like Gecko) Chrome/15.0.874.54 Safari/535.2',
        'Host': 'cdn.turbik.tv',
        'Accept': '*/*',
        'Accept-Language': 'ru,en;q=0.9',
        'Accept-Charset': 'iso-8859-1, utf-8, utf-16, *;q=0.1',
        'Accept-Encoding': 'deflate, gzip, x-gzip, identity, *;q=0',
        'Referer': 'http://turbik.tv/media/swf/Player20.swf',
        'Connection': 'Keep-Alive'
    }
    cookies = {
        'IAS_ID': addon.getSetting('IAS_ID'),
        '$Version': '1',
    }
    s = requests.Session()
    resp = s.get(
        info_dict['url'],
        headers=headers,
        cookies=cookies,
        allow_redirects = False
    )
    video_url = resp.headers['Location']

    img = info_dict['image']
    if addon.getSetting('language') == 0:
        show, title = info_dict['show_title_en'], info_dict['ep_title_en']
    else:
        show, title = info_dict['show_title_ru'], info_dict['ep_title_ru']

    listitem = xbmcgui.ListItem(title, iconImage=img, thumbnailImage=img)
    listitem.setInfo(
        type='Video',
        infoLabels = {
            'Episode': info_dict['episode'],
            'Season': info_dict['season'],
            'Title': title,
            'Plot': info_dict['plot'],
            'TVShowTitle': show,
        }
    )
    listitem.setProperty('Fanart_Image', img)

    xbmcplugin.setResolvedUrl(handle, True, listitem=listitem)

    player = Player(info_dict=info_dict)

    player.play(video_url+make_header_string(headers), listitem)

    while player.playing:
        xbmc.sleep(2000)
        if player.playing == 2:
            if player.isPlaying():
                player.pos = player.getTime()

if __name__ == '__main__':
    if addon.getSetting('username') == '' or addon.getSetting('password') == '':
        first_run()
    params = get_params()
    if params['mode'] == None:
        ShowSeries('/Series')
        xbmcplugin.setPluginCategory(handle, PLUGIN_NAME)
        xbmcplugin.endOfDirectory(handle)
    elif params['mode'][0] == 'OpenSeries':
        OpenSeries(params['url'][0], params['title'][0])
        xbmcplugin.setPluginCategory(handle, PLUGIN_NAME)
        xbmcplugin.endOfDirectory(handle)
    elif params['mode'][0] == 'Watch':
        info_dict = process_meta(params['url'][0])
        PlayURL(info_dict)
        #xbmcplugin.setPluginCategory(handle, PLUGIN_NAME)
        #xbmcplugin.endOfDirectory(handle)
