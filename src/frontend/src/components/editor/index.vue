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
    ref="editorWrapRef"
    :active="!disabled"
    class="editor-wrap editor-wrap--report"
    :class="{ 'expanded-mode': isExpanded && fullscreenScope === 'parent' }">
    <input
      v-if="supportImage"
      ref="imageInputRef"
      accept="image/png,image/jpeg,image/jpg"
      style="display: none"
      type="file"
      @change="onImageFileChange">
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
      v-if="showImagePreview && editorImages.length > 0"
      :images="editorImages"
      :title="t('编辑器中的图片预览')" />
    <insert-table-dialog
      ref="insertTableDialogRef"
      @confirm="handleInsertTableConfirm" />
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch, inject, type Ref } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import UploadManageService from '@service/upload-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import InsertTableDialog from '@views/risk-manage/detail/components/event-report/insert-table-dialog.vue';
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import ReportTableBlot, {
    hasTableContent,
    insertReportTable,
    registerReportTableMatcher,
  } from '@views/risk-manage/detail/components/event-report/report-table-blot';
  import { QuillEditor } from '@vueup/vue-quill';

  import '@vueup/vue-quill/dist/vue-quill.snow.css';
  import '@vueup/vue-quill/dist/vue-quill.bubble.css';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface Emits {
    (e: 'update:content', value: string): void;
    (e: 'blur', value: string): void;
    (e: 'expand-change', value: boolean): void;
  }
  interface Props {
    disabled?: boolean;
    default?: string;
    maxLen?: number;
    placeholder?: string;
    supportImage?: boolean;
    supportFullscreen?: boolean;
    showImagePreview?: boolean;
    /** viewport/main: 浮层全屏; parent: 原地增高编辑器 */
    fullscreenScope?: 'viewport' | 'main' | 'parent';
    /** parent 模式下放大后的编辑区高度 */
    expandHeight?: number;
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
    supportFullscreen: true,
    showImagePreview: true,
    fullscreenScope: 'main',
    expandHeight: 360,
  });

  const emits = defineEmits<Emits>();

  const { messageSuccess, messageError } = useMessage();

  const content = ref();
  const editorRef = ref();
  const editorWrapRef = ref<HTMLElement>();
  const imageInputRef = ref<HTMLInputElement>();
  const insertTableDialogRef = ref<InstanceType<typeof InsertTableDialog>>();
  const { t } = useI18n();
  const TiLength = ref(0);
  const editorImages = ref<Array<{url: string}>>([]);

  const openInsertTableDialog = () => {
    insertTableDialogRef.value?.show();
  };

  // 与「编辑事件调查报告」一致的工具栏，额外保留全屏
  const mediaTools: Array<string | Record<string, unknown>> = ['link'];
  if (props.supportImage) {
    mediaTools.push('image');
  }
  mediaTools.push('video', 'table');
  if (props.supportFullscreen) {
    mediaTools.push('fullscreen');
  }

  const container = [
    [{ header: [1, 2, 3, 4, 5, 6, false] }],
    [{ font: [] }],
    [{ size: [] }],
    ['bold', 'italic', 'underline', 'strike'],
    [{ color: [] }, { background: [] }],
    [{ script: 'sub' }, { script: 'super' }],
    [{ header: 1 }, { header: 2 }, 'blockquote', 'code-block'],
    [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
    [{ direction: 'rtl' }, { align: [] }],
    mediaTools,
    ['clean'],
  ];
  const isFullscreen = ref(false);
  const isExpanded = computed(() => isFullscreen.value);

  const PARENT_COLLAPSED_HEIGHT = 180;

  const dockBoostState = inject<{
    isEditorBoosted: Ref<boolean>;
    panelHeight: Ref<number>;
  } | null>('dockBoostState', null);

  const getReservedBottomHeight = (editorWrap: HTMLElement) => {
    const editorFormItem = editorWrap.closest('.bk-form-item');
    const awaitDealForm = editorWrap.closest('.risk-await-deal-wrap');
    let reserved = 24;
    if (editorFormItem && awaitDealForm) {
      let sibling = editorFormItem.nextElementSibling;
      while (sibling) {
        reserved += (sibling as HTMLElement).getBoundingClientRect().height + 8;
        sibling = sibling.nextElementSibling;
      }
    }
    return reserved;
  };

  const getParentExpandHeight = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) {
      return props.expandHeight;
    }
    const dockBody = editorWrap.closest('.risk-handle-dock__body') as HTMLElement | null;
    if (dockBody) {
      const bodyRect = dockBody.getBoundingClientRect();
      const editorRect = editorWrap.getBoundingClientRect();
      const reservedBottom = getReservedBottomHeight(editorWrap);
      const availableHeight = bodyRect.bottom - editorRect.top - reservedBottom;
      return Math.max(280, availableHeight);
    }
    return props.expandHeight;
  };

  const applyParentExpandHeight = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) {
      return;
    }
    const height = getParentExpandHeight();
    editorWrap.style.setProperty('--editor-expanded-height', `${height}px`);
    editorWrap.style.setProperty('--editor-collapsed-height', `${PARENT_COLLAPSED_HEIGHT}px`);
  };

  const scheduleApplyParentExpandHeight = () => {
    applyParentExpandHeight();
    requestAnimationFrame(() => {
      applyParentExpandHeight();
      requestAnimationFrame(applyParentExpandHeight);
    });
    setTimeout(applyParentExpandHeight, 220);
  };

  const clearParentExpandHeight = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) {
      return;
    }
    editorWrap.style.removeProperty('--editor-expanded-height');
    editorWrap.style.removeProperty('--editor-collapsed-height');
  };

  const toggleParentExpand = async () => {
    if (!isFullscreen.value) {
      emits('expand-change', true);
      await nextTick();
      scheduleApplyParentExpandHeight();
      isFullscreen.value = true;
    } else {
      isFullscreen.value = false;
      clearParentExpandHeight();
      emits('expand-change', false);
    }
  };

  if (dockBoostState) {
    watch(
      () => [dockBoostState.isEditorBoosted.value, dockBoostState.panelHeight.value],
      () => {
        if (isFullscreen.value) {
          scheduleApplyParentExpandHeight();
        }
      },
    );
  }
  interface FullscreenBounds {
    top: number;
    left: number;
    width: number;
    height: number;
  }

  const getFullscreenContainer = (): HTMLElement | null => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) {
      return null;
    }
    switch (props.fullscreenScope) {
    case 'main':
      return document.querySelector('.audit-navigation-main') as HTMLElement;
    case 'viewport':
    default:
      return null;
    }
  };

  const getFullscreenBounds = (): FullscreenBounds => {
    if (props.fullscreenScope === 'viewport') {
      return {
        top: 0,
        left: 0,
        width: window.innerWidth,
        height: window.innerHeight,
      };
    }
    const container = getFullscreenContainer();
    if (!container) {
      return {
        top: 0,
        left: 0,
        width: window.innerWidth,
        height: window.innerHeight,
      };
    }
    const rect = container.getBoundingClientRect();
    return {
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    };
  };

  const applyFullscreenBounds = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap || !isFullscreen.value) {
      return;
    }
    const bounds = getFullscreenBounds();
    editorWrap.style.top = `${bounds.top}px`;
    editorWrap.style.left = `${bounds.left}px`;
    editorWrap.style.width = `${bounds.width}px`;
    editorWrap.style.height = `${bounds.height}px`;
  };

  const clearFullscreenBounds = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) {
      return;
    }
    editorWrap.style.top = '';
    editorWrap.style.left = '';
    editorWrap.style.width = '';
    editorWrap.style.height = '';
  };

  const exitFullscreen = () => {
    const editorWrap = editorWrapRef.value;
    if (!editorWrap || !isFullscreen.value) {
      return;
    }
    if (props.fullscreenScope === 'parent') {
      clearParentExpandHeight();
      isFullscreen.value = false;
      emits('expand-change', false);
      return;
    }
    editorWrap.classList.remove(
      'fullscreen-mode',
      'fullscreen-mode--main',
      'fullscreen-mode--viewport',
    );
    clearFullscreenBounds();
    if (props.fullscreenScope === 'viewport') {
      document.body.style.overflow = '';
    }
    isFullscreen.value = false;
    window.removeEventListener('resize', applyFullscreenBounds);
    window.removeEventListener('scroll', applyFullscreenBounds, true);
  };

  // 全屏/放大切换
  const toggleFullscreen = () => {
    if (props.fullscreenScope === 'parent') {
      toggleParentExpand();
      return;
    }
    const editorWrap = editorWrapRef.value;
    if (!editorWrap) return;

    if (!isFullscreen.value) {
      editorWrap.classList.add('fullscreen-mode');
      if (props.fullscreenScope === 'viewport') {
        editorWrap.classList.add('fullscreen-mode--viewport');
        document.body.style.overflow = 'hidden';
      } else {
        editorWrap.classList.add('fullscreen-mode--main');
      }
      applyFullscreenBounds();
      isFullscreen.value = true;
      window.addEventListener('resize', applyFullscreenBounds);
      window.addEventListener('scroll', applyFullscreenBounds, true);
    } else {
      exitFullscreen();
    }
  };

  const options = reactive({
    modules: {
      toolbar: {
        container,
        handlers: {
          image() {
            if (!props.supportImage || props.disabled) return;
            imageInputRef.value?.click();
          },
          table: openInsertTableDialog,
          ...(props.supportFullscreen
            ? {
              fullscreen() {
                toggleFullscreen();
              },
            }
            : {}),
        },
      },
      history: {
        delay: 1000,
        maxStack: 50,
        userOnly: true,
      },
    },
  });

  const getQuill = () => editorRef.value?.getQuill?.();

  const setupTableToolbarButton = () => {
    const quill = getQuill();
    if (!quill) return;
    const toolbar = quill.getModule('toolbar') as { container?: HTMLElement } | undefined;
    const tableButton = toolbar?.container?.querySelector('.ql-table') as HTMLElement | null;
    if (tableButton) {
      tableButton.innerHTML = t('插入表格');
      tableButton.setAttribute('title', t('插入表格'));
      tableButton.classList.add('editor-table-btn');
    }
  };

  const handleInsertTableConfirm = ({ rows, cols }: { rows: number; cols: number }) => {
    const quill = getQuill();
    if (!quill) return;
    insertReportTable(quill, rows, cols);
    TiLength.value = quill.getLength() - 1;
  };

  // 监听ESC键退出全屏
  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isFullscreen.value) {
      exitFullscreen();
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
    if (!props.showImagePreview) return;
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
    if (!content.value || content.value === '') {
      TiLength.value = 0;
    } else {
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    }

    // 检查是否超过最大长度限制
    if (TiLength.value > props.maxLen) {
      // 删除超出部分的字符
      editorRef.value?.getQuill().deleteText(props.maxLen, 1);
      // 重新计算长度
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
    const quill = getQuill();
    if (quill) {
      registerReportTableMatcher(quill);
    }
    nextTick(() => {
      setupTableToolbarButton();
      if (props.default) {
        content.value = props.default;
        // 提取默认内容中的图片
        extractImagesFromContent(props.default);
      }
      normalizeEditorImages();
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    });
  };
  const onImageLoadSuccess = () => {
    insertImage();
  };

  const normalizeEditorImages = (root?: ParentNode | null, target?: HTMLImageElement) => {
    const container = root || editorRef.value?.getQuill()?.root;
    const imageNodes = target
      ? [target]
      : Array.from(container?.querySelectorAll('img') ?? []) as HTMLImageElement[];
    for (let index = 0; index < imageNodes.length; index += 1) {
      const imageElement = imageNodes[index];
      imageElement.removeAttribute('width');
      imageElement.removeAttribute('height');
      imageElement.style.maxWidth = '100%';
      imageElement.style.height = 'auto';
      imageElement.style.verticalAlign = 'bottom';
    }
  };

  const insertImage = () => {
    const quill = editorRef.value?.getQuill();
    if (!quill || !successData.value?.length) return;
    const range = quill.getSelection(true);
    const length = range ? range.index : quill.getLength();
    const imageUrl = successData.value[0].url;

    quill.insertEmbed(length, 'image', imageUrl);

    const imageElement = quill.root.querySelector(`img[src="${imageUrl}"]`) as HTMLImageElement | null;
    if (imageElement) {
      normalizeEditorImages(undefined, imageElement);
    }

    quill.setSelection(length + 1);
    messageSuccess('上传图片成功');
  };
  const onImageLoadError = () => {
    messageError('上传图片失败');
  };

  const onImageFileChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    const { files } = input;
    if (!files?.length) return;

    fetchUploadImage(files).then((data) => {
      if (!data?.data?.length) {
        onImageLoadError();
        return;
      }
      successData.value = data.data as ResponseData['data'];
      onImageLoadSuccess();
    })
      .catch(() => {
        onImageLoadError();
      })
      .finally(() => {
        input.value = '';
      });
  };

  const extractUrls = (text: string) => {
    const urlRegex = /https?:\/\/[^\s\u4e00-\u9fa5]+/g;
    const links = text.match(urlRegex) || [];

    return links;
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

      if (val) {
        const urls = extractUrls(val);
        // 把配的url变成超链接
        nextTick(() => {
          const quill = editorRef.value?.getQuill();
          if (quill) {
            const text = quill.getText();
            urls.forEach((url: string) => {
              // 查找所有匹配的位置，而不仅仅是第一个
              let startIndex = 0;
              while (startIndex < text.length) {
                const index = text.indexOf(url, startIndex);
                if (index === -1) break;
                quill.formatText(index, url.length, 'link', url);
                startIndex = index + url.length;
              }
            });
          }
        });
      }
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


  const getActiveReportTableCell = (evt: ClipboardEvent) => {
    const path = typeof evt.composedPath === 'function' ? evt.composedPath() : [];
    for (let i = 0; i < path.length; i += 1) {
      const node = path[i];
      if (!(node instanceof HTMLElement)) {
        continue;
      }
      const cell = node.closest('td, th');
      if (cell?.closest('.ql-report-table')) {
        return cell as HTMLTableCellElement;
      }
    }
    const active = document.activeElement;
    if (active instanceof HTMLElement && active.closest('.ql-report-table')) {
      const cell = active.closest('td, th');
      if (cell) {
        return cell as HTMLTableCellElement;
      }
    }
    return null;
  };

  const ensureSelectionInTableCell = (cell: HTMLTableCellElement) => {
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    if (selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      if (cell.contains(range.commonAncestorContainer)) {
        return;
      }
    }
    const range = document.createRange();
    range.selectNodeContents(cell);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  const isTableCellPlaceholderOnly = (cell: HTMLTableCellElement) => {
    const normalized = cell.innerHTML
      .replace(/&nbsp;/gi, ' ')
      .trim()
      .toLowerCase();
    return normalized === '' || normalized === '<br>' || normalized === '<br/>';
  };

  const prepareTableCellForPaste = (targetCell: HTMLTableCellElement) => {
    if (isTableCellPlaceholderOnly(targetCell)) {
      targetCell.replaceChildren();
    }
  };

  const trimPlainTextForTableCell = (text: string) => text
    .replace(/\r\n/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/\n+$/g, '');

  const normalizePastedHtmlForTableCell = (rawHtml: string) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div id="paste-root">${rawHtml}</div>`, 'text/html');
    const root = doc.getElementById('paste-root');
    if (!root) {
      return rawHtml.trim();
    }
    root.querySelectorAll('meta, style, link').forEach(node => node.remove());
    const blockTags = ['P', 'DIV', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'];
    root.querySelectorAll(blockTags.join(',')).forEach((block) => {
      const parent = block.parentElement;
      if (!parent) {
        return;
      }
      while (block.firstChild) {
        parent.insertBefore(block.firstChild, block);
      }
      block.remove();
    });
    let normalizedHtml = root.innerHTML.trim();
    normalizedHtml = normalizedHtml.replace(/^(\s|<br\s*\/?>)+/gi, '');
    normalizedHtml = normalizedHtml.replace(/(\s|<br\s*\/?>)+$/gi, '');
    return normalizedHtml;
  };

  const setTableCellHtmlContent = (targetCell: HTMLTableCellElement, html: string) => {
    const normalized = normalizePastedHtmlForTableCell(html);
    targetCell.replaceChildren();
    if (normalized) {
      targetCell.insertAdjacentHTML('beforeend', normalized);
    } else {
      targetCell.append(document.createElement('br'));
    }
  };

  const cleanupTableCellTrailingBr = (targetCell: HTMLTableCellElement) => {
    const hasText = (targetCell.textContent || '').replace(/\u00a0/g, ' ').trim().length > 0;
    if (!hasText) {
      if (!targetCell.querySelector('img') && !targetCell.textContent?.trim()) {
        targetCell.replaceChildren();
        targetCell.append(document.createElement('br'));
      }
      return;
    }
    Array.from(targetCell.querySelectorAll('br')).forEach((br) => {
      let sibling = br.nextSibling;
      while (sibling && sibling.nodeType === Node.TEXT_NODE && !sibling.textContent?.trim()) {
        sibling = sibling.nextSibling;
      }
      if (!sibling) {
        br.remove();
      }
    });
    const { firstChild } = targetCell;
    if (firstChild?.nodeName === 'BR' && targetCell.childNodes.length > 1) {
      firstChild.remove();
    }
  };

  const finishTableCellPaste = (cell: HTMLTableCellElement) => {
    cleanupTableCellTrailingBr(cell);
    ensureSelectionInTableCell(cell);
    notifyEditorContentChange();
  };

  const insertHtmlIntoTableCell = (html: string) => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      return false;
    }
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const template = document.createElement('template');
    template.innerHTML = html;
    range.insertNode(template.content);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  };

  const pastePlainTextIntoTableCell = (text: string) => {
    const trimmed = trimPlainTextForTableCell(text);
    if (!trimmed) {
      return;
    }
    if (document.queryCommandSupported('insertText')) {
      document.execCommand('insertText', false, trimmed);
      return;
    }
    insertHtmlIntoTableCell(trimmed.replace(/\n/g, '<br>'));
  };

  const notifyEditorContentChange = () => {
    nextTick(() => {
      const quillInstance = editorRef.value?.getQuill();
      quillInstance?.root.dispatchEvent(new Event('input', { bubbles: true }));
    });
  };

  const getTableCellPosition = (cell: HTMLTableCellElement) => {
    const row = cell.parentElement as HTMLTableRowElement | null;
    const table = cell.closest('table');
    if (!row || !table) {
      return null;
    }
    const rows = Array.from(table.querySelectorAll('tr'));
    const rowIndex = rows.indexOf(row);
    const cells = Array.from(row.querySelectorAll('td, th'));
    const colIndex = cells.indexOf(cell);
    if (rowIndex < 0 || colIndex < 0) {
      return null;
    }
    return {
      rowIndex,
      colIndex,
      rows,
    };
  };

  const getTableCellAt = (
    table: HTMLTableElement,
    rowIndex: number,
    colIndex: number,
  ): HTMLTableCellElement | null => {
    const row = table.querySelectorAll('tr')[rowIndex];
    if (!row) {
      return null;
    }
    const cells = row.querySelectorAll('td, th');
    return (cells[colIndex] as HTMLTableCellElement) || null;
  };

  const pasteGridPlainTextIntoTable = (startCell: HTMLTableCellElement, plainText: string) => {
    const table = startCell.closest('table');
    const position = getTableCellPosition(startCell);
    if (!table || !position) {
      pastePlainTextIntoTableCell(plainText);
      return;
    }
    const lines = plainText.replace(/\r\n/g, '\n').split('\n');
    while (lines.length > 0 && lines[lines.length - 1] === '') {
      lines.pop();
    }
    lines.forEach((line, rowOffset) => {
      const values = line.split('\t');
      values.forEach((value, colOffset) => {
        const target = getTableCellAt(
          table,
          position.rowIndex + rowOffset,
          position.colIndex + colOffset,
        );
        if (target) {
          target.textContent = value;
        }
      });
    });
  };

  const handleTableCellPaste = async (evt: ClipboardEvent, tableCell: HTMLTableCellElement) => {
    evt.preventDefault();
    evt.stopPropagation();

    const { clipboardData } = evt;
    if (!clipboardData) {
      return;
    }
    if (clipboardData.files && clipboardData.files.length > 0) {
      return;
    }

    tableCell.focus();
    prepareTableCellForPaste(tableCell);
    ensureSelectionInTableCell(tableCell);

    const plainText = trimPlainTextForTableCell(clipboardData.getData('text/plain'));
    const html = clipboardData.getData('text/html');
    const hasBase64Image = Boolean(html && /<img[\s\S]*?src=["']data:image\//i.test(html));
    const isGridPaste = plainText.includes('\t')
      || (plainText.includes('\n') && hasTableContent(html || ''));

    try {
      if (isGridPaste) {
        pasteGridPlainTextIntoTable(tableCell, plainText);
        return;
      }

      if (hasBase64Image && html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const imgTags = doc.querySelectorAll('img');
        const promises: Promise<void>[] = [];
        imgTags.forEach((imgTag) => {
          const imageElement = imgTag as HTMLImageElement;
          imageElement.removeAttribute('width');
          imageElement.removeAttribute('height');
          imageElement.style.maxWidth = '100%';
          imageElement.style.height = 'auto';
          imageElement.style.verticalAlign = 'bottom';
          if (imageElement.src.startsWith('data:image/')) {
            promises.push(uploadImage(imageElement.src).then((url) => {
              if (url) {
                imageElement.src = url;
              }
            }));
          }
        });
        await Promise.all(promises);
        const contentHtml = normalizePastedHtmlForTableCell(doc.body.innerHTML);
        if (isTableCellPlaceholderOnly(tableCell)) {
          setTableCellHtmlContent(tableCell, contentHtml);
        } else {
          insertHtmlIntoTableCell(contentHtml);
        }
        nextTick(() => normalizeEditorImages(tableCell));
        return;
      }

      if (html && hasTableContent(html)) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const cells = doc.querySelectorAll('td, th');
        if (cells.length === 1) {
          setTableCellHtmlContent(tableCell, cells[0].innerHTML || plainText);
        } else {
          pastePlainTextIntoTableCell(plainText);
        }
        return;
      }

      if (html && html.trim()) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const contentHtml = normalizePastedHtmlForTableCell(doc.body.innerHTML);
        if (isTableCellPlaceholderOnly(tableCell) || !tableCell.textContent?.trim()) {
          setTableCellHtmlContent(tableCell, contentHtml);
        } else if (!insertHtmlIntoTableCell(contentHtml)) {
          tableCell.insertAdjacentHTML('beforeend', contentHtml);
        }
      } else {
        pastePlainTextIntoTableCell(plainText);
      }
    } finally {
      finishTableCellPaste(tableCell);
    }
  };

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown);
    const quill = editorRef.value?.getQuill();
    editorRef.value?.setHTML(props.default);
    if (quill) {
      nextTick(() => normalizeEditorImages(quill.root));
      quill.root.addEventListener(
        'paste',
        async (evt: ClipboardEvent) => {
          quill.enable(!props?.disabled); // source设置用户通过鼠标或键盘等输入设备进行编辑的能力。当"api"或 时，不会影响 API 调用的功能"silent"。
          const clipboardData = evt.clipboardData || (evt as any).originalEvent?.clipboardData;
          if (!clipboardData) {
            return;
          }

          const tableCell = getActiveReportTableCell(evt);
          if (tableCell) {
            await handleTableCellPaste(evt, tableCell);
            return;
          }

          const html = clipboardData.getData('text/html');
          const hasFiles = clipboardData.files && clipboardData.files.length > 0;

          if (html) {
            evt.preventDefault();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const imgTags = doc.querySelectorAll('img');
            const promises: Promise<void>[] = [];

            // base64图片拦截处理
            if (imgTags.length > 0) {
              for (let index = 0; index < imgTags.length; index += 1) {
                const imgTag = imgTags[index] as HTMLImageElement;
                imgTag.removeAttribute('width');
                imgTag.removeAttribute('height');
                imgTag.style.maxWidth = '100%';
                imgTag.style.height = 'auto';
                imgTag.style.verticalAlign = 'bottom';
                const base64Image = imgTag.src;
                // base64
                if (base64Image.startsWith('data:image/')) {
                  promises.push(uploadImage(base64Image).then((url) => {
                    imgTag.src = url; // 替换为上传后的 URL
                  }));
                }
              }
              await Promise.all(promises);
            }
            quill.focus();
            const range = quill.getSelection(true);
            const pasteIndex = range ? range.index : Math.max(0, quill.getLength() - 1);
            quill.clipboard.dangerouslyPasteHTML(pasteIndex, doc.body.innerHTML);
            nextTick(() => normalizeEditorImages(quill.root));
          }

          // 单个文件检测处理
          if (hasFiles) {
            evt.preventDefault();
            const { files } = clipboardData;
            fetchUploadImage(files).then((data) => {
              if (!data) return;
              successData.value = data.data;
              insertImage();
            });
          }
        },
        true,
      );
    }
  });

  // 组件卸载时移除事件监听
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown);
    exitFullscreen();
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

/* parent 模式：原地增高，保持在文档流内 */
.editor-wrap.expanded-mode {
  display: flex;
  flex-direction: column;
  height: var(--editor-expanded-height, 360px);

  .ql-container.ql-snow {
    height: auto !important;
    min-height: 0 !important;
    transition: min-height .2s ease;
    flex: 1;
  }

  .ql-editor {
    flex: 1;
    min-height: 0 !important;
  }
}

.editor-wrap:not(.expanded-mode)[style*='--editor-collapsed-height'] .ql-container.ql-snow,
.editor-wrap .ql-container.ql-snow {
  transition: min-height .2s ease;
}

.ql-editor {
  color: black;

  img {
    display: inline;
    height: auto;
    max-width: 100%;
    vertical-align: bottom;
  }
}

/* 全屏模式样式 */
.editor-wrap.fullscreen-mode {
  position: fixed;
  z-index: 9999;
  display: flex;
  padding: 12px 16px;
  margin: 0;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 0 16px 0 rgb(0 0 0 / 12%);
  box-sizing: border-box;
  flex-direction: column;

  .ql-editor {
    color: black;
    border: 1px solid #ccc;
  }

  .ql-toolbar {
    flex-shrink: 0;
    padding: 8px 0 !important;
    background: #fff !important;
    border-bottom: 1px solid #ccc;
  }

  .ql-container.ql-snow {
    height: auto !important;
    min-height: 0;
    font-size: 14px;
    line-height: 1.6;
    border: none;
    flex: 1;
  }

  .editor-tip-len {
    position: absolute;
    right: 20px;
    bottom: 16px;
    padding: 4px 8px;
    font-size: 12px;
    color: #63656e;
    background: rgb(255 255 255 / 90%);
    border-radius: 4px;
  }
}

.editor-wrap.fullscreen-mode--main {
  z-index: 2100;
}

.editor-wrap.expanded-mode .ql-toolbar .ql-fullscreen::before {
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

.editor-wrap--report .ql-editor .ql-report-table {
  margin: 0 0 16px;
}

.editor-wrap--report .ql-editor table {
  width: 100%;
  margin: 0 0 16px;
  font-size: 14px;
  border-collapse: collapse;
  table-layout: auto;
}

.editor-wrap--report .ql-editor th,
.editor-wrap--report .ql-editor td {
  padding: 10px 12px;
  color: #313238;
  text-align: left;
  vertical-align: top;
  border: 1px solid #dcdee5;
}

.editor-wrap--report .ql-editor thead th {
  font-weight: 600;
  color: #313238;
  background: #f5f7fa;
}

.editor-wrap--report .ql-toolbar .editor-table-btn {
  width: auto !important;
  padding: 0 8px !important;
  margin: 0 4px;
  font-size: 14px !important;
  line-height: 24px !important;
  color: #3a84ff !important;
  cursor: pointer;
  background: transparent !important;
  border: none !important;
  border-radius: 0;
  box-shadow: none !important;
}

.editor-wrap--report .ql-toolbar .editor-table-btn:hover {
  opacity: 80%;
}
</style>
