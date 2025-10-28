# -*- coding: utf-8 -*-
import abc

from bk_resource.exceptions import ValidateException
from bk_resource.utils.common_utils import get_md5
from bkstorages.backends.bkrepo import BKRepoStorage
from blueapps.utils.logger import logger
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _

from core.utils.data import unique_id


class FileUpload(metaclass=abc.ABCMeta):
    FILE_UPLOAD_SUFFIX_LIST = []
    FILE_UPLOAD_SIZE_LIMIT = 0
    FILE_UPLOAD_DEFAULT_DIR = "default"

    def validate_file(self, file):
        """验证文件 ."""
        # 验证资源后缀
        file_name = file.name
        file_suffix = file_name.rsplit(".")[-1]
        if file_suffix.lower() not in self.FILE_UPLOAD_SUFFIX_LIST:
            raise ValidateException(_("无效的资源后缀名"))
        # 验证文件大小
        file_size = file.size
        if file_size > self.FILE_UPLOAD_SIZE_LIMIT:
            raise ValidateException(_("资源大小超出限制，请选择小于{}M文件上传".format(self.FILE_UPLOAD_SIZE_LIMIT / 1024 / 1024)))

        return file_name, file_suffix, file_size

    def store_files(self, files):
        """存儲文件 ."""
        if files:
            storage = BKRepoStorage()
            file_keys = files.keys()
            for file_key in file_keys:
                file_list = files.getlist(file_key)
                for file in file_list:
                    # 验证附件
                    origin_name, file_suffix, file_size = self.validate_file(file)
                    # 计算附件的md5
                    content = file.read()
                    md5 = get_md5(content)
                    # 构造的文件名
                    new_name = f"{unique_id()}.{file_suffix}"
                    # 构造文件路径
                    file_path = f"{self.FILE_UPLOAD_DEFAULT_DIR.strip('/')}/{new_name}"
                    # 存储附件
                    try:
                        f = ContentFile(content)
                        storage_name = storage.save(file_path, f)
                        url = storage.url(storage_name)
                    except Exception as exc_info:  # pylint: disable=broad-except
                        logger.exception(exc_info)
                        raise Exception(_("资源上传失败"))

                    yield {
                        "md5": md5,
                        "origin_name": origin_name,
                        "storage_name": storage_name,
                        "size": file_size,
                        "url": url,
                    }
