# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from io import BytesIO
from urllib.parse import quote

import requests
from blueapps.utils.logger import logger
from django.http import FileResponse, StreamingHttpResponse

from core.constants import FILE_DOWNLOAD_CHUNK_SIZE
from core.exceptions import FileDownloadError


class Filedownloader:
    """
    文件下载器
    """

    def download_file(self, origin_name: str, url: str) -> FileResponse:
        try:
            file = requests.get(url)
            file.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.__class__.__name__}] Failed to download file, error message: {e}")
            raise FileDownloadError()

        # 创建BytesIO对象
        file_object = BytesIO()
        file_object.write(file.content)

        # 将文件指针重置到文件开始
        file_object.seek(0)

        # 创建Django的FileResponse，并设置Content-Disposition头，以便将文件作为附件提供给用户
        response = FileResponse(file_object, content_type=file.headers['Content-Type'])
        response['Content-Disposition'] = "attachment; filename*=utf-8''{}".format(quote(origin_name))
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response

    def stream_download_file(self, origin_name: str, url: str) -> StreamingHttpResponse:
        """
        流式下载文件
        """

        try:
            # 启用流式下载模式
            response = requests.get(url, stream=True)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.__class__.__name__}] Failed to download file, error message: {e}")
            raise FileDownloadError()

        # 创建流式响应对象
        stream_response = StreamingHttpResponse(
            self._file_chunk_generator(response),
            content_type=response.headers.get('Content-Type', 'application/octet-stream'),
        )

        # 设置下载头信息
        filename = quote(origin_name)  # 处理特殊字符
        stream_response['Content-Disposition'] = f"attachment; filename*=utf-8''{filename}"
        stream_response['Access-Control-Expose-Headers'] = 'Content-Disposition'

        # 如果服务器提供了内容长度，则添加该头信息
        if 'Content-Length' in response.headers:
            stream_response['Content-Length'] = response.headers['Content-Length']

        return stream_response

    def _file_chunk_generator(self, response):
        """
        文件内容分块生成器
        """
        try:
            for chunk in response.iter_content(chunk_size=FILE_DOWNLOAD_CHUNK_SIZE):
                if chunk:  # 过滤保持活跃连接的空块
                    yield chunk
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.__class__.__name__}] Stream interrupted, error: {e}")
            raise e
        finally:
            response.close()  # 确保释放网络连接
