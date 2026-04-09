import aiohttp
import os
import re
import shutil
import asyncio
from dataclasses import dataclass
from typing import List, Optional
import subprocess

from mautrix.types import (
    MessageEvent, EventType, MessageType, 
    MediaMessageEventContent, ImageInfo, VideoInfo
)
from mautrix.crypto.attachments import encrypt_attachment
from ...core import loader

@dataclass
class TTData:
    media: List[str]
    type: str  # "video" или "images"

class TikTokAPI:
    def __init__(self, host: Optional[str] = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/91.0.4472.124 Safari/537.36"
        }
        self.host = host or "https://www.tikwm.com/"
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self):
        await self.session.close()

    async def _download_file(self, url: str, path: str):
        async with self.session.get(url) as response:
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(await response.read())

    async def download(self, link: str, hd: bool = True) -> TTData:
        async with self.session.get(f"{self.host}api", params={"url": link, "hd": int(hd)}) as response:
            data = await response.json()
            if not data.get("data"):
                raise Exception(data.get("msg") or "No data found")

            result = data["data"]
            if "images" in result:
                os.makedirs("tt_temp", exist_ok=True)
                paths = []
                for i, url in enumerate(result["images"]):
                    path = f"tt_temp/img_{i}.jpg"
                    await self._download_file(url, path)
                    paths.append(path)
                return TTData(paths, "images")
            
            elif "play" in result:
                url = result.get("play") or result.get("hdplay")
                path = f"tt_temp_{result['id']}.mp4"
                await self._download_file(url, path)
                return TTData([path], "video")
            
            raise Exception("Unknown content type")

def convert_to_mp4(input_path: str) -> str:
    """Конвертирует bvc2 или неподдерживаемый TikTok формат в mp4, возвращает путь нового файла"""
    output_path = input_path.replace(".mp4", "_conv.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ], check=True)
    os.remove(input_path)
    return output_path

@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "TikTokDL",
        "_cls_doc": "Скачивает TikTok видео и фото-слайды (E2EE ready).",
        "no_url": "❌ TikTok URL не найден.",
        "downloading": "⏳ Скачивание и обработка медиа...",
        "error": "❌ Ошибка: {err}"
    }

    @loader.command()
    async def tt(self, mx, event: MessageEvent):
        """Скачивает TikTok видео или фото-слайды (E2EE Ready)"""
        text = getattr(event.content, "body", "") or ""
        matches = re.findall(r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+", text)
        url = matches[0] if matches else None

        if not url:
            return await mx.client.send_text(event.room_id, self.strings["no_url"])

        progress = await mx.client.send_text(event.room_id, self.strings["downloading"])
        
        api = TikTokAPI()
        try:
            result = await api.download(url)
            is_encrypted = await mx.state_store.is_encrypted(event.room_id)

            for file_path in result.media:
                if result.type == "video":
                    file_path = convert_to_mp4(file_path)

                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                filename = os.path.basename(file_path)
                if result.type == "video":
                    mime = "video/mp4"
                    msg_type = MessageType.VIDEO
                    info = VideoInfo(mimetype=mime, size=len(file_bytes))
                else:
                    mime = "image/jpeg"
                    msg_type = MessageType.IMAGE
                    info = ImageInfo(mimetype=mime, size=len(file_bytes))

                if is_encrypted:
                    enc_data, enc_info = encrypt_attachment(file_bytes)
                    mxc = await mx.client.upload_media(enc_data, mime_type="application/octet-stream", filename=filename)
                    enc_info.url = mxc
                    content = MediaMessageEventContent(
                        msgtype=msg_type,
                        body=filename,
                        info=info,
                        file=enc_info
                    )
                else:
                    mxc = await mx.client.upload_media(file_bytes, mime_type=mime, filename=filename)
                    content = MediaMessageEventContent(
                        msgtype=msg_type,
                        body=filename,
                        info=info,
                        url=mxc
                    )

                await mx.client.send_message_event(
                    room_id=event.room_id,
                    event_type=EventType.ROOM_MESSAGE,
                    content=content
                )

                if os.path.exists(file_path):
                    os.remove(file_path)

        except Exception as e:
            await mx.client.send_text(event.room_id, self.strings["error"].format(err=str(e)))
        
        finally:
            await api.close()
            try:
                await mx.client.redact(event.room_id, progress)
                if os.path.exists("tt_temp"):
                    shutil.rmtree("tt_temp")
            except:
                pass