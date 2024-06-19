import base64
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from aiogram import Bot
from aiogram.utils import formatting
from aiogram.types import BufferedInputFile
import requests

bot_token = 'xx:xx'
chat_id = 123456
push_key = 'password'
self_url = 'https://www.example.com'
secret_token = 'a random token'

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
app = FastAPI()

@app.api_route("/push", methods=['GET', 'POST'])
async def push(request: Request):
    if request.method == 'POST':
        data = await request.post()
    elif request.method == 'GET':
        data = request.query_params

    if 'key' not in data or data['key'] != push_key:
        raise HTTPException(status_code=403, detail="invalid send key")
    
    try:
        async with Bot(token=bot_token) as bot:
            if 'type' not in data or data['type'] == 'text':
                ret = await bot.send_message(chat_id, data['msg'])
            elif data['type'] == 'image':
                ret = await bot.send_photo(chat_id, BufferedInputFile(base64.b64decode(data['msg']), filename='image'))
            elif data['type'] == 'markdown':
                ret = await bot.send_message(chat_id, data['msg'], parse_mode='MarkdownV2')
            elif data['type'] == 'file':
                ret = await bot.send_document(chat_id, BufferedInputFile(base64.b64decode(data['msg']), filename=data.get('filename', 'file')))
            else:
                msg = "invalid msg type. type should be text(default), image, markdown or file."
                raise HTTPException(status_code=400, detail=msg)

    except Exception as e:
        msg = "unexpected error: " + str(e)
        logging.exception(e)
        raise HTTPException(status_code=500, detail=msg)

    return {'message_id': ret.message_id}


@app.get("/tg/webhook_init")
async def webhook_init(request: Request):
    if request.query_params.get('token') != secret_token:
        raise HTTPException(status_code=403, detail="invalid token")

    async with Bot(token=bot_token) as bot:
        return await bot.set_webhook(url=f"{self_url}/tg/callback", secret_token=secret_token)


@app.post("/tg/callback")
async def callback(request: Request):
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != secret_token:
        raise HTTPException(status_code=403, detail="invalid token")

    data = await request.json()
    logging.info(data)
    
    r = requests.post(f"{self_url}/tg/process", json=data, headers={
        "X-Fc-Invocation-Type": "Async",
        "Token": secret_token
    })

    logging.info(r.text)
    if r.status_code != 202:
        raise HTTPException(status_code=500, detail="async process failed")

    return {"detail": "scheduled"}


@app.post("/tg/process")
async def process(request: Request):
    if request.headers.get('Token') != secret_token:
        raise HTTPException(status_code=403, detail="invalid token")
    
    data = await request.json()
    logging.info(data)

    async with Bot(token=bot_token) as bot:
        try:
            if data['message']['from']['id'] != chat_id:
                raise Exception("invalid from chat id")

            logging.info("processing: " + data['message']['text'])

        
            await bot.send_message(chat_id, "recved: " + data['message']['text'])
        except Exception as e:
            logging.exception(e)
            await bot.send_message(chat_id, "Error processing message: \n> " + formatting.Text(json.dumps(data, ensure_ascii=False)).as_markdown() + "\nException: \n> " + formatting.Text(str(e)).as_markdown(), parse_mode='MarkdownV2')
            return "dropped"
    
    return "ok"
