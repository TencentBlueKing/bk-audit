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
  <bk-sideslider
    ext-cls="report-create-sideslider"
    :is-show="isShow"
    :quick-close="false"
    show-mask
    :title="isEditMode ? t('编辑报表') : t('新建报表')"
    :width="680"
    :z-index="9999"
    @closed="handleSliderClosed">
    <template #default>
      <div class="report-create-content">
        <bk-form
          ref="formRef"
          class="report-create-form"
          form-type="vertical"
          :model="formData"
          :rules="formRules">
          <!-- 关联 BKVision 报表 -->
          <bk-form-item
            :label="t('关联 BKVision 报表')"
            property="bkvisionReport"
            required>
            <div class="bkvision-select-wrapper">
              <bk-select
                v-model="formData.bkvisionReport"
                :clearable="false"
                filterable
                :placeholder="t('选择项目')"
                :popover-options="{
                  boundary: 'parent',
                  zIndex: 10050
                }"
                style="width: 500px;"
                @change="handleReportChange">
                <bk-option-group
                  v-for="group in chartGroupedLists"
                  :key="group.uid"
                  collapsible
                  :label="group.name">
                  <bk-option
                    v-for="item in group.share"
                    :id="item.uid"
                    :key="item.uid"
                    :name="`【${group.name}】${item.name}`">
                    <template #default>
                      <div class="report-option-content">
                        <span class="option-name">{{ item.name }}</span>
                        <audit-icon
                          class="preview-icon"
                          type="jump-link"
                          @click.stop="handlePreviewReport(item)" />
                      </div>
                    </template>
                  </bk-option>
                </bk-option-group>
              </bk-select>
              <bk-button
                v-if="formData.bkvisionReport"
                class="preview-btn"
                @click="handlePreview">
                {{ t('预览') }}
                <audit-icon
                  class="ml4"
                  type="jump-link" />
              </bk-button>
            </div>
          </bk-form-item>

          <!-- 报表名称 -->
          <bk-form-item
            :label="t('报表名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              :placeholder="t('请输入报表名称（选择报表后自动填充）')"
              @change="handleNameChange" />
          </bk-form-item>

          <!-- 可见范围：复用工具管理 VisibleRangeField（非必选，未选时后端默认全部可见） -->
          <bk-form-item
            :label="t('可见范围')"
            property="visibility_type">
            <visible-range-field
              :form-data="visibilityFormData"
              match-selector-width
              popover-class="is-compact"
              :popover-z-index="10050"
              @update:form-data="handleVisibleRangeChange" />
          </bk-form-item>

          <!-- 覆盖参数配置：加载中展示 loading，避免空态闪屏 -->
          <bk-loading
            v-if="visibilityParamLoading"
            class="visibility-param-loading"
            loading
            size="small">
            <div class="visibility-param-loading-placeholder" />
          </bk-loading>
          <scene-param-config
            v-else-if="showParamOverrideConfig"
            class="visibility-param-config"
            :form-data="paramConfigFormData"
            :input-variables="inputVariables"
            override-select-full-width
            :popover-z-index="10050"
            :selected-scenes="selectedSceneItems"
            :selected-systems="selectedSystemItems"
            @update:param-overrides="handleParamOverridesChange" />

          <!-- 描述 -->
          <bk-form-item
            :label="t('描述')"
            property="description">
            <bk-input
              v-model="formData.description"
              :maxlength="100"
              :placeholder="t('请输入')"
              :rows="3"
              show-word-limit
              type="textarea" />
          </bk-form-item>

          <!-- 是否启用 -->
          <bk-form-item
            :label="t('是否启用')"
            property="status">
            <div class="status-field">
              <bk-popover
                :is-show="enablePopoverVisible"
                placement="bottom-start"
                theme="light"
                trigger="manual"
                :z-index="10050"
                @after-hidden="enablePopoverVisible = false">
                <bk-switcher
                  :before-change="handleStatusBeforeChange"
                  :model-value="formData.enabled"
                  size="small"
                  theme="primary" />
                <template #content>
                  <div class="report-enable-popover">
                    <div class="report-enable-popover-title">
                      {{ t('确认启用该报表？') }}
                    </div>
                    <div class="report-enable-popover-text">
                      {{ t('启用后，可见范围内的空间将可以查看和使用该报表，确认启用吗？') }}
                    </div>
                    <div class="report-status-popover-actions">
                      <bk-button
                        class="mr8"
                        size="small"
                        theme="primary"
                        @click="handleConfirmEnable">
                        {{ t('启用') }}
                      </bk-button>
                      <bk-button
                        size="small"
                        @click="enablePopoverVisible = false">
                        {{ t('取消') }}
                      </bk-button>
                    </div>
                  </div>
                </template>
              </bk-popover>
              <span class="status-label">{{ formData.enabled ? t('启用') : t('停用') }}</span>
            </div>
          </bk-form-item>
        </bk-form>
      </div>
    </template>
    <template #footer>
      <bk-button
        class="mr8"
        :loading="submitLoading"
        theme="primary"
        @click="handleSubmit">
        {{ t('提交') }}
      </bk-button>
      <bk-button @click="handleClose">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-sideslider>
</template>

<script setup lang='ts'>
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import SceneManageService from '@service/scene-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import type { PanelVisibilityType } from '@model/report-config/panel';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import SceneParamConfig from '@views/platform-manage/tool-manage/create-tool/components/scene-param-config.vue';
  import VisibleRangeField from '@views/platform-manage/tool-manage/create-tool/components/visible-range-field.vue';
  import {
    applyVisibilityToFormData,
    buildDefaultValueOverrides,
    parseDefaultValueOverrides,
    reconcileSceneParamOverrides,
    shouldSubmitVisibilityPayload,
    buildVisibilityPayload,
  } from '@views/platform-manage/tool-manage/create-tool/submit-payload';
  import type {
    DefaultValueOverrides,
    FormData as ToolFormData,
    SceneParamOverride,
  } from '@views/platform-manage/tool-manage/create-tool/types';

  import { showReportDisableConfirm } from '../show-report-disable-confirm';

  export interface ReportFormData {
    id?: string;
    bkvisionReport: string;
    name: string;
    description: string;
    status?: 'published' | 'unpublished';
    enabled: boolean;
    visibility_type: PanelVisibilityType;
    scene_ids: number[];
    system_ids: string[];
    scene_param_overrides?: Record<string, SceneParamOverride>;
    /** 管理列表带回的完整覆盖配置 */
    default_value_overrides?: DefaultValueOverrides;
  }

  interface ChartListModel {
    uid: string;
    name: string;
    share: Array<{
      uid: string;
      name: string;
    }>;
  }

  interface Props {
    isShow: boolean;
    editData?: ReportFormData | null;
    chartLists?: ChartListModel[];
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
    (e: 'success', panelId?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    editData: null,
    chartLists: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const isEditMode = computed(() => !!props.editData);
  const chartLists = computed(() => props.chartLists || []);
  const chartGroupedLists = computed(() => chartLists.value);
  const { messageSuccess } = useMessage();
  const formRef = ref();
  const enablePopoverVisible = ref(false);

  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    description: '',
    enabled: false,
    // 与工具管理一致：默认未选择，展示「请选择」占位
    visibility_type: 'scenes_and_systems',
    scene_ids: [],
    system_ids: [],
    scene_param_overrides: {},
  });

  // 参数列表：由 share_detail 填充（与 BKVision 工具第一步一致）
  const inputVariables = ref<ToolFormData['config']['input_variable']>([]);
  const allSceneList = ref<Array<{ id: number; name: string }>>([]);
  const allSystemList = ref<Array<{ id: string; name: string }>>([]);
  /** 可见范围参数区加载中（避免覆盖配置回显前空态闪屏） */
  const visibilityParamLoading = ref(false);
  let visibilityParamLoadSeq = 0;

  const runVisibilityParamLoad = async (task: () => Promise<void>) => {
    visibilityParamLoadSeq += 1;
    const seq = visibilityParamLoadSeq;
    visibilityParamLoading.value = true;
    try {
      await task();
    } finally {
      if (seq === visibilityParamLoadSeq) {
        visibilityParamLoading.value = false;
      }
    }
  };

  /**
   * 解析 share_detail 响应为覆盖参数选项
   * service 已解包外层 data，结构为：
   * { data: { panels, variables, ... }, filters, constants }
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

    // 1) 交互组件：filters key ↔ panels.uid，默认值取 filters
    filterUids.forEach((uid) => {
      const com = panels.find((p: any) => p.uid === uid);
      if (!com) return;
      const item = getInputVariableConfig(false, com, filters[com.uid]);
      if (!item.raw_name || usedKeys.has(item.raw_name)) return;
      usedKeys.add(item.raw_name);
      result.push(item);
    });

    // 2) 变量：data.variables（跳过 build_in），默认值取 constants[flag]
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

    // 3) 兜底：variables 为空时从 constants 取自定义变量（跳过 bkv_ 内置）
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

  const loadShareDetailVariables = async (shareUid: string) => {
    if (!shareUid) {
      inputVariables.value = [];
      return;
    }
    try {
      const res = await ToolManageService.fetchReportLists({ share_uid: shareUid });
      inputVariables.value = buildInputVariablesFromShareDetail(res);
      reconcileParamOverrides();
    } catch (e) {
      console.error('获取报表参数列表失败:', e);
      inputVariables.value = [];
    }
  };

  const visibilityFormData = computed(() => ({
    name: formData.value.name,
    tags: [],
    description: formData.value.description,
    tool_type: '',
    updated_at: '',
    updated_by: '',
    is_bkvision: true,
    updated_time: null,
    data_search_config_type: '',
    visibility_type: formData.value.visibility_type,
    scene_ids: formData.value.scene_ids,
    system_ids: formData.value.system_ids,
    scene_param_overrides: formData.value.scene_param_overrides || {},
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

  const paramConfigFormData = computed(() => visibilityFormData.value);

  const reconcileParamOverrides = () => {
    formData.value.scene_param_overrides = reconcileSceneParamOverrides(
      formData.value.scene_param_overrides,
      inputVariables.value,
      formData.value.visibility_type,
      formData.value.scene_ids || [],
      formData.value.system_ids || [],
      allSceneList.value,
      allSystemList.value,
    );
  };

  const hasVisibleRangeSelection = computed(() => {
    const visibilityType = formData.value.visibility_type;
    if (visibilityType === 'all_visible'
      || visibilityType === 'all_scenes'
      || visibilityType === 'all_systems') {
      return false;
    }
    return (formData.value.scene_ids?.length ?? 0) > 0 || (formData.value.system_ids?.length ?? 0) > 0;
  });

  // 无参数时不展示覆盖参数配置（避免「无数据」空态）
  const showParamOverrideConfig = computed(() => !visibilityParamLoading.value
    && hasVisibleRangeSelection.value
    && inputVariables.value.length > 0);

  const selectedSceneItems = computed(() => {
    if (!formData.value.scene_ids || formData.value.visibility_type === 'all_visible') return [];
    if (formData.value.visibility_type === 'all_scenes') return [];
    const sceneMap = new Map(allSceneList.value.map(scene => [scene.id, scene]));
    return formData.value.scene_ids
      .map(sceneId => sceneMap.get(sceneId))
      .filter((scene): scene is { id: number; name: string } => Boolean(scene));
  });

  const selectedSystemItems = computed(() => {
    if (!formData.value.system_ids || formData.value.visibility_type === 'all_visible') return [];
    if (formData.value.visibility_type === 'all_systems') return [];
    const systemMap = new Map(allSystemList.value.map(system => [system.id, system]));
    return formData.value.system_ids
      .map(systemId => systemMap.get(systemId))
      .filter((system): system is { id: string; name: string } => Boolean(system));
  });

  const loadSceneListForParams = async () => {
    try {
      const data = await SceneManageService.fetchSceneAll({ status: 'enabled' });
      allSceneList.value = (data || []).map((item: { scene_id: number; name: string }) => ({
        id: item.scene_id,
        name: item.name,
      }));
    } catch {
      allSceneList.value = [];
    }
  };

  const loadSystemListForParams = async () => {
    try {
      const data = await MetaManageService.fetchSystemWithAction({
        audit_status__in: 'accessed',
        namespace: 'default',
      });
      allSystemList.value = (data || []).map((item: any) => ({
        id: String(item.system_id || item.id),
        name: item.name,
      }));
    } catch {
      allSystemList.value = [];
    }
  };

  const formRules = {
    bkvisionReport: [
      {
        required: true,
        message: t('请选择关联 BKVision 报表'),
        trigger: 'blur',
      },
    ],
    name: [
      {
        required: true,
        message: t('请输入报表名称'),
        trigger: 'blur',
      },
    ],
  };

  const handleNameChange = () => {
    formRef.value?.validate('name');
  };

  const handleVisibleRangeChange = (value: ToolFormData) => {
    formData.value = {
      ...formData.value,
      visibility_type: (value.visibility_type || 'scenes_and_systems') as PanelVisibilityType,
      scene_ids: value.scene_ids || [],
      system_ids: value.system_ids || [],
    };
    reconcileParamOverrides();
  };

  const handleParamOverridesChange = (value: Record<string, SceneParamOverride>) => {
    formData.value.scene_param_overrides = value;
  };

  /**
   * 通过报表详情接口按 scope 拉取默认值覆盖，组装为 scenes/systems 结构
   * GET /bkvision/api/v1/panel/{panel_id}/?scope_type=&scope_id=
   */
  const fetchDefaultValueOverridesByScopes = async (
    panelId: string,
    sceneIds: number[],
    systemIds: string[],
  ): Promise<DefaultValueOverrides> => {
    const result: DefaultValueOverrides = { scenes: {}, systems: {} };

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

  const loadEditParamOverrides = async (data: ReportFormData) => {
    const sceneIds = data.scene_ids || [];
    const systemIds = data.system_ids || [];
    const listOverrides = data.default_value_overrides;
    const hasListOverrides = listOverrides !== undefined && listOverrides !== null;

    let overrides: DefaultValueOverrides | undefined;

    if (hasListOverrides) {
      // 管理列表返回完整 default_value_overrides，编辑回显优先使用
      overrides = listOverrides;
    } else if (data.id && (sceneIds.length > 0 || systemIds.length > 0)) {
      // 列表未带回时，按 scope 调报表详情接口组装
      overrides = await fetchDefaultValueOverridesByScopes(data.id, sceneIds, systemIds);
    }

    formData.value.scene_param_overrides = parseDefaultValueOverrides(
      overrides,
      allSceneList.value,
      allSystemList.value,
    );
    // 需在 inputVariables 已就绪后调用，避免覆盖参数被空列表过滤掉
    reconcileParamOverrides();
  };

  const fillEditFormData = (data: ReportFormData) => {
    const visibilityData = applyVisibilityToFormData({
      visibility_type: data.visibility_type,
      scene_ids: data.scene_ids,
      system_ids: data.system_ids,
    }) || {
      visibility_type: 'all_visible' as PanelVisibilityType,
      scene_ids: [],
      system_ids: [],
    };
    formData.value = {
      id: data.id,
      bkvisionReport: data.bkvisionReport || '',
      name: data.name,
      description: data.description === '--' ? '' : (data.description || ''),
      status: data.status || 'unpublished',
      enabled: (data.status ?? 'unpublished') === 'published',
      visibility_type: (visibilityData.visibility_type || 'all_visible') as PanelVisibilityType,
      scene_ids: visibilityData.scene_ids,
      system_ids: visibilityData.system_ids,
      scene_param_overrides: {},
      default_value_overrides: data.default_value_overrides,
    };
  };

  const resetCreateFormData = () => {
    formData.value = {
      bkvisionReport: '',
      name: '',
      description: '',
      enabled: false,
      visibility_type: 'scenes_and_systems',
      scene_ids: [],
      system_ids: [],
      scene_param_overrides: {},
    };
    inputVariables.value = [];
  };

  watch(() => props.isShow, async (val) => {
    if (val) {
      enablePopoverVisible.value = false;
      // 仅当编辑态存在具体可见范围时需要回显覆盖参数，此时展示 loading
      const needParamLoad = !!(props.editData
        && ((props.editData.scene_ids?.length || 0) > 0
          || (props.editData.system_ids?.length || 0) > 0));

      const bootstrapForm = async () => {
        await Promise.all([
          loadSceneListForParams(),
          loadSystemListForParams(),
        ]);
        if (props.editData) {
          fillEditFormData(props.editData);
        } else {
          resetCreateFormData();
        }
        // 先加载参数列表，再回显覆盖配置（reconcile 依赖 inputVariables）
        if (formData.value.bkvisionReport) {
          await loadShareDetailVariables(formData.value.bkvisionReport);
        } else {
          inputVariables.value = [];
        }
        if (props.editData) {
          await loadEditParamOverrides(props.editData);
        }
      };

      if (needParamLoad) {
        await runVisibilityParamLoad(bootstrapForm);
      } else {
        visibilityParamLoadSeq += 1;
        visibilityParamLoading.value = false;
        await bootstrapForm();
      }
      nextTick(() => {
        formRef.value?.clearValidate();
        setTimeout(() => {
          formRef.value?.clearValidate();
        }, 100);
      });
    } else {
      visibilityParamLoadSeq += 1;
      visibilityParamLoading.value = false;
    }
  });

  watch(() => props.editData, async (data) => {
    if (props.isShow && data) {
      const needParamLoad = (data.scene_ids?.length || 0) > 0
        || (data.system_ids?.length || 0) > 0;
      const bootstrapEdit = async () => {
        fillEditFormData(data);
        if (data.bkvisionReport) {
          await loadShareDetailVariables(data.bkvisionReport);
        } else {
          inputVariables.value = [];
        }
        await loadEditParamOverrides(data);
      };
      if (needParamLoad) {
        await runVisibilityParamLoad(bootstrapEdit);
      } else {
        visibilityParamLoadSeq += 1;
        visibilityParamLoading.value = false;
        await bootstrapEdit();
      }
    } else if (props.isShow && !data) {
      resetCreateFormData();
      visibilityParamLoadSeq += 1;
      visibilityParamLoading.value = false;
    }
  });

  const handleStatusBeforeChange = (newValue: boolean) => {
    if (newValue) {
      enablePopoverVisible.value = true;
      return false;
    }
    // 复用列表停用弹窗；侧滑内抬高层级，避免无法关闭
    showReportDisableConfirm({
      name: formData.value.name,
      t,
      aboveSideslider: true,
      onConfirm: () => {
        formData.value.enabled = false;
      },
    });
    return false;
  };

  const handleConfirmEnable = () => {
    formData.value.enabled = true;
    enablePopoverVisible.value = false;
  };

  const handleReportChange = async (value: string) => {
    if (value) {
      formData.value.bkvisionReport = value;
      for (const group of chartLists.value) {
        if (group.share) {
          const report = group.share.find(item => item.uid === value);
          if (report?.name) {
            formData.value.name = report.name;
            break;
          }
        }
      }
      // 切换报表后重置覆盖配置，再拉取新参数列表
      formData.value.scene_param_overrides = {};
      if (hasVisibleRangeSelection.value) {
        await runVisibilityParamLoad(async () => {
          await loadShareDetailVariables(value);
        });
      } else {
        await loadShareDetailVariables(value);
      }
    } else {
      formData.value.bkvisionReport = '';
      formData.value.name = '';
      formData.value.scene_param_overrides = {};
      inputVariables.value = [];
      visibilityParamLoading.value = false;
    }
    formRef.value?.validate('bkvisionReport');
    formRef.value?.validate('name');
  };

  const handlePreviewReport = async (item: { uid: string; name: string }) => {
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      const res = await fetchReportDetail({
        share_uid: item.uid,
      });
      if (res && res.data?.dashboard_uid) {
        let spaceUid = '';
        for (const group of chartLists.value) {
          if (group.share?.find(i => i.uid === item.uid)) {
            spaceUid = group.uid;
            break;
          }
        }
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

  const handlePreview = async () => {
    if (!formData.value.bkvisionReport) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      const res = await fetchReportDetail({
        share_uid: formData.value.bkvisionReport,
      });
      if (res && res.data?.dashboard_uid) {
        let spaceUid = '';
        for (const group of chartLists.value) {
          const report = group.share?.find(item => item.uid === formData.value.bkvisionReport);
          if (report) {
            spaceUid = group.uid;
            break;
          }
        }
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  const {
    run: createPlatformPanel,
    loading: createLoading,
  } = useRequest(ReportConfigService.createPlatformPanel, {
    defaultValue: null,
    onSuccess: (res: any) => {
      messageSuccess(t('创建成功'));
      emit('success', res?.id);
      handleClose();
    },
  });

  const {
    run: updatePlatformPanel,
    loading: updateLoading,
  } = useRequest(ReportConfigService.updatePlatformPanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('更新成功'));
      emit('success');
      handleClose();
    },
  });

  const submitLoading = computed(() => createLoading.value || updateLoading.value);

  const buildSubmitPayload = () => {
    const payload: Record<string, any> = {
      vision_id: formData.value.bkvisionReport,
      name: formData.value.name,
      status: formData.value.enabled ? 'published' : 'unpublished',
      description: formData.value.description || undefined,
    };

    if (shouldSubmitVisibilityPayload(formData.value)) {
      payload.visibility = buildVisibilityPayload(formData.value);
    }

    // 显式传覆盖配置：有可见范围选择时按表单组装，否则传 {} 以清空
    payload.default_value_overrides = hasVisibleRangeSelection.value
      ? buildDefaultValueOverrides(formData.value.scene_param_overrides)
      : { scenes: {}, systems: {} };

    return payload;
  };

  const handleSubmit = async () => {
    formRef.value?.validate().then(() => {
      const payload = buildSubmitPayload();

      if (isEditMode.value && formData.value.id) {
        updatePlatformPanel({
          panel_id: formData.value.id,
          ...payload,
        });
      } else {
        createPlatformPanel(payload);
      }
    });
  };

  const handleSliderClosed = () => {
    emit('update:isShow', false);
  };

  const handleClose = () => {
    emit('update:isShow', false);
    emit('cancel');
  };
</script>

<style lang="postcss" scoped>
.report-create-content {
  padding: 24px 40px;
}

.ml4 {
  margin-left: 4px;
}

.mr8 {
  margin-right: 8px;
}

.bkvision-select-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;

  :deep(.bk-select) {
    flex: 1;
  }

  .preview-btn {
    flex-shrink: 0;
    color: #3a84ff;

    &:hover {
      color: #699df4;
    }
  }
}

.report-option-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .option-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .preview-icon {
    margin-left: 8px;
    color: #3a84ff;
    cursor: pointer;

    &:hover {
      color: #699df4;
    }
  }
}

.status-field {
  display: flex;
  align-items: center;
  margin-bottom: 8px;

  .status-label {
    margin-left: 8px;
    font-size: 12px;
    color: #63656e;
  }
}

.report-enable-popover {
  width: 280px;
  padding: 4px 0;

  .report-enable-popover-title {
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 700;
    color: #313238;
  }

  .report-enable-popover-text {
    margin-bottom: 16px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }
}

.report-status-popover-actions {
  display: flex;
  justify-content: flex-end;
}

.report-create-form {
  :deep(.bk-form-label) {
    font-size: 12px;
  }
}

.visibility-param-loading {
  min-height: 120px;
  margin-top: 16px;
  margin-bottom: 24px;
}

.visibility-param-config {
  margin-bottom: 24px;
}

.visibility-param-loading-placeholder {
  min-height: 120px;
}
</style>

<style lang="postcss">
  .report-create-sideslider .bk-modal-content {
    scrollbar-width: thin;
    scrollbar-color: #c4c6cc transparent;
  }

  .report-create-sideslider .bk-modal-content::-webkit-scrollbar {
    width: 6px;
    appearance: none;
  }

  .report-create-sideslider .bk-modal-content::-webkit-scrollbar-track {
    background: transparent;
  }

  .report-create-sideslider .bk-modal-content::-webkit-scrollbar-thumb {
    background-color: #c4c6cc;
    border-radius: 3px;
  }

  .report-create-sideslider .bk-modal-content::-webkit-scrollbar-thumb:hover {
    background-color: #979ba5;
  }

  /* InfoBox 未透传 zIndex，侧滑 z-index=9999 时需用样式抬高层级，保证可关闭 */
  .bk-infobox.report-disable-infobox-above-sideslider,
  .bk-infobox.report-disable-infobox-above-sideslider .bk-modal-wrapper,
  .bk-infobox.report-disable-infobox-above-sideslider .bk-modal-mask {
    z-index: 10060 !important;
  }

  /* +n hover tips：v-bk-tooltips 默认 z-index≈8000，低于侧滑 9999 */
  .bk-select-tooltips,
  .bk-popper.visible-range-overflow-tips {
    z-index: 10060 !important;
  }
</style>
