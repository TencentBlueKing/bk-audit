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
    class="rich-text-editor-container"
    :class="{ 'is-fullscreen': isFullscreen }">
    <div class="editor-wrapper">
      <div
        v-if="disabled"
        class="editor-wrapper-disabled" />
      <quill-editor
        ref="quillEditorRef"
        v-model:content="content"
        content-type="html"
        :options="editorOptions"
        :placeholder="placeholder"
        @blur="handleBlur"
        @focus="handleFocus"
        @ready="onEditorReady"
        @text-change="handleTextChange" />
    </div>
    <a-i-agent-modal
      v-model:visible="showAIModal"
      :initial-prompt="editingPrompt"
      :risk-lisks="riskLisks"
      @confirm="handleAIAgentConfirm" />
    <delete-dialog
      v-model:visible="showDeleteDialog"
      :agent-name="deletingAgentName"
      @cancel="handleDeleteCancel"
      @confirm="handleDeleteConfirm" />
    <inset-var
      ref="insetVarRef"
      v-model:visible="showInsetVarModal"
      :event-info-data="eventInfoData"
      @confirm="handleInsetVarConfirm" />
  </div>
</template>

<script lang="ts" setup>
  import Quill from 'quill';
  import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import aiIconUrl from '@images/ai.svg';
  import fullScreenIconUrl from '@images/full screen.svg';
  import unFullScreenIconUrl from '@images/un-full-screen.svg';
  import { QuillEditor } from '@vueup/vue-quill';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import AIAgentBlot from './ai-model';
  import AIAgentModal from './ai-model.vue';
  import DeleteDialog from './delete-dialog.vue';
  import InsetVar from './inset-var.vue';

  import '@vueup/vue-quill/dist/vue-quill.snow.css';


  interface info {
    name: string,
    prompt_template: string,
    result: string,
  }
  interface riskItem {
    risk_id: string,
    title: string,
    strategy_id: number,
    created_at: string,
  }

  interface Props {
    disabled?: boolean;
    riskLisks: Array<riskItem>;
    eventInfoData?: any[];
  }

  interface expose {
    getAiLists: () => any[];
    setQuillContent: (content: string) => void;
    getContentVal: () => string;
    getQuillContent: () => string;
    hasContent: () => boolean;
    clearContent: () => void;
  }

  interface emits {
    (e: 'isHasContent', value: boolean): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    eventInfoData: () => [],
  });
  const emit = defineEmits<emits>();
  const { t } = useI18n();
  // 定义 Quill 实例类型
  interface QuillInstance {
    root: HTMLElement;
    getSelection: (focus?: boolean) => { index: number; length: number } | null;
    getIndex: (blot: any) => number | null;
    getLength: () => number;
    deleteText: (index: number, length: number) => void;
    insertText: (index: number, text: string, source?: string, force?: boolean) => void;
    insertEmbed: (index: number, type: string, value: any) => void;
    setSelection: (index: number, length?: number) => void;
    getModule: (name: string) => any;
    getContents: () => any;
    setContents: (delta: any, source?: string) => void;
    updateContents: (delta: any, source?: string) => any;
    clipboard: {
      convert: (html: string) => any;
      dangerouslyPasteHTML: (index: number, html: string) => void;
    };
  }

  const quillEditorRef = ref<InstanceType<typeof QuillEditor> | null>(null);
  const content = ref('');
  let quill: QuillInstance | null = null;
  const showAIModal = ref(false);
  const editingPrompt = ref<info | null>(null);
  const editingNode = ref<HTMLElement | null>(null);
  const savedSelection = ref<{ index: number; length: number } | null>(null);
  const showDeleteDialog = ref(false);
  const deletingAgentName = ref('');
  const deletingNode = ref<HTMLElement | null>(null);
  const previousContent = ref<any>(null);
  const pendingDeleteAgent = ref<{ node: HTMLElement; name: string } | null>(null);
  const showInsetVarModal = ref(false);
  const insetVarRef = ref();
  const aiList = ref<info[]>([]); // AI列表
  const placeholder = ref(t('请输入模版内容，或直接引用变量，也可使用AI智能体辅助快速生成'));
  const isFullscreen = ref(false);
  // 定义处理函数
  const insertVariable = () => {
    if (!quill) return;
    // 保存当前光标位置
    const range = quill.getSelection(true);
    savedSelection.value = range || { index: quill.getLength(), length: 0 };
    showInsetVarModal.value = true;
  };

  const handleInsetVarConfirm = (variableText: string) => {
    if (!quill) return;
    // 使用保存的光标位置插入变量
    const range = savedSelection.value || quill.getSelection() || { index: quill.getLength(), length: 0 };
    quill.insertText(range.index, variableText, 'user', true);
    quill.setSelection(range.index + variableText.length);
    // 清除保存的选择
    savedSelection.value = null;
    // 更新保存的内容状态
    previousContent.value = quill.getContents();
  };

  const openAIAgentModal = () => {
    if (!quill) return;
    // 保存当前光标位置
    const range = quill.getSelection(true);
    savedSelection.value = range || { index: quill.getLength(), length: 0 };
    editingPrompt.value = null;
    editingNode.value = null;
    showAIModal.value = true;
  };

  const setFullscreenButtonLabel = () => {
    if (!quill) return;
    const toolbar = quill.getModule('toolbar');
    if (toolbar && toolbar.container) {
      const fullscreenButton = toolbar.container.querySelector('.ql-fullscreen') as HTMLElement | null;
      if (fullscreenButton) {
        const icon = isFullscreen.value ? unFullScreenIconUrl : fullScreenIconUrl;
        const title = isFullscreen.value ? t('退出全屏') : t('全屏');
        fullscreenButton.innerHTML = `<img class="fullscreen-icon" src="${icon}" alt="${title}" />`;
        fullscreenButton.setAttribute('title', title);
        fullscreenButton.classList.add('custom-toolbar-icon-btn');
      }
    }
  };

  const toggleFullscreen = () => {
    isFullscreen.value = !isFullscreen.value;
    document.body.classList.toggle('ai-editor-fullscreen-open', isFullscreen.value);
    setFullscreenButtonLabel();
  };

  const handleFullscreenKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isFullscreen.value) {
      event.preventDefault();
      toggleFullscreen();
    }
  };

  const onEditorReady = (quillInstance: QuillInstance) => {
    quill = quillInstance;

    // 使用nextTick确保DOM已渲染
    nextTick(() => {
      if (!quill) return;
      // 添加自定义工具栏按钮文本
      const toolbar = quill.getModule('toolbar');
      if (toolbar && toolbar.container) {
        // 如果 disabled，给工具栏容器添加 disabled class
        if (props.disabled) {
          toolbar.container.classList.add('toolbar-disabled');
        }

        // 设置"引用变量"按钮
        const variableButton = toolbar.container.querySelector('.ql-variable');
        if (variableButton) {
          variableButton.innerHTML = '引用变量';
          variableButton.setAttribute('title', '引用变量');
          variableButton.classList.add('custom-toolbar-btn');
        }

        // 设置"引用AI智能体"按钮
        const aiAgentButton = toolbar.container.querySelector('.ql-aiagent');
        if (aiAgentButton) {
          aiAgentButton.innerHTML = `<img src="${aiIconUrl}" style="width: 20px; height: 15px; margin-right: 4px; vertical-align: middle; margin-top: -2px;" />引用AI智能体`;
          aiAgentButton.setAttribute('title', '引用AI智能体');
          aiAgentButton.classList.add('custom-toolbar-btn');
        }

        setFullscreenButtonLabel();
      }
    });

    // 监听编辑器点击事件，处理AI智能体块的编辑和删除
    const editorElement = quill.root;
    if (editorElement) {
      editorElement.addEventListener('click', handleEditorClick);
    }

    // 保存初始内容状态
    previousContent.value = quill.getContents();
  };
  const editorOptions = {
    theme: 'snow',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, 4, 5, 6, false] }],
          [{ font: [] }],
          [{ size: [] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ color: [] }, { background: [] }],
          [{ script: 'sub' }, { script: 'super' }],
          [{ header: 1 }, { header: 2 }, 'blockquote', 'code-block'],
          [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
          [{ direction: 'rtl' }, { align: [] }],
          ['link', 'image', 'video'],
          ['clean'],
          ['variable', 'aiagent', 'fullscreen'], // 自定义按钮
        ],
        handlers: {
          variable: insertVariable,
          aiagent: openAIAgentModal,
          fullscreen: toggleFullscreen,
        },
      },
    },
    placeholder: placeholder.value,
  };
  window.addEventListener('keydown', handleFullscreenKeydown);
  onBeforeUnmount(() => {
    if (quill && quill.root) {
      quill.root.removeEventListener('click', handleEditorClick);
    }
    document.body.classList.remove('ai-editor-fullscreen-open');
    window.removeEventListener('keydown', handleFullscreenKeydown);
  });

  const handleEditorClick = (e: MouseEvent) => {
    const { target } = e;
    if (!(target instanceof HTMLElement)) return;

    // 检查是否点击了编辑按钮
    if (target.closest('.ai-agent-edit')) {
      e.preventDefault();
      e.stopPropagation();
      const block = target.closest('.ql-ai-agent') as HTMLElement | null;
      if (block) {
        const promptTemplate = block.getAttribute('data-prompt') || '';
        const name = block.getAttribute('data-name') || '';
        const result = block.getAttribute('data-result') || '';
        // 从 aiList 中查找对应的完整 info 对象
        let promptInfo: info | null = null;
        if (name || promptTemplate) {
          promptInfo = aiList.value.find(item => item.name === name && item.prompt_template === promptTemplate) || null;
        }

        // 如果找到了，使用完整的 info 对象；否则从 DOM 属性创建
        if (promptInfo) {
          editingPrompt.value = { ...promptInfo };
        } else {
          // 从 DOM 属性创建 info 对象（fallback）
          editingPrompt.value = {
            name,
            prompt_template: promptTemplate,
            result,
          };
        }
        editingNode.value = block;
        showAIModal.value = true;
      }
      return;
    }

    // 检查是否点击了删除按钮
    if (target.closest('.ai-agent-delete')) {
      e.preventDefault();
      e.stopPropagation();
      const block = target.closest('.ql-ai-agent') as HTMLElement | null;
      if (block) {
        // 获取智能体的名称
        const name = block.getAttribute('data-name') || '';
        // 如果名称为空，使用默认名称
        deletingAgentName.value = name || t('AI智能体');
        deletingNode.value = block;
        showDeleteDialog.value = true;
      }
      return;
    }
  };

  const handleAIAgentConfirm = (promptInfo: info) => {
    if (!quill) return;

    // 提取数据
    const promptText = promptInfo?.prompt_template || '';
    const name = promptInfo?.name || '';
    const result = promptInfo?.result || '';

    if (editingNode.value) {
      // 编辑现有块
      // 获取旧的 name 和 prompt_template 用于匹配 aiList 中的项
      const oldName = editingNode.value.getAttribute('data-name') || '';
      const oldPromptTemplate = editingNode.value.getAttribute('data-prompt') || '';

      editingNode.value.setAttribute('data-prompt', promptText);
      if (name) {
        editingNode.value.setAttribute('data-name', name);
      }
      if (result) {
        editingNode.value.setAttribute('data-result', result);
      }

      // 更新显示内容
      const labelElement = editingNode.value.querySelector('.ai-agent-label') as HTMLElement | null;
      const promptElement = editingNode.value.querySelector('.ai-agent-prompt') as HTMLElement | null;
      if (labelElement) {
        labelElement.textContent = name || '';
      }
      if (promptElement) {
        promptElement.textContent = result || promptText || '';
      }

      // 更新 aiList 中对应的项
      if (oldName || oldPromptTemplate) {
        // eslint-disable-next-line max-len
        const index = aiList.value.findIndex(item => item.name === oldName && item.prompt_template === oldPromptTemplate);
        if (index !== -1) {
          aiList.value[index] = promptInfo;
        }
      }

      editingNode.value = null;
    } else {
      // 插入新块 - 使用保存的光标位置
      const range = savedSelection.value || quill.getSelection() || { index: quill.getLength(), length: 0 };

      const id = Date.now().toString();
      quill.insertEmbed(range.index, 'aiAgent', {
        id,
        prompt: promptText,
        name,
        result,
      });
      // 在插入的块后面插入换行符
      quill.insertText(range.index + 1, '\n', 'user', true);
      // 移动光标到换行符后面
      quill.setSelection(range.index + 2);
      // 清除保存的选择
      savedSelection.value = null;

      // 添加到 aiList
      aiList.value.push(promptInfo);
    }

    // 更新保存的内容状态
    previousContent.value = quill.getContents();
  };

  const handleDeleteConfirm = () => {
    if (!quill || !deletingNode.value) return;

    // 获取要删除的节点的信息
    const name = deletingNode.value.getAttribute('data-name') || '';
    const promptTemplate = deletingNode.value.getAttribute('data-prompt') || '';

    // 从 aiList 中删除对应的项
    if (name || promptTemplate) {
      aiList.value = aiList.value.filter(item => !(item.name === name && item.prompt_template === promptTemplate));
    }

    // 使用Quill的find方法找到对应的blot
    const blot = Quill.find(deletingNode.value);
    if (blot) {
      const index = quill.getIndex(blot);
      if (index !== null && index >= 0) {
        quill.deleteText(index, 1);
      }
    }
    // 关闭弹窗并清除状态
    showDeleteDialog.value = false;
    deletingNode.value = null;
    deletingAgentName.value = '';
    pendingDeleteAgent.value = null;

    // 更新保存的内容状态
    previousContent.value = quill.getContents();
  };

  const handleDeleteCancel = () => {
    showDeleteDialog.value = false;
    deletingNode.value = null;
    deletingAgentName.value = '';
    pendingDeleteAgent.value = null;

    // 如果之前保存了内容，恢复它
    if (previousContent.value && quill) {
      const currentSelection = quill.getSelection();
      quill.setContents(previousContent.value, 'user');
      // 恢复光标位置
      if (currentSelection) {
        quill.setSelection(currentSelection.index, currentSelection.length);
      }
      // 更新保存的内容
      previousContent.value = quill.getContents();
    }
  };

  // 获取所有智能体块的信息
  const getAllAIAgentBlocks = (): Array<{ node: HTMLElement; index: number; prompt: string }> => {
    if (!quill) return [];
    const blocks: Array<{ node: HTMLElement; index: number; prompt: string }> = [];
    const editorElement = quill.root;
    if (!editorElement) return blocks;

    const aiAgentNodes = editorElement.querySelectorAll('.ql-ai-agent');
    aiAgentNodes.forEach((node) => {
      const htmlNode = node as HTMLElement;
      const blot = Quill.find(htmlNode);
      if (blot && quill) {
        const index = quill.getIndex(blot);
        if (index !== null && index >= 0) {
          const prompt = htmlNode.getAttribute('data-prompt') || '';
          blocks.push({ node: htmlNode, index, prompt });
        }
      }
    });
    return blocks;
  };
  const handleFocus = () => {
    if (!quill) return;
    placeholder.value = '';
    if (quill.root) {
      quill.root.dataset.placeholder = placeholder.value;
    }
  };
  const handleBlur = () => {
    if (!quill) return;
    placeholder.value = t('请输入模版内容，或直接引用变量，也可使用AI智能体辅助快速生成');
    if (quill.root) {
      quill.root.dataset.placeholder = placeholder.value;
    }
  };
  // 处理文本变化事件
  const handleTextChange = () => {
    if (!quill || showDeleteDialog.value) return;

    // 获取删除前后的智能体块
    const previousBlocks = previousContent.value
      ? getAllAIAgentBlocksFromContent(previousContent.value)
      : [];
    const currentBlocks = getAllAIAgentBlocks();

    // 检查是否有智能体块被删除
    if (previousBlocks.length > currentBlocks.length) {
      // 找到被删除的智能体块（通过比较索引和 prompt）
      const deletedBlock = previousBlocks.find(prevBlock =>
        // 检查当前块中是否还存在相同索引或相同 prompt 的块
        // eslint-disable-next-line implicit-arrow-linebreak
        !currentBlocks.some(currBlock => currBlock.index === prevBlock.index || currBlock.prompt === prevBlock.prompt));

      if (deletedBlock) {
        // 保存被删除的智能体块信息
        const deletedPrompt = deletedBlock.prompt;
        const deletedIndex = deletedBlock.index;

        // 恢复之前的内容
        const currentSelection = quill.getSelection();
        quill.setContents(previousContent.value, 'user');

        // 使用 nextTick 确保 DOM 已更新
        nextTick(() => {
          if (!quill) return;

          // 恢复光标位置（如果可能）
          if (currentSelection) {
            // 尝试保持光标位置，但如果删除的是光标位置的内容，可能需要调整
            const adjustedIndex = Math.min(currentSelection.index, quill.getLength() - 1);
            quill.setSelection(adjustedIndex, 0);
          }

          // 找到对应的DOM节点（通过 prompt 匹配）
          const editorElement = quill.root;
          if (editorElement && quill) {
            const aiAgentNodes = editorElement.querySelectorAll('.ql-ai-agent');
            let targetNode: HTMLElement | null = null;

            for (let i = 0; i < aiAgentNodes.length; i++) {
              const node = aiAgentNodes[i];
              const htmlNode = node as HTMLElement;
              const blot = Quill.find(htmlNode);
              if (blot && quill) {
                const index = quill.getIndex(blot);
                const prompt = htmlNode.getAttribute('data-prompt') || '';
                // 通过索引或 prompt 匹配
                if (index === deletedIndex || prompt === deletedPrompt) {
                  targetNode = htmlNode;
                  break;
                }
              }
            }

            if (targetNode) {
              // 显示确认弹窗
              const name = targetNode.getAttribute('data-name') || '';
              deletingAgentName.value = name || t('AI智能体');
              deletingNode.value = targetNode;
              pendingDeleteAgent.value = { node: targetNode, name: deletingAgentName.value };
              showDeleteDialog.value = true;
              // 恢复内容后，更新 previousContent 为恢复后的内容
              previousContent.value = quill.getContents();
            }
          }
        });
        return;
      }
    }

    // 更新保存的内容状态（只有在没有检测到删除时才更新）
    previousContent.value = quill.getContents();
  };

  // 从Delta内容中获取智能体块信息（用于比较）
  const getAllAIAgentBlocksFromContent = (delta: any): Array<{ index: number; prompt: string }> => {
    const blocks: Array<{ index: number; prompt: string }> = [];
    if (!delta || !delta.ops) return blocks;

    let currentIndex = 0;
    delta.ops.forEach((op: any) => {
      if (op.insert && typeof op.insert === 'object' && op.insert.aiAgent) {
        blocks.push({
          index: currentIndex,
          prompt: op.insert.aiAgent.prompt || '',
        });
        currentIndex += 1;
      } else if (typeof op.insert === 'string') {
        currentIndex += op.insert.length;
      } else if (op.insert && typeof op.insert === 'object') {
        // 其他嵌入内容
        currentIndex += 1;
      }
    });

    return blocks;
  };

  // 监听 disabled 变化，更新工具栏按钮状态
  watch(() => props.disabled, (isDisabled) => {
    nextTick(() => {
      if (!quill) return;
      const toolbar = quill.getModule('toolbar');
      if (toolbar && toolbar.container) {
        if (isDisabled) {
          toolbar.container.classList.add('toolbar-disabled');
        } else {
          toolbar.container.classList.remove('toolbar-disabled');
        }
      }
    });
  });
  // 判断编辑器是否有实际内容
  const hasContent = (html?: string): boolean => {
    const htmlContent = typeof html === 'string' ? html : (quill?.root?.innerHTML || '');
    if (!htmlContent || htmlContent.trim() === '') {
      return false;
    }

    // 解析 HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    // eslint-disable-next-line prefer-destructuring
    const body = doc.body;

    // 检查是否有 AI Agent 块（即使没有文本，有 AI Agent 也算有内容）
    const aiAgentNodes = body.querySelectorAll('.ql-ai-agent');
    if (aiAgentNodes.length > 0) {
      return true;
    }

    // 获取所有文本内容（去除 HTML 标签）
    const textContent = body.textContent || body.innerText || '';
    const trimmedText = textContent.trim();

    // 如果有实际文本内容，返回 true
    if (trimmedText.length > 0) {
      return true;
    }

    // 检查是否有图片
    const images = body.querySelectorAll('img');
    if (images.length > 0) {
      return true;
    }

    // 检查是否有其他嵌入内容（如视频、链接等）
    const embeds = body.querySelectorAll('iframe, video, embed, object');
    if (embeds.length > 0) {
      return true;
    }

    return false;
  };

  // 监听 content 变化
  watch(() => content.value, () => {
    const hasActualContent = hasContent();
    emit('isHasContent', hasActualContent);
  }, {
    immediate: true,
    deep: true,
  });
  // 获取编辑器内容
  const getQuillContent = () => {
    if (!quill) return '';
    return JSON.stringify(quill.getContents());
  };
  const getContentVal = () => {
    if (!quill) return '';
    // 直接从 Quill 实例的 DOM 获取 HTML 内容
    return quill.root.innerHTML;
  };

  // 获取 getAiLists 数据
  const getAiLists = () => aiList.value;

  const initValue = (data: string) => {
    if (!quill) return;
    const delta = JSON.parse(data);
    quill.setContents(delta, 'silent');

    // 从 Delta 内容中提取 AI Agent 信息并恢复 aiList
    const aiAgents: info[] = [];
    if (delta && delta.ops) {
      delta.ops.forEach((op: any) => {
        if (op.insert && typeof op.insert === 'object' && op.insert.aiAgent) {
          const aiAgentData = op.insert.aiAgent;
          aiAgents.push({
            name: aiAgentData.name || '',
            prompt_template: aiAgentData.prompt || '',
            result: aiAgentData.result || '',
          });
        }
      });
    }
    aiList.value = aiAgents;

    // 更新保存的内容状态
    previousContent.value = quill.getContents();
    emit('isHasContent', true);
  };
  // 暴露方法给父组件
  defineExpose<expose>({
    getQuillContent,
    getContentVal,
    getAiLists,
    setQuillContent(data: string) {
      initValue(data);
    },
    hasContent: () => hasContent(),
    clearContent() {
      content.value = '';
      aiList.value = [];
      savedSelection.value = null;
      if (quill) {
        quill.setContents([{ insert: '\n' }], 'silent');
        previousContent.value = quill.getContents();
      } else {
        previousContent.value = null;
      }
      emit('isHasContent', false);
    },
  });
</script>

<style lang="postcss" scoped>
.rich-text-editor-container {
  display: flex;
  overflow: hidden;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  flex-direction: column;
}

:deep(body.ai-editor-fullscreen-open) {
  overflow: hidden;
}

.rich-text-editor-container.is-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 2000;
  width: 100vw;
  height: 100vh;
  border-radius: 0;
}

.rich-text-editor-container.is-fullscreen .editor-wrapper {
  height: calc(100vh - 2px);
}

.rich-text-editor-container.is-fullscreen :deep(.quill-editor) {
  height: 100%;
}

.rich-text-editor-container.is-fullscreen :deep(.ql-editor) {
  min-height: calc(100vh - 120px);
}

.editor-wrapper {
  position: relative;
  min-height: 400px;
}

.editor-wrapper-disabled {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1000;
  width: 100%;
  height: 100%;
  background-color: rgb(250 251 253 / 40%)
}

.editor-wrapper :deep(.quill-editor) {
  min-height: 400px;
}

/* AI智能体块样式 */
:deep(.ql-ai-agent) {
  position: relative;
  display: block;
  width: 100%;
  height: 90px;
  padding: 0;
  margin: 0;
  line-height: 1;
}

:deep(.ai-agent-block) {
  position: absolute;
  top: 0;
  display: flex;
  width: 100%;
  min-height: auto;
  padding: 4px 12px;
  margin: 0;
  background: #f5f7fa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  align-items: center;
}

:deep(.ai-agent-content) {
  display: flex;
  height: 80px;
  padding-top: 10px;
  margin-left: 35px;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

:deep(.ai-agent-label) {
  font-family: MicrosoftYaHei-Bold, sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  letter-spacing: 0;
  color: #313238;
}

:deep(.ai-agent-prompt) {
  display: -webkit-box;
  overflow: hidden;
  font-family: MicrosoftYaHei, sans-serif;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
  text-align: justify;
  text-overflow: ellipsis;
  word-break: break-word;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

:deep(.ai-agent-actions) {
  position: absolute;
  top: 20px;
  right: 8px;
  display: flex;
  gap: 8px;
}

:deep(.ai-agent-edit),
:deep(.ai-agent-delete) {
  width: 16px;
  height: 16px;
  padding: 0;
  cursor: pointer;
  transition: all .2s;
  user-select: none;
  -webkit-user-drag: none;
}

:deep(.ai-agent-edit:hover) {
  opacity: 70%;
}

:deep(.ai-agent-delete:hover) {
  opacity: 70%;
}

/* Quill编辑器样式调整 */
:deep(.ql-editor) {
  min-height: 400px;
  padding: 12px 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
}

:deep(.ql-editor.ql-blank::before) {
  font-style: normal;
  color: #999;
}

/* 移除AI智能体块周围的默认间距 */
:deep(.ql-editor .ql-ai-agent) {
  padding: 0;
  margin: 0;
}

:deep(.ql-editor p) {
  margin: 0;
  line-height: 1.5;
}

/* 自定义工具栏按钮样式 - 文字按钮 */
:deep(.ql-toolbar .ql-variable),
:deep(.ql-toolbar .ql-aiagent) {
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
  transition: all .2s;
}

:deep(.ql-toolbar .ql-variable:hover),
:deep(.ql-toolbar .ql-aiagent:hover) {
  color: #3a84ff !important;
  background-color: transparent !important;
  opacity: 80%;
}

:deep(.ql-toolbar .ql-fullscreen) {
  width: 28px !important;
  height: 24px !important;
  padding: 0 4px !important;
}

:deep(.ql-toolbar .ql-fullscreen .fullscreen-icon) {
  display: inline-block;
  width: 16px;
  height: 16px;
  vertical-align: middle;
}

/* disabled 状态下自定义按钮样式 */
:deep(.ql-toolbar.toolbar-disabled .ql-variable),
:deep(.ql-toolbar.toolbar-disabled .ql-aiagent) {
  color: #c4c6cc !important;
  cursor: not-allowed !important;
}

:deep(.ql-toolbar.toolbar-disabled .ql-variable:hover),
:deep(.ql-toolbar.toolbar-disabled .ql-aiagent:hover) {
  color: #c4c6cc !important;
  opacity: 100% !important;
}

:deep(.ai-agent-ai) {
  position: absolute;
}


</style>
