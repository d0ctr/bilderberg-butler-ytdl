from dotenv_vault import load_dotenv
load_dotenv()

import os

if os.getenv('TELEGRAM_TOKEN') is None \
    or os.getenv('TELEGRAM_API_HASH') is None \
    or os.getenv('TELEGRAM_API_ID') is None:
    raise Exception('Telgram configuration is not set')

if os.getenv('PORT') is None:
    raise Exception('PORT is not set')


import youtube_dl
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio, DocumentAttributeFilename

from sanic import Sanic
from sanic.response import json


app = Sanic('bilderberg-butler-ytdl')

ytdl_opts = {
    'no_color': True,
    'format': 'bestvideo[ext=mp4]/bestvideo/bestaudio[ext=mp3]/best'
}

jobs = {}

async def async_download(ydl, *args):
    ydl.download(*args)

async def download_and_send(url, telegram_chat_id, info, ydl):
    ydl.download([url])
    filename = ydl.prepare_filename(info)
    file = open(filename, 'rb')
    if info['ext'] == 'mp4':
        attrs = DocumentAttributeVideo(int(info['duration']), w=0, h=0, supports_streaming=True)
    elif info['ext'] == 'mp3':
        attrs = DocumentAttributeAudio(int(info['duration']), voice=False, title=info['title'])
    else:
        attrs = DocumentAttributeFilename(f'{info["title"]}.{info["ext"]}')
    try:
        await app.ctx.tg.send_file(int(telegram_chat_id), file=file, attributes=[attrs])
    except Exception as e:
        await app.ctx.tg.send_message(int(telegram_chat_id), f'Не получилось отправить файл:\n<code>{str(e)}</code>', parse_mode='html')

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
async def start_bot(app, loop):
    app.ctx.tg = TelegramClient('bot', int(os.getenv('TELEGRAM_API_ID')), os.getenv('TELEGRAM_API_HASH'), loop=loop)
    await app.ctx.tg.start(bot_token=os.getenv('TELEGRAM_TOKEN'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT')))