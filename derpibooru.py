import aiofiles
import aiohttp
import asyncio
import json
import logging
import os
import time

from pathlib import Path
from pprint import pprint
from typing import List, Dict


logger = logging.getLogger(name='boorutagger')  # type: logging.Logger
logger.setLevel(logging.DEBUG)

if not os.path.exists('logs'):
    os.makedirs('logs')
fh = logging.FileHandler(Path('logs/log-{}.txt'.format(time.strftime('%Y%m%d-%H%M%S'))))
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

class FileWriter:
    def __init__(self, path: Path):
        self._path = path

    async def write_image(self, data: bytes, name: str, path=None):
        if not path:
            path = self._path
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except FileExistsError:
                pass
        async with aiofiles.open((path / name), 'wb') as f:
            await f.write(data)
            logger.info('Written {} to disk at path: {}/'.format(name, path))

class Image:

    _cache = {}

    def __init__(self, json, session: aiohttp.ClientSession):
        self._session = session
        self.data = json

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "<Image class; id {}>".format(self.imageId)

    @property
    def filename(self):
        return self.imageId + '.' + self.data['original_format']

    @property
    def imageId(self):
        return str(self.data['id'])

    @property
    def imageUrl(self, option='full'):
        if option and option != 'full':
            pass
        return 'https:' + self.data['image']

    async def image(self):
        if self._read_cache('image'):
            return self._read_cache('image')
        async with self._session.get(self.imageUrl) as response:
            logger.info("Got response for Image({}) image data".format(self.imageId))
            self._write_cache('image', await response.read())
            return self._read_cache('image')

    def _read_cache(self, key):
        return Image._cache.get(self.imageId, {}).get(key)

    def _write_cache(self, key, value):
        if self.imageId not in Image._cache:
            Image._cache[self.imageId] = {}
        Image._cache[self.imageId][key] = value


class Derpibooru:
    domain = 'https://derpibooru.org'
    batch_size = 15

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *err):
        await self._session.close()
        self._session = None

    async def get_images(self, amount=50) -> List[Image]:
        logger.info("Getting images")

        page_count = amount // Derpibooru.batch_size + (amount % Derpibooru.batch_size > 0)
        logger.info("page_count: {}".format(page_count))

        results = await asyncio.gather(
            *(self._get_page('images', page) for page in range(1, page_count + 1)),
            #return_exceptions=True
        )

        results = [Image(i, self._session) for r in results for i in r['images']][:amount]
        logger.info("Success: Got {} images".format(amount))
        return results

    async def get_image_from_id(self, id: int):
        url = Derpibooru.domain + '/' + str(id) + '.json'
        async with self._session.get(url) as response:
            j = await response.json()
            return Image(j, self._session)


    async def _get_page(self, service: str, page: int) -> dict:
        url = Derpibooru.domain + '/' + service + '.json'
        params = {
            'page': page,
            'order': 'a'
        }
        
        async with self._session.get(url, params=params) as response:
            j = await response.json()
            return j


async def main():
    async def image_apply(image: Image):
        fw = FileWriter(Path('downloaded_data'))
        await fw.write_image(await image.image(), image.filename)

    async with Derpibooru() as derpi:
        result = await derpi.get_images()
        logger.info("len(result): {}".format(len(result)))
        result = await asyncio.gather(*(image_apply(image) for image in result))

        # image = await derpi.get_image_from_id(1957355)
        # pprint(image)
        # await image_apply(image)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
