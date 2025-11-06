<!--
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
-->
<template>
  <div
    :active="!disabled"
    class="editor-wrap">
    <bk-upload
      v-if="supportImage"
      id="editor-upload-image"
      ref="imageRef"
      accept="image/png,image/jpeg,image/jpg"
      :handle-res-code="handleRes"
      :headers="headers"
      method="post"
      :multiple="false"
      name="file"
      style="display: none"
      tip="只允许上传JPG、PNG、JPEG的文件"
      :url="`${attachmentUrl}`"
      with-credentials
      @error="onImageLoadError"
      @success="onImageLoadSuccess" />
    <quill-editor
      ref="editorRef"
      v-model:content="content"
      content-type="html"
      disabled
      :options="options"
      :placeholder="t(placeholder)"
      :style="{ background: backgroundColor }"
      theme="snow"
      @blur="onContentBlur"
      @ready="onEditorReady"
      @update:content="onContentChange" />
    <div class="editor-tip-len">
      <span :class="{ 'can-edit': TiLength < maxLen }"> {{ TiLength }} </span>/{{ maxLen }}
    </div>
    <!-- 编辑器中的图片预览 -->
    <editor-image-preview
      v-if="editorImages.length > 0"
      :images="editorImages" />
  </div>
</template>

<script setup lang="ts">
  import Cookie from 'js-cookie';
  import { nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import UploadManageService from '@service/upload-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import { QuillEditor } from '@vueup/vue-quill';

  import '@vueup/vue-quill/dist/vue-quill.snow.css';
  import '@vueup/vue-quill/dist/vue-quill.bubble.css';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface Emits {
    (e: 'update:content', value: string): void;
    (e: 'blur', value: string): void;
  }
  interface Props {
    disabled?: boolean;
    default?: string;
    maxLen?: number;
    placeholder?: string;
    supportImage?: boolean;
    // typeAssess?: boolean;
  }
  interface ResponseData {
    result: boolean;
    code: number;
    data: Array<{
      id: number;
      md5: string;
      origin_name: string;
      size: number;
      storage_name: string;
      url: string;
      uuid: string;
    }>;
  }
  const props = withDefaults(defineProps<Props>(), {
    maxLen: 10000,
    default: '',
    active: false,
    placeholder: '',
    disabled: false,
    supportImage: true,
  });

  const emits = defineEmits<Emits>();

  const { messageSuccess, messageError } = useMessage();

  const content = ref();
  const editorRef = ref();
  const imageRef = ref();
  const { t } = useI18n();
  const TiLength = ref(0);
  const editorImages = ref<Array<{url: string}>>([]);
  const CRRF_TOKEN_KEY = 'bk-wesec_csrftoken';
  const CSRFToken = Cookie.get(CRRF_TOKEN_KEY);
  const headers = new Headers({ 'X-CSRFToken': CSRFToken });
  const attachmentUrl = ref(`${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/api/v1/blob_storage/upload/`);

  // 工具栏
  const container = [
    [{ header: 1 }, { header: 2 }, 'bold', 'italic', 'strike', 'underline', { color: [] },  { align: 'center' },  { align: 'right' }],
    [
      { list: 'ordered' }, // 有序
      { list: 'bullet' }, // 无序列表的图标
    ],
    ['link', { background: [] }, 'code-block', 'fullscreen'],
  ];
  if (props.supportImage) {
    container[2].splice(0, 0, 'image');
  }
  const isFullscreen = ref(false);
  const options = reactive({
    modules: {
      toolbar: {
        container,
        handlers: {
          image() {
            const html = document.querySelector('.editor-wrap #editor-upload-image .bk-upload-trigger__draggable-upload-link') as HTMLElement;
            if (html) {
              html.click();
            }
          },
          fullscreen() {
            toggleFullscreen();
          },
        },
      },
      history: {
        delay: 1000,
        maxStack: 50,
        userOnly: true,
      },
    },
  });

  // 全屏切换功能
  const toggleFullscreen = () => {
    const editorWrap = document.querySelector('.editor-wrap') as HTMLElement;
    if (!editorWrap) return;

    if (!isFullscreen.value) {
      // 进入全屏
      editorWrap.classList.add('fullscreen-mode');
      document.body.style.overflow = 'hidden';
      isFullscreen.value = true;
    } else {
      // 退出全屏
      editorWrap.classList.remove('fullscreen-mode');
      document.body.style.overflow = '';
      isFullscreen.value = false;
    }
  };

  // 监听ESC键退出全屏
  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isFullscreen.value) {
      toggleFullscreen();
    }
  };

  const backgroundColor = ref('#fff');
  // 上传图片成功后的数据
  const successData = ref<ResponseData['data']>();

  const { run: fetchUploadImage } = useRequest(
    UploadManageService.UploadNewImage,
    {
      defaultValue: null,
    },
  );

  // 提取编辑器内容中的图片
  const extractImagesFromContent = (htmlContent: string) => {
    if (!htmlContent) {
      editorImages.value = [];
      return;
    }
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    const imgElements = doc.querySelectorAll('img');

    const images = Array.from(imgElements).map(img => ({
      url: img.src,
    }));

    editorImages.value = images;
  };

  const onContentChange = (val: string) => {
    editorRef.value?.getQuill().deleteText(props.maxLen, 4);
    if (!content.value || content.value === '') {
      TiLength.value = 0;
    } else {
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    }

    // 提取图片并更新预览
    extractImagesFromContent(val);

    emits('update:content', TiLength.value ? val : '');
  };

  const onContentBlur = (val: string) => {
    emits('blur', val);
  };

  const onEditorReady = () => {
    nextTick(() => {
      if (props.default) {
        content.value = props.default;
        // 提取默认内容中的图片
        extractImagesFromContent(props.default);
      }
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    });
  };
  const handleRes = (response: any) => {
    if (response.result) {
      successData.value = response.data;
      return true;
    }
    return false;
  };
  const onImageLoadSuccess = () => {
    insertImage();
  };
  const insertImage = () => {
    const quill = editorRef.value?.getQuill();
    const length = quill.getSelection().index;

    // 插入图片
    if (successData.value && successData.value.length) {
      quill.insertEmbed(length, 'image', successData.value[0].url);
    }

    // 设置插入图片的高度为 100%
    const imageElement = quill.root.querySelector(`.ql-editor img[src="${successData.value?.[0]?.url || ''}"]`);
    if (imageElement) {
      imageElement.setAttribute('width', '30%');
      imageElement.setAttribute('height', '30%');
    }

    // 调整光标到最后
    quill.setSelection(length + 1);
    messageSuccess('上传图片成功');
  };
  const onImageLoadError = () => {
    messageError('上传图片失败');
  };

  watch(
    () => props.disabled,
    () => {
      editorRef.value?.getQuill().enable(!props.disabled);
    },
  );

  watch(
    () => props.default,
    (val) => {
      content.value = val;
      // 当默认内容变化时，也要提取图片
      extractImagesFromContent(val);
    },
  );
  const dataURLtoBlob = (dataURL: any) => {
    const [meta, content] = dataURL.split(',');
    const byteString = atob(content);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    const mimeString = meta.match(/:(.*?);/)[1]; // 提取 MIME 类型
    return new Blob([ab], { type: mimeString });
  };

  // Blob对象 -> File 兼容接口
  const blobToFile = (blob: any, fileName: string) => new File([blob], fileName, { type: blob.type });

  // 定义上传图片的函数 base64Image -> Blob对象
  const uploadImage = async (base64Image: any) => {
    try {
      const formData = new FormData();
      const blob = dataURLtoBlob(base64Image);

      formData.append('file', blobToFile(blob, `${new Date().getTime()}.png`));
      return fetchUploadImage(formData).then((response: any) => {
        if (response?.data && response?.data[0].url) {
          return response?.data[0].url; // 假设服务器响应包含图片URL
        }
      });
    } catch (error) {
      console.error('Image upload failed:', error);
      return '';
    }
  };


  onMounted(() => {
    document.addEventListener('keydown', handleKeydown);
    const quill = editorRef.value?.getQuill();
    editorRef.value?.setHTML(props.default);
    if (quill) {
      quill.root.addEventListener(
        'paste',
        async (evt: any) => {
          quill.enable(!props?.disabled); // source设置用户通过鼠标或键盘等输入设备进行编辑的能力。当"api"或 时，不会影响 API 调用的功能"silent"。
          const clipboardData = evt.clipboardData || evt.originalEvent.clipboardData;
          if (clipboardData) {
            const html = clipboardData.getData('text/html');
            if (html) {
              evt.preventDefault();
              const parser = new DOMParser();
              const doc = parser.parseFromString(html, 'text/html');
              const imgTags = doc.querySelectorAll('img');
              const promises: Promise<void>[] = [];

              // base64图片拦截处理
              if (imgTags.length > 0) {
                imgTags.forEach((imgTag) => {
                  imgTag.setAttribute('width', '100%');
                  imgTag.setAttribute('height', '100%');
                  const base64Image = imgTag.src;
                  // base64
                  if (base64Image.startsWith('data:image/')) {
                    promises.push(uploadImage(base64Image).then((url) => {
                      // eslint-disable-next-line no-param-reassign
                      imgTag.src = url; // 替换为上传后的 URL
                    }));
                  }
                });
                await Promise.all(promises);
              }
              quill.focus();
              if (quill.getSelection()) {
                quill.clipboard.dangerouslyPasteHTML(quill.getSelection().index, doc.body.innerHTML);
              }
            }

            // 单个文件检测处理
            if (clipboardData && clipboardData.files && clipboardData.files.length) {
              evt.preventDefault();
              const { files } = clipboardData;
              fetchUploadImage(files).then((data) => {
                if (!data) return;
                successData.value = data.data;
                insertImage();
              });
            }
          }
        },
        false,
      );
    }
  });

  // 组件卸载时移除事件监听
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown);
  });
</script>

<style lang="postcss">
.ql-toolbar {
  display: flex;
  padding: 0 !important;
  flex-wrap: wrap;
  align-items: center;
  border: 1px solid #ccc;
}

/* 禁用时候的样式 */
.ql-disabled {
  background-color: #fafbfd !important;
}

.editor-wrap[active='false'] .ql-toolbar {
  background-color: #fafbfd !important;
}

/* toolbar 激活样式 */
.editor-wrap[active='true'] .ql-toolbar {
  background-color: #fff !important;
}

.editor-wrap {
  position: relative;
  box-sizing: border-box;

  .editor-tip-len {
    position: absolute;
    right: 5px;
    bottom: 5px;
    font-size: 12px;
  }

  .can-edit {
    color: green;
  }
}

.ql-container.ql-snow {
  min-height: 120px;
  padding-bottom: 10px;
}

.ql-editor {
  color: black;
}

/* 全屏模式样式 */
.editor-wrap.fullscreen-mode {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 9999;
  width: 100vw !important;
  height: 100vh !important;
  padding: 20px;
  margin: 0;
  background: #fff;

  .ql-editor {
    color: black;
    border: 1px solid #ccc;
  }

  .ql-toolbar {
    padding: 10px 0 !important;
    background: #fff !important;
    border-bottom: 1px solid #ccc;
  }

  .ql-container.ql-snow {
    height: calc(100vh - 300px) !important;
    min-height: auto;
    font-size: 16px;
    line-height: 1.6;
    border: none;
  }

  .editor-tip-len {
    position: fixed;
    right: 30px;
    bottom: 30px;
    padding: 5px 10px;
    font-size: 14px;
    color: #fff;
    background: rgb(0 0 0 / 70%);
    border-radius: 4px;
  }
}

/* 全屏图标样式 */
.ql-toolbar .ql-fullscreen {
  position: relative;
}

.ql-toolbar .ql-fullscreen::before {
  display: inline-block;
  width: 16px;
  height: 16px;
  margin-top: 1px;
  margin-left: -10px;
  font-size: 16px;
  line-height: 1;
  vertical-align: top;
  background-image: url('/static/images/field-type/full_screen.svg');
  background-position: center;
  background-repeat: no-repeat;
  background-size: contain;
  content: '';
}

.editor-wrap.fullscreen-mode .ql-toolbar .ql-fullscreen::before {
  display: inline-block;
  width: 16px;
  height: 16px;
  margin-top: 1px;
  margin-left: -10px;
  font-size: 16px;
  line-height: 1;
  vertical-align: top;
  background-image: url('/static/images/field-type/zoom_out.svg');
  background-position: center;
  background-repeat: no-repeat;
  background-size: contain;
  content: '';
}
</style>
