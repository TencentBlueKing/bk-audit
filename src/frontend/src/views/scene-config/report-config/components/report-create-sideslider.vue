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
    ext-cls="scene-report-create-sideslider"
    :is-show="isShow"
    :quick-close="false"
    show-mask
    :title="isEditMode ? t('编辑报表') : t('新建报表')"
    :width="680"
    :z-index="9999"
    @closed="handleSliderClosed">
    <template #default>
      <div class="report-create-content">
        <!-- 基本信息 -->
        <div class="report-card">
          <div class="report-card-title">
            {{ t('基本信息') }}
          </div>
          <div class="report-card-body">
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
                      zIndex: 9999
                    }"
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

              <!-- 所属分组 -->
              <bk-form-item
                :label="t('所属分组')"
                property="groupId"
                required>
                <bk-select
                  v-model="formData.groupId"
                  :clearable="false"
                  :placeholder="t('请选择')"
                  :popover-options="{
                    boundary: 'parent',
                    zIndex: 9999
                  }"
                  @change="handleGroupChange">
                  <bk-option
                    v-for="group in groupList"
                    :key="group.id"
                    :label="group.name"
                    :value="group.id" />
                  <template #extension>
                    <div
                      class="create-group-btn"
                      @click="handleCreateGroup">
                      <audit-icon type="plus-circle" />
                      {{ t('新建分组') }}
                    </div>
                  </template>
                </bk-select>
              </bk-form-item>

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
                  <bk-switcher
                    v-model="formData.enabled"
                    size="small"
                    theme="primary" />
                  <span class="status-label">{{ formData.enabled ? t('启用') : t('停用') }}</span>
                </div>
              </bk-form-item>
            </bk-form>
          </div>
        </div>

        <!-- 参数配置 -->
        <bk-loading
          :loading="paramLoading"
          size="small">
          <bkvision-param-config
            ref="paramConfigRef"
            :has-report="!!formData.bkvisionReport"
            :input-variables="inputVariables"
            :report-lists-panels="reportListsPanels" />
        </bk-loading>
      </div>
    </template>
    <template #footer>
      <div class="report-footer-actions">
        <bk-button
          class="footer-btn confirm-btn"
          :loading="submitLoading"
          theme="primary"
          @click="handleSubmit">
          {{ t('确定') }}
        </bk-button>
        <bk-button
          class="footer-btn cancel-btn"
          @click="handleClose">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang='ts'>
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import BkvisionParamConfig, {
    type InputVariableItem,
  } from './bkvision-param-config.vue';

  export interface ReportGroup {
    id: number;
    name: string;
  }

  export interface ReportFormData {
    id?: string;
    bkvisionReport: string;
    name: string;
    groupId: number | null;
    description: string;
    status?: 'published' | 'unpublished';
    enabled: boolean;
    /**
     * 场景报表参数覆盖（新协议）：
     * { default: { [raw_name]: value }, use_bkvision_default: { [raw_name]: boolean } }
     * 兼容列表仍回旧结构 default_value_overrides.scenes[sceneId]
     */
    default_value_override?: {
      default?: Record<string, any>;
      use_bkvision_default?: Record<string, boolean>;
    };
    /** @deprecated 旧列表字段，回显兼容用 */
    default_value_overrides?: {
      default?: Record<string, any>;
      scenes?: Record<string, Record<string, any>>;
      systems?: Record<string, Record<string, any>>;
      use_bkvision_default?: Record<string, boolean>;
    };
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
    groupList?: ReportGroup[];
    defaultGroupId?: number | null;
    defaultGroupName?: string | null;
    editData?: ReportFormData | null;
    chartLists?: ChartListModel[];
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
    (e: 'success', panelId?: string): void;
    (e: 'create-group'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    groupList: () => [],
    defaultGroupId: null,
    defaultGroupName: null,
    editData: null,
    chartLists: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 是否编辑模式
  const isEditMode = computed(() => !!props.editData);

  // 图表列表数据（从 props 获取）
  const chartLists = computed(() => props.chartLists || []);

  // 分组后的图表列表（用于下拉框展示）
  const chartGroupedLists = computed(() => chartLists.value);

  const { messageSuccess } = useMessage();

  // 表单引用
  const formRef = ref();
  const paramConfigRef = ref<InstanceType<typeof BkvisionParamConfig>>();

  // 表单数据
  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    groupId: null,
    description: '',
    enabled: false,
  });

  // BKVision 参数（交互组件 + 变量）
  const inputVariables = ref<InputVariableItem[]>([]);
  const reportListsPanels = ref<Array<Record<string, any>>>([]);
  const paramLoading = ref(false);
  let paramLoadSeq = 0;

  /**
   * 解析 share_detail 响应为 input_variable（对齐 BKVision 工具拉取逻辑）
   * service 已解包外层 data，结构为：
   * { data: { panels, variables, ... }, filters, constants }
   */
  const buildInputVariablesFromShareDetail = (res: any): InputVariableItem[] => {
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
    ): InputVariableItem => ({
      raw_name: (isVariables ? com?.flag : com?.chartConfig?.flag) || '',
      display_name: (isVariables ? com?.description : com.title) || '',
      description: com.uid || '',
      field_category: isVariables ? (com.type || 'variable') : (com.type || ''),
      required: true,
      is_default_value: false,
      raw_default_value: defaultValue || '',
      default_value: defaultValue || '',
      choices: [],
    });

    const result: InputVariableItem[] = [];
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

  const clearParamState = () => {
    inputVariables.value = [];
    reportListsPanels.value = [];
  };

  const loadShareDetailVariables = async (shareUid: string) => {
    if (!shareUid) {
      clearParamState();
      return;
    }
    paramLoadSeq += 1;
    const seq = paramLoadSeq;
    paramLoading.value = true;
    try {
      const res = await ToolManageService.fetchReportLists({ share_uid: shareUid });
      if (seq !== paramLoadSeq) return;
      reportListsPanels.value = Array.isArray(res?.data?.panels) ? res.data.panels : [];
      inputVariables.value = buildInputVariablesFromShareDetail(res);
    } catch (e) {
      console.error('获取报表参数列表失败:', e);
      if (seq === paramLoadSeq) {
        clearParamState();
      }
    } finally {
      if (seq === paramLoadSeq) {
        paramLoading.value = false;
      }
    }
  };

  /**
   * 将参数配置转为场景报表协议中的 default_value_overrides
   * 协议：{ default, use_bkvision_default }（scene_id 已在请求体，不再套 scenes）
   * default：仅提交未勾选「使用默认值」的自定义值
   * use_bkvision_default：各参数复选框勾选态
   */
  const buildSceneDefaultValueOverride = () => {
    const fields = paramConfigRef.value?.getFields?.() || inputVariables.value;
    const overrides: Record<string, any> = {};
    const useBkvisionDefault: Record<string, boolean> = {};
    fields.forEach((item) => {
      if (!item.raw_name) return;
      useBkvisionDefault[item.raw_name] = !!item.is_default_value;
      if (item.is_default_value) return;
      const value = item.default_value;
      const isEmpty = value === '' || value === undefined || value === null
        || (Array.isArray(value) && value.length === 0);
      if (isEmpty) return;
      overrides[item.raw_name] = value;
    });
    return {
      default: overrides,
      use_bkvision_default: useBkvisionDefault,
    };
  };

  /** 从列表/详情多种回包结构中解析出参数 map */
  const resolveSavedParamMap = (saved?: ReportFormData['default_value_override']
    | ReportFormData['default_value_overrides']
    | Record<string, any>
    | null): Record<string, any> => {
    if (!saved || typeof saved !== 'object') {
      return {};
    }
    // 新协议：{ default: { ... } }
    if (
      'default' in saved
      && saved.default
      && typeof saved.default === 'object'
      && !Array.isArray(saved.default)
    ) {
      return { ...saved.default };
    }
    // 旧协议：{ scenes: { [sceneId]: {...} }, systems: {} }
    if ('scenes' in saved && saved.scenes && typeof saved.scenes === 'object') {
      const sceneId = String(getSceneSystemParams().scope_id || '');
      return { ...((saved.scenes as Record<string, Record<string, any>>)[sceneId] || {}) };
    }
    // 扁平 map（列表/详情直接回 { [raw_name]: value }）
    const reserved = new Set(['default', 'scenes', 'systems', 'use_bkvision_default']);
    const flatEntries = Object.entries(saved).filter(([key]) => !reserved.has(key));
    if (flatEntries.length) {
      return Object.fromEntries(flatEntries);
    }
    return {};
  };

  /** 解析列表/详情带回的 use_bkvision_default（复选框勾选态） */
  const resolveUseBkvisionDefaultMap = (saved?: ReportFormData['default_value_override']
    | ReportFormData['default_value_overrides']
    | Record<string, any>
    | null): Record<string, boolean> | null => {
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) {
      return null;
    }
    const map = (saved as { use_bkvision_default?: unknown }).use_bkvision_default;
    if (!map || typeof map !== 'object' || Array.isArray(map)) {
      return null;
    }
    return map as Record<string, boolean>;
  };

  const isNonEmptyPlainObject = (value: unknown): value is Record<string, any> => (
    !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0
  );

  /** 是否明确带回了 default 覆盖层（含空 {}）；旧数据无此键时不应误勾「使用默认值」 */
  const hasExplicitDefaultLayer = (saved: unknown): boolean => (
    !!saved
    && typeof saved === 'object'
    && !Array.isArray(saved)
    && Object.prototype.hasOwnProperty.call(saved, 'default')
    && !!(saved as Record<string, any>).default
    && typeof (saved as Record<string, any>).default === 'object'
    && !Array.isArray((saved as Record<string, any>).default)
  );

  /** 组装回填用的覆盖对象（保留 use_bkvision_default） */
  const buildOverridePayload = (
    paramMap: Record<string, any>,
    useBkvisionDefault?: Record<string, boolean> | null,
  ): ReportFormData['default_value_override'] => ({
    default: paramMap,
    ...(useBkvisionDefault ? { use_bkvision_default: useBkvisionDefault } : {}),
  });

  /** 用已保存的覆盖配置回填到 inputVariables（编辑态）
   * - 优先用 use_bkvision_default 决定复选框勾选态
   * - 无该字段时回退：出现在覆盖 map → 取消勾选；未出现 → 勾选并还原 BKVision 原始默认值
   * - saved 为空/undefined：不改动（避免误把全部勾选上）
   */
  const applySavedOverridesToInputVariables = (saved?: ReportFormData['default_value_override'] | ReportFormData['default_value_overrides'] | null) => {
    if (saved === null || saved === undefined || !inputVariables.value.length) return;
    const paramMap = resolveSavedParamMap(saved);
    const useBkvisionDefaultMap = resolveUseBkvisionDefaultMap(saved);
    const hasUseFlag = !!useBkvisionDefaultMap;

    inputVariables.value = inputVariables.value.map((item) => {
      if (hasUseFlag && item.raw_name in useBkvisionDefaultMap!) {
        const isDefault = !!useBkvisionDefaultMap![item.raw_name];
        if (isDefault) {
          return {
            ...item,
            is_default_value: true,
            default_value: item.raw_default_value ?? '',
          };
        }
        return {
          ...item,
          is_default_value: false,
          default_value: item.raw_name in paramMap
            ? paramMap[item.raw_name]
            : (item.default_value ?? ''),
        };
      }
      if (item.raw_name in paramMap) {
        return {
          ...item,
          is_default_value: false,
          default_value: paramMap[item.raw_name],
        };
      }
      return {
        ...item,
        is_default_value: true,
        default_value: item.raw_default_value ?? '',
      };
    });
  };

  /**
   * 编辑回显：优先列表带回的覆盖 / use_bkvision_default；否则拉详情。
   * 仅「明确存在 default 层」或带回 use_bkvision_default 时回填勾选态；
   * 旧报表 {} / 仅有 scenes·systems 时不回填勾选态。
   */
  const resolveEditOverrides = async (data: ReportFormData): Promise<ReportFormData['default_value_override'] | undefined> => {
    const listSources = [data.default_value_override, data.default_value_overrides];
    for (const source of listSources) {
      const paramMap = resolveSavedParamMap(source);
      const useFlag = resolveUseBkvisionDefaultMap(source);
      if (Object.keys(paramMap).length || useFlag) {
        return buildOverridePayload(paramMap, useFlag);
      }
      // 列表明确带回 default 层且内容为空（{ default: {} }）→ 全部使用 BKVision 默认值
      if (hasExplicitDefaultLayer(source)) {
        return buildOverridePayload({}, useFlag);
      }
    }

    if (!data.id) return undefined;
    try {
      const scopeId = String(getSceneSystemParams().scope_id || '');
      const detail = await ReportConfigService.fetchPanelDetail({
        panel_id: data.id,
        scope_type: 'scene',
        scope_id: scopeId,
      });
      const override = detail?.default_value_override;
      if (!isNonEmptyPlainObject(override)) {
        return undefined;
      }
      const useFlag = resolveUseBkvisionDefaultMap(override);
      // 明确带回 default 层（含空 {}）或 use_bkvision_default → 按覆盖回显
      if (hasExplicitDefaultLayer(override) || useFlag) {
        return buildOverridePayload(resolveSavedParamMap(override), useFlag);
      }
      const paramMap = resolveSavedParamMap(override);
      if (!Object.keys(paramMap).length) {
        return undefined;
      }
      return buildOverridePayload(paramMap, useFlag);
    } catch (e) {
      console.error('获取报表参数覆盖失败:', e);
      return undefined;
    }
  };

  let editBootstrapSeq = 0;

  /** 编辑态统一引导：避免 isShow / editData 双 watch 竞态导致覆盖未回填 */
  const bootstrapEditForm = async (data: ReportFormData) => {
    editBootstrapSeq += 1;
    const seq = editBootstrapSeq;
    fillEditFormData(data);
    if (!data.bkvisionReport) {
      clearParamState();
      return;
    }
    await loadShareDetailVariables(data.bkvisionReport);
    if (seq !== editBootstrapSeq) return;
    const overrides = await resolveEditOverrides(data);
    if (seq !== editBootstrapSeq) return;
    applySavedOverridesToInputVariables(overrides);
  };

  // 新建模式，重置表单
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
    groupId: [
      {
        required: true,
        message: t('请选择所属分组'),
        trigger: 'blur',
      },
    ],
  };
  const handleNameChange = () => {
    formRef.value?.validate('name');
  };
  const handleGroupChange = () => {
    formRef.value?.validate('groupId');
  };

  // 新建分组
  const handleCreateGroup = () => {
    emit('create-group');
  };
  // 填充编辑数据的通用逻辑
  const fillEditFormData = (data: ReportFormData) => {
    formData.value = {
      id: data.id,
      bkvisionReport: data.bkvisionReport || '',
      name: data.name,
      groupId: data.groupId ?? null,
      description: data.description === '--' ? '' : (data.description || ''),
      status: data.status || 'unpublished',
      enabled: (data.status ?? 'unpublished') === 'published',
      default_value_override: data.default_value_override,
      default_value_overrides: data.default_value_overrides,
    };
  };

  // 重置新建模式表单
  const resetCreateFormData = () => {
    let defaultGroupIdValue = props.defaultGroupId ?? null;
    if (props.defaultGroupName) {
      const matchedGroup = props.groupList.find(g => g.name === props.defaultGroupName);
      if (matchedGroup) {
        defaultGroupIdValue = matchedGroup.id;
      }
    }
    formData.value = {
      bkvisionReport: '',
      name: '',
      groupId: defaultGroupIdValue,
      description: '',
      enabled: false,
    };
    clearParamState();
  };

  // 监听显示状态，重置/填充表单
  watch(() => props.isShow, async (val) => {
    if (val) {
      if (props.editData) {
        await bootstrapEditForm(props.editData);
      } else {
        editBootstrapSeq += 1;
        resetCreateFormData();
      }
      // 打开时清除校验状态，避免立即显示错误提示
      nextTick(() => {
        formRef.value?.clearValidate();
        // 再次确保清除（解决某些情况下 clearValidate 不生效的问题）
        setTimeout(() => {
          formRef.value?.clearValidate();
        }, 100);
      });
    } else {
      editBootstrapSeq += 1;
      paramLoadSeq += 1;
      paramLoading.value = false;
    }
  });

  // 监听 editData 变化（双重保障，解决 isShow 与 editData 更新时序竞态问题）
  watch(() => props.editData, async (data) => {
    if (props.isShow && data) {
      await bootstrapEditForm(data);
    } else if (props.isShow && !data) {
      editBootstrapSeq += 1;
      resetCreateFormData();
    }
  });

  // 监听 defaultGroupId 变化（新建分组成功后自动选中新建的分组）
  watch(() => props.defaultGroupId, (newId) => {
    if (props.isShow && newId !== null && !props.editData) {
      formData.value.groupId = newId;
    }
  });

  // 报表选择变化处理
  const handleReportChange = async (value: string) => {
    if (value) {
      formData.value.bkvisionReport = value;
      // 从 chartLists 中查找报表名称并自动填充
      for (const group of chartLists.value) {
        if (group.share) {
          const report = group.share.find(item => item.uid === value);
          if (report?.name) {
            formData.value.name = report.name;
            break;
          }
        }
      }
      await loadShareDetailVariables(value);
    } else {
      formData.value.bkvisionReport = '';
      formData.value.name = '';
      clearParamState();
    }
    formRef.value?.validate('bkvisionReport');
    formRef.value?.validate('name');
  };

  // 预览报表（点击选项右侧图标）
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

  // 获取配置数据（用于获取 BKVision URL）
  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 获取报表详情（用于获取 dashboard_uid）
  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

  // 预览报表
  const handlePreview = async () => {
    if (!formData.value.bkvisionReport) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      // 先调用接口获取 dashboard_uid
      const res = await fetchReportDetail({
        share_uid: formData.value.bkvisionReport,
      });
      if (res && res.data?.dashboard_uid) {
        // 从 chartLists 中查找空间 uid
        let spaceUid = '';
        for (const group of chartLists.value) {
          const report = group.share?.find(item => item.uid === formData.value.bkvisionReport);
          if (report) {
            spaceUid = group.uid;
            break;
          }
        }
        // 构建跳转链接：baseUrl#/spaceUid/dashboards/detail/root/dashboardUid
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  // 创建 Panel
  const {
    run: createPanel,
    loading: createLoading,
  } = useRequest(ReportConfigService.createPanel, {
    defaultValue: null,
    onSuccess: (res: any) => {
      messageSuccess(t('创建成功'));
      emit('success', res?.id); // 通知父组件刷新列表，并传递新建报表ID用于高亮
      handleClose();
    },
  });

  // 更新 Panel
  const {
    run: updatePanel,
    loading: updateLoading,
  } = useRequest(ReportConfigService.updatePanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('更新成功'));
      emit('success'); // 通知父组件刷新列表
      handleClose();
    },
  });

  // 提交 loading
  const submitLoading = computed(() => createLoading.value || updateLoading.value);

  // 提交（字段对齐 POST /bkvision/api/v1/panel/scene/ 协议，不传 input_variable）
  const handleSubmit = async () => {
    formRef.value?.validate().then(() => {
      const selectedGroup = props.groupList.find(g => g.id === formData.value.groupId);
      const groupId = Number(selectedGroup?.id);
      const sceneId = Number(getSceneSystemParams().scope_id);
      const visionId = formData.value.bkvisionReport;
      const defaultValueOverride = buildSceneDefaultValueOverride();

      if (isEditMode.value && formData.value.id) {
        updatePanel({
          id: formData.value.id,
          scene_id: sceneId,
          group_id: groupId,
          panel_id: formData.value.id,
          vision_id: visionId,
          name: formData.value.name,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description || undefined,
          default_value_overrides: defaultValueOverride,
        });
      } else {
        createPanel({
          vision_id: visionId,
          name: formData.value.name,
          group_id: groupId,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description || '',
          scene_id: sceneId,
          default_value_overrides: defaultValueOverride,
        });
      }
    });
  };

  // 侧边栏关闭（箭头/遮罩点击），仅关闭弹窗
  const handleSliderClosed = () => {
    emit('update:isShow', false);
  };

  // 取消按钮关闭，同时通知父组件
  const handleClose = () => {
    emit('update:isShow', false);
    emit('cancel');
  };
</script>

<style lang="postcss" scoped>
.report-create-content {
  min-height: 100%;
  padding: 16px 24px 24px;
  background: #f5f7fa;
}

.report-card {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 #00000029;
}

.report-card-title {
  display: flex;
  height: 52px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 600;
  color: #313238;
  align-items: center;
}

.report-card-body {
  padding: 0px 24px;
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

.create-group-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 40px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
  border-top: 1px solid #dcdee5;

  &:hover {
    background-color: #f5f7fa;
  }
}

.report-create-form {
  :deep(.bk-form-label) {
    font-size: 12px;
  }
}

.report-footer-actions {
  display: flex;
  gap: 8px;
}

.footer-btn {
  min-width: 88px;
}
</style>

<style lang="postcss">
/* ext-cls 挂在 .bk-modal 根节点；非 scoped 勿用 :deep()，否则选择器无效 */
.scene-report-create-sideslider {
  .bk-modal-body {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: #f5f7fa;
  }

  .bk-modal-content {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
    background: #f5f7fa;
  }

  .bk-modal-footer {
    flex: none;
    background: #fafbfd;
    box-shadow: 0 -1px 3px 0 rgb(0 0 0 / 4%);
  }

  .bk-sideslider-footer {
    height: 52px;
    margin-top: 0;
    background: #fafbfd;
  }
}
</style>
