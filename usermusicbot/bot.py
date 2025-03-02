import asyncio, os, re, sys, logging

from os import getenv
from dotenv import load_dotenv
from typing import Union, List, Pattern
from logging.handlers import RotatingFileHandler

from pyrogram import Client, filters, idle
from pytgcalls import PyTgCalls, filters as fl
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, VideoQuality
from pytgcalls.types import Call, MediaStream, GroupCallConfig
from pytgcalls.types import ChatUpdate, Update, StreamAudioEnded
from youtubesearchpython.__future__ import VideosSearch as yt_search


logging.basicConfig(
    format="[%(name)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
    handlers=[
        RotatingFileHandler("logs.txt", maxBytes=(1024 * 1024 * 5), backupCount=10),
        logging.StreamHandler(),
    ],
)

logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)

logs = logging.getLogger()


if os.path.exists("Config.env"):
    load_dotenv("Config.env")

API_ID = int(getenv("API_ID", 0))
API_HASH = getenv("API_HASH", None)
STRING_SESSION = getenv("STRING_SESSION", None)


app = Client(
    name="App",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)
call = PyTgCalls(app)
call_config = GroupCallConfig(auto_start=False)


queue_dict = {}
global_player = False
only_owner = filters.me
sudo_users = filters.user()


async def main():
    logs.info("🔄 Processing, Please Wait❗...")
    if "cache" not in os.listdir():
        os.mkdir("cache")
    if "downloads" not in os.listdir():
        os.mkdir("downloads")
    for file in os.listdir():
        if file.endswith(".session"):
            os.remove(file)
    for file in os.listdir():
        if file.endswith(".session-journal"):
            os.remove(file)
    if API_ID == 0:
        logs.info("❌ 'API_ID' - Not Found❗")
        sys.exit()
    if not API_HASH:
        logs.info("❌ 'API_HASH' - Not Found❗")
        sys.exit()
    if not STRING_SESSION:
        logs.info("❌ 'STRING_SESSION' - Not Found❗")
        sys.exit()
    try:
        await app.start()
        await call.start()
        try:
            await app.join_chat("Tele_Ki_Duniya")
        except Exception:
            pass
        logs.info("✅ Userbot started & now running❗")
    except Exception as e:
        logs.info(f"🚫 Failed to start Userbot❗\n⚠️Reason: {e}")
    if app.me.id not in sudo_users:
        sudo_users.add(app.me.id)
    await idle()


def cdx(commands: Union[str, List[str]]):
    return filters.command(commands, ["/", "!", "."])


async def eor(message, *args, **kwargs):
    try:
        msg = (
            message.edit_text
            if bool(message.from_user and message.from_user.is_self or message.outgoing)
            else (message.reply_to_message or message).reply_text
        )
    except:
        msg = (
            message.edit_text
            if bool(message.from_user and message.outgoing)
            else (message.reply_to_message or message).reply_text
        )
    
    return await msg(*args, **kwargs)




async def get_stream_file(query: str) -> dict:
    if query.startswith("https://"):
        search_base_url = r"(?:https?:)?(?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube(?:\-nocookie)?\.(?:[A-Za-z]{2,4}|[A-Za-z]{2,3}\.[A-Za-z]{2})\/)?(?:shorts\/|live\/)?(?:watch|embed\/|vi?\/)*(?:\?[\w=&]*vi?=)?([^#&\?\/]{11}).*$"
        search_base_result = re.findall(search_base_url, query)
        id = search_base_result[0] if search_base_result[0] else None
    else:
        id = None
    search_url = f"https://www.youtube.com/watch?v={id}" if id else None
    search_query = search_url if search_url else query
    search_results = yt_search(search_query, limit=1)
    try:
        youtube_result = [result for result in (await search_results.next())["result"]][
            0
        ]
    except Exception:
        return False, False
    yt_link = youtube_result["link"] if youtube_result["link"] else None
    stream_link = search_url if search_url else yt_link
    
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-g",
        "-f",
        "bestvideo+bestaudio/best",
        stream_link,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    links = stdout.decode().split("\n")
    if len(links) < 2:
        return False, False
    return links[1] if links[1] else links[0], links[0]


async def get_stream_data(stream_type, audio_file, video_file):
    if stream_type == "audio":
        final_stream_data = MediaStream(
            media_path=audio_file,
            video_flags=MediaStream.Flags.IGNORE,
            audio_parameters=AudioQuality.STUDIO,
        )

    elif stream_type == "video":
        if audio_file:
            final_stream_data = MediaStream(
                media_path=video_file,
                audio_path=audio_file,
                audio_parameters=AudioQuality.STUDIO,
                video_parameters=VideoQuality.HD_720p,
            )
            
        else:
            final_stream_data = MediaStream(
                media_path=video_file,
                audio_parameters=AudioQuality.STUDIO,
                video_parameters=VideoQuality.HD_720p,
            )
        
    return final_stream_data


async def get_call_status(chat_id):
    calls = await call.calls
    chat_call = calls.get(chat_id)
    if chat_call:
        status = chat_call.status
        if status == Call.Status.IDLE:
            call_status = "idle"
        elif status == Call.Status.PLAYING:
            call_status = "playing"

        elif status == Call.Status.PAUSED:
            call_status = "paused"
    else:
        call_status = "nothing"

    return call_status



async def add_to_queue(
    chat_id, stream_type, stream_data
):
    put = {
        "chat_id": chat_id,
        "stream_type": stream_type,
        "stream_data": stream_data,
    }
    chat_id_in_queue = queue_dict.get(chat_id)
    if chat_id_in_queue:
        queue_dict[chat_id].append(put)
    else:
        queue_dict[chat_id] = []
        queue_dict[chat_id].append(put)
        
    return len(queue_dict[chat_id]) - 1



async def clear_queue(chat_id):
    check = queue_dict.get(chat_id)
    if check:
        queue_dict.pop(chat_id)


async def change_stream(chat_id):
    queued = queue_dict.get(chat_id)
    if queued:
        queued.pop(0)
    if not queued:
        await app.send_message(
            chat_id, "**❎ Queue is Empty, So Left\nFrom VC❗...**",
        )
        return await close_stream(chat_id)

    stream_type = queued[0].get("stream_type")
    stream_data = queued[0].get("stream_data")
    
    await call.play(chat_id, stream_data, config=call_config)
    return await app.send_message(chat_id, "**✅ Started Streaming.**")


async def close_stream(chat_id):
    try:
        await call.leave_call(chat_id)
    except Exception:
        pass
    await clear_queue(chat_id)


def global_play_wrapper(command):
    async def wrapper(client, message):
        if not global_player:
            if not message.from_user:
                return 
            if message.from_user.id not in sudo_users:
                return
            
        return await command(client, message)

    return wrapper



@app.on_message(cdx(["play", "vplay"]) & ~filters.private)
@global_play_wrapper
async def start_audio_or_video_stream(client, message):
    chat_id = message.chat.id
    replied = message.reply_to_message
    audio_file = replied.audio or replied.voice if replied else None
    video_file = replied.video or replied.document if replied else None

    try:
        aux = await eor(message, "**🔄 Proccessing ✨...**")
        if (audio_file or video_file):
            stream_type = "audio" if audio_file else "video"
            stream_file = await replied.download()
            audio = stream_file if audio_file else None
            video = stream_file if video_file else None

        else:
            if len(message.command) < 2:
                return await aux.edit(
                    "**⚠️ Give me a query to stream\naudio or video on vc.**"
                )
            query = message.text.split(None, 1)[1]
            stream_type = "audio" if not message.command[
                0
            ].startswith("v") else "video"
            audio, video = await get_stream_file(query)
            if not (audio and video):
                return await aux.edit(
                    "**⚠️ Something went wrong, So\ntry another query❗**"
                )
    
        stream_data = await get_stream_data(stream_type, audio, video)
        call_status = await get_call_status(chat_id)

        if call_status == "playing" or call_status == "paused":
            position = await add_to_queue(chat_id, stream_type, stream_data)
            await aux.edit(f"**✅ Added To Queue At: #{position}**")
        else:
            try:
                await call.play(chat_id, stream_data, config=call_config)
                await add_to_queue(chat_id, stream_type, stream_data)
                await aux.edit("**✅ Started Streaming On VC.**")
            except NoActiveGroupCall:
                return await aux.edit("**⚠️ No active vc found❗**")
    except Exception as e:
        print(e)
        try:
            await aux.delete()
        except Exception:
            pass
        return
        


@app.on_message(cdx(["pause", "vpause"]) & sudo_users & ~filters.private)
async def pause_running_stream_on_vc(client, message):
    chat_id = message.chat.id
    try:
        call_status = await get_call_status(chat_id)
        if call_status == "paused":
            return await eor(message, "**🔈 Already Paused❗**")
        elif call_status == "playing":
            await call.pause_stream(chat_id)
            return await eor(message, "**🔈 Stream Paused❗**")
        else:
            return await eor(message, "**❎ 𝖭𝗈𝗍𝗁𝗂𝗇𝗀 𝖲𝗍𝗋𝖾𝖺𝗆𝗂𝗇𝗀❗**")
    except Exception:
        pass


@app.on_message(cdx(["resume", "vresume"]) & sudo_users & ~filters.private)
async def resume_paused_stream_on_vc(client, message):
    chat_id = message.chat.id
    try:
        call_status = await get_call_status(chat_id)
        if call_status == "playing":
            return await eor(message, "**🔊 Already Streaming❗**")
        elif call_status == "paused":
            await call.resume_stream(chat_id)
            return await eor(message, "**🔊 Stream Resumed❗**")
        else:
            return await eor(message, "**❎ Nothing Streaming❗**")
    except Exception:
        pass


@app.on_message(cdx(["skip", "vskip"]) & sudo_users & ~filters.private)
async def skip_current_stream(client, message):
    aux = await eor(message, "**🔄 Processing ✨...**")
    chat_id = message.chat.id
    try:
        call_status = await get_call_status(chat_id)
        if call_status == "playing" or call_status == "paused":
            try:
                await change_stream(chat_id)
            except Exception:
                pass
        else:
            return await aux.edit("**❎ Nothing Streaming❗...**")
    except Exception:
        pass
    try:
        await aux.delete()
    except Exception:
        pass


@app.on_message(cdx(["end", "vend"]) & sudo_users & ~filters.private)
async def stop_stream_and_leave_vc(client, message):
    chat_id = message.chat.id
    try:
        call_status = await get_call_status(chat_id)
        if call_status == "idle":
            return await eor(message, "**✅ Successfully Left From VC❗**")
        elif call_status == "playing" or call_status == "paused":
            await close_stream(chat_id)
            return await eor(message, "**❎ Stopped Stream & Left\nFrom VC❗...**")
        else:
            return await eor(message, "**❎ Nothing Streaming❗**")
    except Exception:
        pass


@app.on_message(cdx("changemode") & only_owner)
async def change_stream_mode(client, message):
    global global_player
    if not global_player:
        global_player = True
        return await message.edit("**✅ Switched To Global Mode.**")
    elif global_player:
        return await message.edit("**✅ Switched To Sudo Mode.**")
    else:
        return



@app.on_message(cdx("addsudo") & only_owner)
async def add_sudo_user(client, message):
    replied = message.reply_to_message
    if not replied:
        return await message.edit(
            "**✅ Please reply to an user to add in sudo users list.**"
        )
    if not replied.from_user:
        return await message.edit(
            "**✅ Please reply to an valid user to add in sudo users list.**"
        )
    if replied.from_user.id not in sudo_users:
        sudo_users.add(replied.from_user.id)
        return await message.edit("**✅ Added To Sudo Users.**")
    else:
        return await message.edit("**✅ Already in Sudo List.**")
    


@app.on_message(cdx("delsudo") & only_owner)
async def del_sudo_user(client, message):
    replied = message.reply_to_message
    if not replied:
        return await message.edit(
            "**✅ Please reply to an user to remove from sudo users list.**"
        )
    if not replied.from_user:
        return await message.edit(
            "**✅ Please reply to an valid user to remove from sudo users list.**"
        )
    if replied.from_user.id in sudo_users:
        sudo_users.remove(replied.from_user.id)
        return await message.edit("**✅ Removed from Sudo Users.**")
    else:
        return await message.edit("**✅ User not in Sudo List.**")
        





@call.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
@call.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
@call.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
async def stream_services_handler(_, update: Update):
    return await close_stream(update.chat_id)
    
    
@call.on_update(fl.stream_end)
async def stream_end_handler(_, update: Update):
    chat_id = update.chat_id
    return await change_stream(chat_id)



if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    logs.info("❎ Goodbye, Userbot has been stopped‼️")
