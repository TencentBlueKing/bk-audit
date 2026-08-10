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
                :form-data="visibilityFormData"
                match-selector-width
                popover-class="is-compact"
                @update:form-data="handleVisibleRangeChange" />
            </div>
          </div>

          <scene-param-config
            v-if="showParamOverrideConfig"
            :form-data="visibilityFormData"
            :input-variables="inputVariables"
            override-select-full-width
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
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportConfigService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';

  import type {
    PanelDefaultValueOverrides,
    PanelVisibilityType,
  } from '@model/report-config/panel';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import SceneParamConfig from '@views/platform-manage/tool-manage/create-tool/components/scene-param-config.vue';
  import VisibleRangeField from '@views/platform-manage/tool-manage/create-tool/components/visible-range-field.vue';
  import {
    applyVisibilityToFormData,
    buildDefaultValueOverrides,
    buildVisibilityPayload,
    parseDefaultValueOverrides,
    reconcileSceneParamOverrides,
    shouldSubmitVisibilityPayload,
  } from '@views/platform-manage/tool-manage/create-tool/submit-payload';
  import type {
    FormData as ToolFormData,
    SceneParamOverride,
  } from '@views/platform-manage/tool-manage/create-tool/types';

  interface ReportItem {
    id: string;
    name: string;
    vision_id?: string;
    visibility_type?: PanelVisibilityType;
    scene_ids?: Array<number | string>;
    system_ids?: Array<number | string>;
    default_value_overrides?: PanelDefaultValueOverrides;
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
    target: ReportItem | null;
    sceneOptions?: SceneOption[];
    systemOptions?: SystemOption[];
  }

  interface Emits {
    (e: 'success'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    sceneOptions: () => [],
    systemOptions: () => [],
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = defineModel<boolean>('isShow', { default: false });

  const allSceneList = computed(() => props.sceneOptions);
  const allSystemList = computed(() => props.systemOptions.map(item => ({
    id: String(item.system_id || item.id),
    name: item.name,
  })));

  const createDefaultFormState = () => ({
    visibility_type: 'scenes_and_systems' as PanelVisibilityType,
    scene_ids: [] as number[],
    system_ids: [] as string[],
    scene_param_overrides: {} as Record<string, SceneParamOverride>,
  });

  const formState = ref(createDefaultFormState());
  const inputVariables = ref<ToolFormData['config']['input_variable']>([]);
  const isDetailReady = ref(false);
  const detailLoading = ref(false);
  const dialogContentKey = ref('');
  const pendingPanelId = ref('');

  const visibilityFormData = computed(() => ({
    name: '',
    tags: [],
    description: '',
    tool_type: '',
    updated_at: '',
    updated_by: '',
    is_bkvision: true,
    updated_time: null,
    data_search_config_type: '',
    visibility_type: formState.value.visibility_type,
    scene_ids: formState.value.scene_ids,
    system_ids: formState.value.system_ids,
    scene_param_overrides: formState.value.scene_param_overrides,
    config: {
      referenced_tables: [],
      input_variable: inputVariables.value,
      output_fields: [],
      sql: '',
      uid: '',
      output_config: {
        enable_grouping: false,
        groups: [],
      },
    },
  } as unknown as ToolFormData));

  const resetFormState = (target?: ReportItem | null) => {
    const applied = applyVisibilityToFormData({
      visibility_type: target?.visibility_type,
      scene_ids: target?.scene_ids?.map(Number),
      system_ids: target?.system_ids,
    });
    formState.value = {
      ...createDefaultFormState(),
      ...(applied || {}),
    };
  };

  const reconcileParamOverrides = () => {
    formState.value.scene_param_overrides = reconcileSceneParamOverrides(
      formState.value.scene_param_overrides,
      inputVariables.value,
      formState.value.visibility_type,
      formState.value.scene_ids || [],
      formState.value.system_ids || [],
      allSceneList.value,
      allSystemList.value,
    );
  };

  /**
   * 解析 share_detail 响应为覆盖参数选项（与报表侧滑一致）
   */
  const buildInputVariablesFromShareDetail = (res: any): ToolFormData['config']['input_variable'] => {
    if (!res?.data) return [];

    const panels = Array.isArray(res.data.panels) ? res.data.panels : [];
    const variables = Array.isArray(res.data.variables) ? res.data.variables : [];
    const filters = res.filters || {};
    const constants = res.constants || {};
    const filterUids = [...new Set(Object.keys(filters))];

    const getInputVariableConfig = (
      isVariables: boolean,
      com: any,
      defaultValue?: string | Array<string>,
    ) => ({
      raw_name: (isVariables ? com?.flag : com?.chartConfig?.flag) || '',
      display_name: (isVariables ? com?.description : com.title) || '',
      description: com.uid || '',
      field_category: isVariables ? (com.type || 'variable') : (com.type || ''),
      required: true,
      is_default_value: false,
      raw_default_value: defaultValue || '',
      default_value: defaultValue || '',
      choices: [] as Array<{ key: string; name: string }>,
    });

    const result: ToolFormData['config']['input_variable'] = [];
    const usedKeys = new Set<string>();

    filterUids.forEach((uid) => {
      const com = panels.find((p: any) => p.uid === uid);
      if (!com) return;
      const item = getInputVariableConfig(false, com, filters[com.uid]);
      if (!item.raw_name || usedKeys.has(item.raw_name)) return;
      usedKeys.add(item.raw_name);
      result.push(item);
    });

    variables.forEach((com: any) => {
      if (com.build_in) return;
      const defaultValue = constants[com.flag] ?? '';
      const item = {
        ...getInputVariableConfig(true, com, defaultValue),
        is_default_value: false,
        raw_default_value: defaultValue || '',
      };
      if (!item.raw_name || usedKeys.has(item.raw_name)) return;
      usedKeys.add(item.raw_name);
      result.push(item);
    });

    if (variables.length === 0) {
      Object.entries(constants).forEach(([flag, defaultValue]) => {
        if (!flag || usedKeys.has(flag) || flag.startsWith('bkv_')) return;
        usedKeys.add(flag);
        result.push({
          raw_name: flag,
          display_name: flag,
          description: '',
          field_category: 'variable',
          required: true,
          is_default_value: false,
          raw_default_value: (defaultValue as any) ?? '',
          default_value: (defaultValue as any) ?? '',
          choices: [],
        });
      });
    }

    return result;
  };

  const fetchDefaultValueOverridesByScopes = async (
    panelId: string,
    sceneIds: number[],
    systemIds: string[],
  ): Promise<PanelDefaultValueOverrides> => {
    const result: PanelDefaultValueOverrides = { scenes: {}, systems: {} };

    const sceneTasks = sceneIds.map(async (sceneId) => {
      try {
        const detail = await ReportConfigService.fetchPanelDetail({
          panel_id: panelId,
          scope_type: 'scene',
          scope_id: String(sceneId),
        });
        const override = detail?.default_value_override || {};
        if (Object.keys(override).length) {
          result.scenes![String(sceneId)] = override;
        }
      } catch (e) {
        console.error(`获取场景 ${sceneId} 默认值覆盖失败:`, e);
      }
    });

    const systemTasks = systemIds.map(async (systemId) => {
      try {
        const detail = await ReportConfigService.fetchPanelDetail({
          panel_id: panelId,
          scope_type: 'system',
          scope_id: String(systemId),
        });
        const override = detail?.default_value_override || {};
        if (Object.keys(override).length) {
          result.systems![String(systemId)] = override;
        }
      } catch (e) {
        console.error(`获取系统 ${systemId} 默认值覆盖失败:`, e);
      }
    });

    await Promise.all([...sceneTasks, ...systemTasks]);
    return result;
  };

  const loadDialogData = async () => {
    const { target } = props;
    const panelId = target?.id;
    if (!panelId) {
      return;
    }

    pendingPanelId.value = panelId;
    dialogContentKey.value = panelId;
    isDetailReady.value = false;
    detailLoading.value = true;
    resetFormState(target);
    inputVariables.value = [];

    try {
      if (target?.vision_id) {
        const res = await ToolManageService.fetchReportLists({ share_uid: target.vision_id });
        if (pendingPanelId.value !== panelId) return;
        inputVariables.value = buildInputVariablesFromShareDetail(res);
      }

      const sceneIds = (formState.value.scene_ids || []).map(Number);
      const systemIds = (formState.value.system_ids || []).map(String);
      const listOverrides = target?.default_value_overrides;
      const hasListOverrides = listOverrides !== undefined && listOverrides !== null;

      let overrides: PanelDefaultValueOverrides = { scenes: {}, systems: {} };
      if (hasListOverrides) {
        overrides = listOverrides || { scenes: {}, systems: {} };
      } else if (sceneIds.length > 0 || systemIds.length > 0) {
        overrides = await fetchDefaultValueOverridesByScopes(panelId, sceneIds, systemIds);
      }

      if (pendingPanelId.value !== panelId) return;

      formState.value.scene_param_overrides = parseDefaultValueOverrides(
        overrides,
        allSceneList.value,
        allSystemList.value,
      );
      reconcileParamOverrides();
      isDetailReady.value = true;
    } catch (e) {
      console.error('加载报表可见范围编辑数据失败:', e);
      if (pendingPanelId.value === panelId) {
        isDetailReady.value = true;
      }
    } finally {
      if (pendingPanelId.value === panelId) {
        detailLoading.value = false;
      }
    }
  };

  const resetDialogState = () => {
    isDetailReady.value = false;
    detailLoading.value = false;
    dialogContentKey.value = '';
    pendingPanelId.value = '';
    inputVariables.value = [];
    resetFormState();
  };

  watch(isShow, (visible) => {
    if (visible) {
      loadDialogData();
    }
  });

  const hasVisibleRangeSelection = computed(() => {
    const visibilityType = formState.value.visibility_type;
    if (visibilityType === 'all_visible'
      || visibilityType === 'all_scenes'
      || visibilityType === 'all_systems') {
      return false;
    }
    return (formState.value.scene_ids?.length ?? 0) > 0 || (formState.value.system_ids?.length ?? 0) > 0;
  });

  const showParamOverrideConfig = computed(() => hasVisibleRangeSelection.value
    && (inputVariables.value?.length ?? 0) > 0);

  const selectedSceneItems = computed(() => {
    if (!formState.value.scene_ids || formState.value.visibility_type === 'all_visible') return [];
    if (formState.value.visibility_type === 'all_scenes') return [];
    const sceneMap = new Map(allSceneList.value.map(scene => [scene.id, scene]));
    return formState.value.scene_ids
      .map(sceneId => sceneMap.get(sceneId))
      .filter((scene): scene is SceneOption => Boolean(scene));
  });

  const selectedSystemItems = computed(() => {
    if (!formState.value.system_ids || formState.value.visibility_type === 'all_visible') return [];
    if (formState.value.visibility_type === 'all_systems') return [];
    const systemMap = new Map(allSystemList.value.map(system => [system.id, system]));
    return formState.value.system_ids
      .map(systemId => systemMap.get(systemId))
      .filter((system): system is { id: string; name: string } => Boolean(system));
  });

  const handleVisibleRangeChange = (val: ToolFormData) => {
    formState.value.visibility_type = (val.visibility_type || 'scenes_and_systems') as PanelVisibilityType;
    formState.value.scene_ids = val.scene_ids || [];
    formState.value.system_ids = val.system_ids || [];
    reconcileParamOverrides();
  };

  const handleParamOverridesChange = (value: Record<string, SceneParamOverride>) => {
    formState.value.scene_param_overrides = value;
  };

  const {
    loading: submitLoading,
    run: updatePlatformPanel,
  } = useRequest(ReportConfigService.updatePlatformPanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('修改成功'));
      isShow.value = false;
      emit('success');
    },
  });

  const handleConfirm = () => {
    if (!props.target?.id || !isDetailReady.value) return;

    const hasVisibilitySelection = shouldSubmitVisibilityPayload(formState.value);
    const visibility = hasVisibilitySelection
      ? buildVisibilityPayload(formState.value)
      : {
        visibility_type: 'all_visible' as const,
        scene_ids: [],
        system_ids: [],
      };
    const sceneSystemOverrides = hasVisibilitySelection
      ? buildDefaultValueOverrides(formState.value.scene_param_overrides)
      : { scenes: {}, systems: {} };
    const defaultValueOverrides: PanelDefaultValueOverrides = {
      // 可见范围弹窗不改参数配置，保留列表带回的 default / use_bkvision_default
      default: props.target?.default_value_overrides?.default || {},
      scenes: sceneSystemOverrides.scenes || {},
      systems: sceneSystemOverrides.systems || {},
      use_bkvision_default: props.target?.default_value_overrides?.use_bkvision_default || {},
    };

    updatePlatformPanel({
      panel_id: props.target.id,
      visibility,
      default_value_overrides: defaultValueOverrides,
    });
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
