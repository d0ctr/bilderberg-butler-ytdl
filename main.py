from dotenv_vault import load_dotenv
load_dotenv()

import os

if os.getenv('TELEGRAM_TOKEN') is None \
    or os.getenv('TELEGRAM_API_HASH') is None \
    or os.getenv('TELEGRAM_API_ID') is None:
    raise Exception('Telgram configuration is not set')

if os.getenv('PORT') is None:
    raise Exception('PORT is not set')

import io
import asyncio

import youtube_dl
from threading import Thread
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo

from sanic import Sanic
from sanic.response import json


bot = TelegramClient('bot', int(os.getenv('TELEGRAM_API_ID')), os.getenv('TELEGRAM_API_HASH'))
bot.session.save_entities = False
app = Sanic('bilderberg-butler-ytdl')
ytdl_opts = {
    'no_color': True,
    'format': 'best[ext=mp4]'
}

jobs = {}

async def async_download(ydl, *args):
    ydl.download(*args)

async def download_and_send(url, telegram_chat_id, info, ydl):
    ydl.download([url])
    filename = ydl.prepare_filename(info)
    video_file = open(filename, 'rb')
    attrs = DocumentAttributeVideo(info['duration'], 0, 0, supports_streaming=True)
    await bot.send_file(int(telegram_chat_id), file=video_file, caption=info['title'], attributes=[attrs])
    os.remove(filename)

@app.route('/ytdl', methods=['POST'])
async def ytdl_handler(request):
    if request.json is None:
        return json({'body': {'status': 'error', 'message': 'request body is empty'}}, 200)

    if 'url' not in request.json:
        return json({'body': {'status': 'error', 'message': 'url is not set'}}, 200)
    url = request.json['url']
    
    if 'telegram_chat_id' not in request.json:
        return json({'body': {'status': 'error', 'message': 'telegram_chat_id is not set'}}, 200)
    telegram_chat_id = request.json['telegram_chat_id']

    # if telegram_chat_id in jobs:
        # return json({'body': {'status': 'error', 'message': 'job is already in progress'}}, 200)
    try:
        with youtube_dl.YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            app.add_task(download_and_send(url, telegram_chat_id, info, ydl))
            return json({'body': {'status': 'ok', 'info': info}}, 200)
    except Exception as e:
        return json({'body': {'status': 'error', 'message': str(e)}}, 200)

@app.route('/ytdl-stop', methods=['POST'])
async def ytdl_stop_handler(request):
    if request.json is None:
        return json({'body': {'status': 'error', 'message': 'request body is empty'}}, 200)

    if 'telegram_chat_id' not in request.json:
        return json({'body': {'status': 'error', 'message': 'telegram_chat_id is not set'}}, 200)
    telegram_chat_id = request.json['telegram_chat_id']

    if telegram_chat_id not in jobs:
        return json({'body': {'status': 'error', 'message': 'job is not in progress'}}, 200)
    try:
        await jobs[telegram_chat_id].cancel()
        del jobs[telegram_chat_id]

        return json({'body': {'status': 'ok'}}, 200)
    except Exception as e:
        return json({'body': {'status': 'error', 'message': str(e)}}, 200)

@app.after_server_start
async def start_bot(*_):
    await bot.start(bot_token=os.getenv('TELEGRAM_TOKEN'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT')))