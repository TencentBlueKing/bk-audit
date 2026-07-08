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
  <bk-dialog
    v-model:is-show="isShow"
    class="edit-visibility-dialog"
    :esc-close="false"
    :is-loading="submitLoading"
    :quick-close="false"
    :title="t('修改可见范围')"
    width="580"
    @closed="handleCancel">
    <div class="edit-visibility-form">
      <div class="form-item">
        <label class="form-label">{{ t('可见范围') }}</label>
        <div class="form-content">
          <visible-range-field
            :form-data="formData"
            match-selector-width
            popover-class="is-compact"
            @update:form-data="handleVisibleRangeChange" />
        </div>
      </div>
    </div>
    <template #footer>
      <bk-button
        class="mr8"
        :loading="submitLoading"
        theme="primary"
        @click="handleConfirm">
        {{ t('确定') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import {
    computed,
    reactive,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import type { FormData } from '../create-tool/types';
  import {
    applyVisibilityToFormData,
    buildVisibilityPayload,
    shouldSubmitVisibilityPayload,
  } from '../create-tool/submit-payload';
  import VisibleRangeField from '../create-tool/components/visible-range-field.vue';

  interface VisibilityInfo {
    binding_type?: string;
    visibility_type: string;
    scene_ids: Array<number | string>;
    system_ids: Array<number | string>;
  }

  interface TagItem {
    tag_id: string;
    tag_name: string;
  }

  interface ToolItem {
    uid: string;
    name: string;
    tags?: string[];
    visibility?: VisibilityInfo;
  }

  interface Props {
    target: ToolItem | null;
    tagsEnums?: TagItem[];
  }

  interface Emits {
    (e: 'success'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    tagsEnums: () => [],
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = defineModel<boolean>('isShow', { default: false });

  const tagNameMap = computed(() => {
    const map: Record<string, string> = {};
    props.tagsEnums.forEach((tag) => {
      map[tag.tag_id] = tag.tag_name;
    });
    return map;
  });

  const createDefaultFormData = (): FormData => ({
    name: '',
    tags: [],
    description: '',
    tool_type: '',
    updated_at: '',
    updated_by: '',
    is_bkvision: false,
    updated_time: null,
    data_search_config_type: '',
    visibility_type: 'scenes_and_systems',
    scene_ids: [],
    system_ids: [],
    config: {
      referenced_tables: [],
      input_variable: [],
      output_fields: [],
      sql: '',
      uid: '',
      output_config: {
        enable_grouping: false,
        groups: [],
      },
    },
  });

  const formData = reactive(createDefaultFormData());

  const resetFormData = (visibility?: VisibilityInfo) => {
    Object.assign(formData, createDefaultFormData());
    const applied = applyVisibilityToFormData(visibility as any);
    if (applied) {
      formData.visibility_type = applied.visibility_type;
      formData.scene_ids = applied.scene_ids;
      formData.system_ids = applied.system_ids;
    }
  };

  watch(isShow, (visible) => {
    if (visible) {
      resetFormData(props.target?.visibility);
    }
  });

  const handleVisibleRangeChange = (val: FormData) => {
    formData.visibility_type = val.visibility_type;
    formData.scene_ids = val.scene_ids;
    formData.system_ids = val.system_ids;
  };

  const {
    loading: submitLoading,
    run: updatePlatformTool,
  } = useRequest(ToolManageService.updatePlatformTool, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('修改成功'));
      isShow.value = false;
      emit('success');
    },
  });

  /** 列表返回 tag_id，更新接口要求传 tag_name */
  const resolveTagNames = () => (props.target?.tags || []).map(tag => tagNameMap.value[tag] || tag);

  const handleConfirm = () => {
    if (!props.target?.uid) return;

    const visibility = shouldSubmitVisibilityPayload(formData)
      ? buildVisibilityPayload(formData)
      : {
        visibility_type: 'all_visible' as const,
        scene_ids: [],
        system_ids: [],
      };

    updatePlatformTool({
      uid: props.target.uid,
      tags: resolveTagNames(),
      visibility,
    });
  };

  const handleCancel = () => {
    isShow.value = false;
  };
</script>

<style lang="postcss">
  .edit-visibility-dialog {
    .bk-modal-footer {
      padding: 8px 24px !important;
      text-align: right;
      background: #fafbfd !important;
      border-top: 1px solid #dcdee5 !important;
      box-shadow: none !important;
    }

    .bk-dialog-footer {
      padding: 0 !important;
      text-align: right;
      background: transparent !important;
      border-top: none !important;
      box-shadow: none !important;
    }

    .bk-dialog-body {
      padding: 16px 24px 24px !important;
      overflow: visible !important;
      border-bottom: none !important;
    }

    .bk-modal-content,
    .bk-dialog-content {
      overflow: visible !important;
    }
  }
</style>

<style lang="postcss" scoped>
  .edit-visibility-form {
    .form-item {
      display: flex;
      flex-direction: column;
      align-items: stretch;
    }

    .form-label {
      margin-bottom: 8px;
      font-size: 14px;
      line-height: 22px;
      color: #63656e;
      text-align: left;
    }

    .form-content {
      width: 100%;
      min-width: 0;
    }
  }

  .mr8 {
    margin-right: 8px;
  }
</style>
