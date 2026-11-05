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
  <div class="audit-inline-tag">
    <div
      v-if="isEditing"
      class="audit-inline-tag__editor"
      @click.stop>
      <bk-tag-input
        v-model="editValue"
        allow-create
        collapse-tags
        display-key="name"
        has-delete-icon
        :list="tagOptions"
        :placeholder="t('请输入并Enter结束')"
        save-key="id"
        search-key="name"
        trigger="focus" />
      <div class="audit-inline-tag__actions">
        <audit-icon
          v-bk-tooltips="{ content: t('确定'), placement: 'top' }"
          class="confirm-icon"
          svg
          type="check-line"
          @click.stop="handleConfirm"
          @mousedown.prevent />
        <audit-icon
          v-bk-tooltips="{ content: t('取消'), placement: 'top' }"
          class="cancel-icon"
          svg
          type="close"
          @click.stop="handleCancel"
          @mousedown.prevent />
      </div>
    </div>
    <div
      v-else
      class="audit-inline-tag__display">
      <edit-tag
        :data="tags"
        :show-copy="showCopy">
        <template
          v-if="editable"
          #suffix>
          <audit-icon
            v-if="!saving"
            class="audit-inline-tag__edit-icon"
            type="edit-fill"
            @click.stop="handleEdit" />
          <audit-icon
            v-else
            class="audit-inline-tag__loading"
            type="loading" />
        </template>
      </edit-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';

  import EditTag from './tag.vue';

  interface TagItem {
    tag_id: string | number;
    tag_name: string;
  }

  interface Props {
    tags: string[];
    tagList?: TagItem[];
    isEditing: boolean;
    editable?: boolean;
    saving?: boolean;
    showCopy?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    tags: () => [],
    tagList: () => [],
    editable: true,
    saving: false,
    showCopy: true,
  });

  const emit = defineEmits<{
    edit: [];
    cancel: [];
    save: [value: string[]];
  }>();

  const { t } = useI18n();
  const { messageWarn } = useMessage();

  const editValue = ref<string[]>([]);

  // 负数 tag_id 为系统内置/虚拟分类（全部、无标签、我创建的等），不能作为业务标签选择
  const tagOptions = computed(() => props.tagList.reduce((res, item) => {
    if (!String(item.tag_id).startsWith('-') && item.tag_name) {
      res.push({ id: item.tag_name, name: item.tag_name });
    }
    return res;
  }, [] as Array<{ id: string; name: string }>));

  watch(() => props.isEditing, (editing) => {
    if (editing) {
      editValue.value = [...(props.tags || [])];
    }
  }, { immediate: true });

  const validateTags = (tags: string[]) => {
    if (!tags.every(item => /^[\w\u4e00-\u9fa5-_]+$/.test(item))) {
      messageWarn(t('标签只允许中文、字母、数字、中划线或下划线组成'));
      return false;
    }
    if (!tags.every(item => /\D+/.test(item))) {
      messageWarn(t('标签不能为纯数字'));
      return false;
    }
    return true;
  };

  const handleEdit = () => {
    emit('edit');
  };

  const handleCancel = () => {
    emit('cancel');
  };

  const handleConfirm = () => {
    const nextTags = [...editValue.value];
    if (!validateTags(nextTags)) {
      return;
    }
    const original = props.tags || [];
    const isSame = original.length === nextTags.length
      && original.every((item, index) => item === nextTags[index]);
    if (isSame) {
      emit('cancel');
      return;
    }
    emit('save', nextTags);
  };
</script>

<style lang="postcss" scoped>
  @keyframes audit-inline-tag-spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .audit-inline-tag {
    width: 100%;
    min-width: 0;
  }

  .audit-inline-tag__display {
    display: flex;
    align-items: center;
    width: 100%;
    min-width: 0;

    :deep(.audit-edit-tag) {
      flex: 1;
      min-width: 0;
      overflow: hidden;
    }
  }

  .audit-inline-tag__edit-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: #4d4f56;
    cursor: pointer;
    opacity: 0%;

    &:hover {
      color: #3a84ff;
    }
  }

  .audit-inline-tag__loading {
    flex-shrink: 0;
    font-size: 14px;
    color: #3a84ff;
    animation: audit-inline-tag-spin 1s linear infinite;
  }

  .audit-inline-tag__editor {
    display: flex;
    width: 100%;
    max-width: 480px;
    gap: 8px;
    align-items: center;

    :deep(.bk-tag-input) {
      flex: 1;
      min-width: 0;
    }
  }

  .audit-inline-tag__actions {
    display: inline-flex;
    flex-shrink: 0;
    gap: 4px;
    align-items: center;
    height: 32px;
  }

  .confirm-icon {
    font-size: 18px;
    color: #2dcb56;
    cursor: pointer;

    &:hover {
      color: #45e06f;
    }
  }

  .cancel-icon {
    font-size: 18px;
    color: #ea3636;
    cursor: pointer;

    &:hover {
      color: #ff5656;
    }
  }
</style>

<style lang="postcss">
  /* 悬停整行时显示编辑图标；不在表格内使用时悬停组件自身显示 */
  tr:hover .audit-inline-tag__edit-icon,
  .audit-inline-tag:hover .audit-inline-tag__edit-icon {
    opacity: 100%;
  }
</style>
