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
    <quill-editor
      ref="editorRef"
      v-model:content="content"
      content-type="html"
      disabled
      :options="options"
      :placeholder="t('请输入')"
      :style="{background: backgroundColor}"
      theme="snow"
      @ready="onEditorReady"
      @update:content="onContentChange" />
    <div
      v-if="maxLen"
      class="editor-tip-len">
      <span
        :class="{'can-edit': TiLength < maxLen}">
        {{ TiLength }}
      </span> / {{ maxLen }}
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    nextTick,
    onMounted,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  const props = withDefaults(defineProps<Props>(), {
    maxLen: 0,
    default: '',
    disabled: false,
    height: 'auto',
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  import { QuillEditor } from '@vueup/vue-quill';

  import '@vueup/vue-quill/dist/vue-quill.snow.css';
  import '@vueup/vue-quill/dist/vue-quill.bubble.css';

  interface Emits{
    (e: 'update:content', value: string): void,
  }
  interface Props{
    disabled?: boolean;
    default?: string;
    maxLen?: number;
    height?: string;
  }
  const content = ref();
  const editorRef = ref();
  const TiLength = ref(0);
  const options = reactive({
    modules: {
      toolbar: {
        container: [
          [
            { header: 1 },
            'bold',
            'italic',
            'strike',
            'underline',
            { color: [] },
          ],
          [
            { align: '' },
            { align: 'center' },
            { align: 'right' },
            'blockquote',
            { list: 'ordered' }, // 有序
            { list: 'bullet' }, // 无序列表的图标
          ],
          [
            'link',
            { background: [] },
            'code-block',
          ],
        ],
      },
      history: {
        delay: 1000,
        maxStack: 50,
        userOnly: true,
      },
    },
  });
  const backgroundColor = ref('#fff');


  const onContentChange = (val: string) => {
    if (props.maxLen) {
      editorRef.value?.getQuill().deleteText(props.maxLen, 4);
    }
    if (!content.value || content.value === '') {
      TiLength.value = 0;
    } else {
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    }
    emits('update:content', val);
  };
  const onEditorReady = () => {
    nextTick(() => {
      if (props.default) {
        content.value = props.default;
      }
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    });
  };

  onMounted(() => {
    editorRef.value?.setHTML(props.default);
    editorRef.value?.getQuill().enable(!props?.disabled);
  });

  watch(() => props.default, () => {
    content.value = props.default;
  }, {
    immediate: true,
  });
  watch(() => props.disabled, () => {
    editorRef.value?.getQuill().enable(!props.disabled);
  });
  watch(() => props.height, () => {
    if (props.height) {
      nextTick(() => {
        const el = document.querySelector('.ql-container.ql-snow') as HTMLElement;
        if (el) {
          el.style.height = props.height;
        }
      });
    }
  }, {
    immediate: true,
  });
</script>
<style lang="postcss">
.ql-toolbar {
  display: flex;
  padding: 0 !important;
  flex-wrap: wrap;
  align-items: center;
}


.ql-editor ul li:not(.ql-direction-rtl) {
  padding-left: 10px;
}

.ql-editor ol li:not(.ql-direction-rtl) {
  padding-left: 15px;
}

.ql-editor {
  ol,
  ul {
    padding-left: 0;
  }
}

/* 禁用时候的样式 */
.ql-disabled {
  background-color: #fafbfd !important;
}

:deep(.editor-wrap[active='false'] .ql-toolbar) {
  background-color: #fafbfd;
}

/* toolbar 激活样式 */
:deep(.editor-wrap[active='true'] .ql-toolbar) {
  background-color: #fff;
}

.editor-wrap {
  position: relative;
  padding: 5px 0;
  box-sizing: border-box;

  .editor-tip-len {
    position: absolute;
    right: 5px;
    bottom: 2px;
  }

  .can-edit {
    color: green;
  }
}

.ql-container.ql-snow {
  min-height: 120px;
  padding-bottom: 10px;
}
</style>
