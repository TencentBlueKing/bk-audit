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
    width="680"
    @closed="handleClosed">
    <bk-loading
      class="edit-visibility-loading"
      :loading="detailLoading">
      <div
        v-if="isDetailReady"
        :key="dialogContentKey"
        class="edit-visibility-scroll">
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

          <scene-param-config
            v-if="showParamOverrideConfig"
            :form-data="formData"
            :input-variables="formData.config.input_variable"
            :selected-scenes="selectedSceneItems"
            :selected-systems="selectedSystemItems"
            @update:param-overrides="handleParamOverridesChange" />
        </div>
      </div>
    </bk-loading>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="detailLoading || !isDetailReady"
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
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import _ from 'lodash';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import type { FormData, SceneParamOverride } from '../create-tool/types';
  import {
    applyVisibilityToFormData,
    buildDefaultValueOverrides,
    buildVisibilityPayload,
    parseDefaultValueOverrides,
    reconcileSceneParamOverrides,
    shouldSubmitVisibilityPayload,
  } from '../create-tool/submit-payload';
  import SceneParamConfig from '../create-tool/components/scene-param-config.vue';
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

  interface SceneOption {
    id: number;
    name: string;
  }

  interface SystemOption {
    id: number | string;
    system_id?: string;
    name: string;
  }

  interface Props {
    target: ToolItem | null;
    tagsEnums?: TagItem[];
    sceneOptions?: SceneOption[];
    systemOptions?: SystemOption[];
  }

  interface Emits {
    (e: 'success'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    tagsEnums: () => [],
    sceneOptions: () => [],
    systemOptions: () => [],
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

  const allSceneList = computed(() => props.sceneOptions);
  const allSystemList = computed(() => props.systemOptions.map(item => ({
    id: String(item.id),
    name: item.name,
  })));

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
    scene_param_overrides: {},
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
  const toolConfigSnapshot = ref<Record<string, any> | null>(null);
  const isDetailReady = ref(false);
  const dialogContentKey = ref('');
  const pendingDetailUid = ref('');

  const resetFormData = (visibility?: VisibilityInfo) => {
    Object.assign(formData, createDefaultFormData());
    const applied = applyVisibilityToFormData(visibility as any);
    if (applied) {
      formData.visibility_type = applied.visibility_type;
      formData.scene_ids = applied.scene_ids;
      formData.system_ids = applied.system_ids;
    }
  };

  const applyToolDetail = (detail: Record<string, any>, visibility?: VisibilityInfo) => {
    resetFormData(visibility || detail.visibility);

    toolConfigSnapshot.value = _.cloneDeep(detail.config || {});
    formData.config.input_variable = detail.config?.input_variable || [];
    formData.scene_param_overrides = parseDefaultValueOverrides(
      detail.config?.default_value_overrides,
      allSceneList.value,
      allSystemList.value,
    );
    reconcileParamOverrides();
  };

  const reconcileParamOverrides = () => {
    formData.scene_param_overrides = reconcileSceneParamOverrides(
      formData.scene_param_overrides,
      formData.config.input_variable || [],
      formData.visibility_type,
      formData.scene_ids || [],
      formData.system_ids || [],
      allSceneList.value,
      allSystemList.value,
    );
  };

  const {
    loading: detailLoading,
    run: fetchToolsDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: null,
    onSuccess: (data) => {
      if (!pendingDetailUid.value || pendingDetailUid.value !== props.target?.uid) {
        return;
      }
      applyToolDetail(data as Record<string, any>, props.target?.visibility);
      isDetailReady.value = true;
    },
  });

  const resetDialogState = () => {
    isDetailReady.value = false;
    dialogContentKey.value = '';
    pendingDetailUid.value = '';
    toolConfigSnapshot.value = null;
    resetFormData();
  };

  const loadDialogData = () => {
    const uid = props.target?.uid;
    if (!uid) {
      return;
    }
    pendingDetailUid.value = uid;
    dialogContentKey.value = uid;
    isDetailReady.value = false;
    toolConfigSnapshot.value = null;
    resetFormData();
    fetchToolsDetail({ uid });
  };

  watch(isShow, (visible) => {
    if (visible) {
      loadDialogData();
    }
  });

  const hasVisibleRangeSelection = computed(() => {
    const visibilityType = formData.visibility_type;
    if (visibilityType === 'all_visible'
      || visibilityType === 'all_scenes'
      || visibilityType === 'all_systems') {
      return false;
    }
    return (formData.scene_ids?.length ?? 0) > 0 || (formData.system_ids?.length ?? 0) > 0;
  });

  const showParamOverrideConfig = computed(() => hasVisibleRangeSelection.value
    && (formData.config.input_variable?.length ?? 0) > 0);

  const selectedSceneItems = computed(() => {
    if (!formData.scene_ids || formData.visibility_type === 'all_visible') return [];
    if (formData.visibility_type === 'all_scenes') return [];
    return allSceneList.value.filter(scene => formData.scene_ids.includes(scene.id));
  });

  const selectedSystemItems = computed(() => {
    if (!formData.system_ids || formData.visibility_type === 'all_visible') return [];
    if (formData.visibility_type === 'all_systems') return [];
    return allSystemList.value.filter(system => formData.system_ids.includes(system.id));
  });

  const handleVisibleRangeChange = (val: FormData) => {
    formData.visibility_type = val.visibility_type;
    formData.scene_ids = val.scene_ids;
    formData.system_ids = val.system_ids;
    reconcileParamOverrides();
  };

  const handleParamOverridesChange = (value: Record<string, SceneParamOverride>) => {
    formData.scene_param_overrides = value;
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
    if (!props.target?.uid || !isDetailReady.value) return;

    const hasVisibilitySelection = shouldSubmitVisibilityPayload(formData);
    const visibility = hasVisibilitySelection
      ? buildVisibilityPayload(formData)
      : {
        visibility_type: 'all_visible' as const,
        scene_ids: [],
        system_ids: [],
      };
    const defaultValueOverrides = hasVisibilitySelection
      ? buildDefaultValueOverrides(formData.scene_param_overrides)
      : { scenes: {}, systems: {} };
    const originalOverrides = toolConfigSnapshot.value?.default_value_overrides || { scenes: {}, systems: {} };
    const overridesChanged = !_.isEqual(defaultValueOverrides, originalOverrides);

    const payload: Record<string, any> = {
      uid: props.target.uid,
      tags: resolveTagNames(),
      visibility,
    };

    // 后端校验要求完整 config，不能只传 default_value_overrides
    if (overridesChanged) {
      if (!toolConfigSnapshot.value) {
        return;
      }
      payload.config = {
        ..._.cloneDeep(toolConfigSnapshot.value),
        default_value_overrides: defaultValueOverrides,
      };
    }

    updatePlatformTool(payload);
  };

  const handleCancel = () => {
    isShow.value = false;
  };

  const handleClosed = () => {
    resetDialogState();
  };
</script>

<style lang="postcss">
  .edit-visibility-dialog.bk-modal {
    --edit-visibility-dialog-max-height: min(640px, calc(100vh - 80px));
    --edit-visibility-scroll-max-height: min(440px, calc(100vh - 220px));

    .bk-modal-wrapper {
      display: flex;
      flex-direction: column;
      max-height: var(--edit-visibility-dialog-max-height);
    }

    .bk-modal-body {
      display: flex;
      height: auto !important;
      max-height: var(--edit-visibility-dialog-max-height);
      min-height: 0;
      overflow: hidden;
      flex-direction: column;
    }

    .bk-modal-header {
      flex-shrink: 0;
    }

    .bk-modal-content {
      max-height: none !important;
      min-height: 0;
      overflow: hidden !important;
      flex: 1 1 auto;
    }

    .bk-modal-content > div {
      display: block !important;
      height: 100%;
    }

    .bk-modal-footer {
      flex-shrink: 0;
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

    .bk-dialog-content {
      height: 100%;
      padding: 0 !important;
      margin-top: 0 !important;
      margin-bottom: 0 !important;
    }

    .edit-visibility-loading {
      min-height: 100px;
    }

    /* 弹窗内容区：细滚动条，隐藏上下箭头 */
    .edit-visibility-scroll {
      height: 100%;
      max-height: var(--edit-visibility-scroll-max-height);
      overflow: hidden auto;
      scrollbar-gutter: stable;
      scrollbar-width: thin;
      scrollbar-color: #c4c6cc transparent;
    }

    .edit-visibility-scroll::-webkit-scrollbar {
      width: 4px;
      appearance: none;
    }

    .edit-visibility-scroll::-webkit-scrollbar-track {
      background: transparent;
    }

    .edit-visibility-scroll::-webkit-scrollbar-thumb {
      background-color: #c4c6cc;
      border-radius: 2px;
    }

    .edit-visibility-scroll::-webkit-scrollbar-thumb:hover {
      background-color: #979ba5;
    }

    .edit-visibility-scroll::-webkit-scrollbar-button,
    .edit-visibility-scroll::-webkit-scrollbar-button:single-button,
    .edit-visibility-scroll::-webkit-scrollbar-button:vertical:start:decrement,
    .edit-visibility-scroll::-webkit-scrollbar-button:vertical:start:increment,
    .edit-visibility-scroll::-webkit-scrollbar-button:vertical:end:decrement,
    .edit-visibility-scroll::-webkit-scrollbar-button:vertical:end:increment,
    .edit-visibility-scroll::-webkit-scrollbar-button:single-button:vertical:decrement,
    .edit-visibility-scroll::-webkit-scrollbar-button:single-button:vertical:increment,
    .edit-visibility-scroll::-webkit-scrollbar-corner {
      display: none !important;
      width: 0 !important;
      height: 0 !important;
      background: transparent !important;
      appearance: none !important;
    }
  }
</style>

<style lang="postcss" scoped>
  .edit-visibility-form {
    padding: 16px 24px 24px;

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
