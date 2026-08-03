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
    :is-show="isShow"
    :quick-close="false"
    show-mask
    :title="isEditMode ? t('编辑报表') : t('新建报表')"
    :width="640"
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
                  zIndex: 9999
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

          <bk-loading
            v-if="paramConfigLoading"
            class="param-config-loading"
            loading
            size="small">
            <div class="param-config-loading-placeholder" />
          </bk-loading>
          <report-param-config
            v-else-if="showParamConfig"
            v-model="inputVariables"
            :report-lists-panels="reportListsPanels" />

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
              style="flex: 1;"
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

  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import type {
    PanelDefaultValueOverrides,
  } from '@model/report-config/panel';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';
  import ReportParamConfig, {
    type ReportInputVariable,
  } from './report-param-config.vue';

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
    default_value_overrides?: PanelDefaultValueOverrides;
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

  // 表单数据
  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    groupId: null,
    description: '',
    enabled: false,
  });

  const currentScope = computed(() => getSceneSystemParams());
  const inputVariables = ref<ReportInputVariable[]>([]);
  const reportListsPanels = ref<Array<Record<string, any>>>([]);
  const paramConfigLoading = ref(false);
  let paramConfigLoadSeq = 0;

  const runParamConfigLoad = async (task: () => Promise<void>) => {
    paramConfigLoadSeq += 1;
    const seq = paramConfigLoadSeq;
    paramConfigLoading.value = true;
    try {
      await task();
    } finally {
      if (seq === paramConfigLoadSeq) {
        paramConfigLoading.value = false;
      }
    }
  };

  const buildInputVariablesFromShareDetail = (res: any): ReportInputVariable[] => {
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
    ): ReportInputVariable => ({
      raw_name: (isVariables ? com?.flag : com?.chartConfig?.flag) || '',
      display_name: (isVariables ? com?.description : com.title) || '',
      description: com.uid || '',
      field_category: isVariables ? 'variable' : (com.type || ''),
      required: true,
      is_default_value: false,
      raw_default_value: defaultValue || '',
      default_value: defaultValue || '',
      choices: [],
    });

    const result: ReportInputVariable[] = [];
    const usedKeys = new Set<string>();

    filterUids.forEach((uid) => {
      const com = panels.find((item: any) => item.uid === uid);
      if (!com) return;
      const inputItem = getInputVariableConfig(false, com, filters[com.uid]);
      if (!inputItem.raw_name || usedKeys.has(inputItem.raw_name)) return;
      usedKeys.add(inputItem.raw_name);
      result.push(inputItem);
    });

    variables.forEach((item: any) => {
      if (item.build_in) return;
      const defaultValue = constants[item.flag] ?? '';
      const inputItem = getInputVariableConfig(true, item, defaultValue);
      if (!inputItem.raw_name || usedKeys.has(inputItem.raw_name)) return;
      usedKeys.add(inputItem.raw_name);
      result.push(inputItem);
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

  /** 将 BKVision 参数配置转为当前 scope 的 default_value_overrides */
  const buildDefaultValueOverridesFromVariables = (variables: ReportInputVariable[]): PanelDefaultValueOverrides => {
    const paramValues: Record<string, any> = {};
    variables.forEach((item) => {
      if (item.is_default_value || !item.raw_name) return;
      const value = item.default_value;
      if (value === undefined || value === null || value === '') return;
      if (Array.isArray(value) && value.length === 0) return;
      paramValues[item.raw_name] = value;
    });

    const scopeType = currentScope.value.scope_type;
    const scopeId = currentScope.value.scope_id;
    if (!scopeId || !(scopeType === 'scene' || scopeType === 'system')) {
      return { scenes: {}, systems: {} };
    }

    if (!Object.keys(paramValues).length) {
      return { scenes: {}, systems: {} };
    }

    return scopeType === 'scene'
      ? { scenes: { [String(scopeId)]: paramValues }, systems: {} }
      : { scenes: {}, systems: { [String(scopeId)]: paramValues } };
  };

  /** 用已保存的覆盖值回填到 BKVision 参数（有覆盖 → 自定义；无覆盖 → 使用默认值） */
  const applyOverrideToVariables = (
    variables: ReportInputVariable[],
    overrideMap: Record<string, any> = {},
  ): ReportInputVariable[] => variables.map((item) => {
    if (item.raw_name in overrideMap) {
      return {
        ...item,
        is_default_value: false,
        default_value: overrideMap[item.raw_name],
      };
    }
    return {
      ...item,
      is_default_value: true,
      default_value: item.raw_default_value || '',
    };
  });

  const loadShareDetailVariables = async (shareUid: string) => {
    if (!shareUid) {
      inputVariables.value = [];
      reportListsPanels.value = [];
      return;
    }
    try {
      const res = await ToolManageService.fetchReportLists({ share_uid: shareUid });
      reportListsPanels.value = Array.isArray(res?.data?.panels) ? res.data.panels : [];
      inputVariables.value = buildInputVariablesFromShareDetail(res);
    } catch (e) {
      console.error('获取报表参数列表失败:', e);
      inputVariables.value = [];
      reportListsPanels.value = [];
    }
  };

  const showParamConfig = computed(() => !paramConfigLoading.value
    && inputVariables.value.length > 0);

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

  const loadEditParamOverrides = async (data: ReportFormData) => {
    if (!data.id || inputVariables.value.length === 0) {
      return;
    }

    const scopeType = currentScope.value.scope_type;
    const scopeId = currentScope.value.scope_id;
    if (!(scopeType === 'scene' || scopeType === 'system') || !scopeId) {
      return;
    }

    let overrideMap: Record<string, any> = {};
    const listOverrides = data.default_value_overrides;
    if (listOverrides) {
      overrideMap = scopeType === 'scene'
        ? (listOverrides.scenes?.[String(scopeId)] || {})
        : (listOverrides.systems?.[String(scopeId)] || {});
    } else {
      try {
        const detail = await ReportConfigService.fetchPanelDetail({
          panel_id: data.id,
          scope_type: scopeType,
          scope_id: String(scopeId),
        });
        overrideMap = detail?.default_value_override || {};
      } catch (e) {
        console.error('获取场景报表参数覆盖配置失败:', e);
      }
    }

    inputVariables.value = applyOverrideToVariables(inputVariables.value, overrideMap);
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
      description: data.description || '--',
      status: data.status || 'unpublished',
      enabled: (data.status ?? 'unpublished') === 'published',
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
    inputVariables.value = [];
    reportListsPanels.value = [];
  };

  // 监听显示状态，重置/填充表单
  watch(() => props.isShow, async (val) => {
    if (val) {
      const bootstrap = async () => {
        if (props.editData) {
          fillEditFormData(props.editData);
          if (formData.value.bkvisionReport) {
            await loadShareDetailVariables(formData.value.bkvisionReport);
          }
          await loadEditParamOverrides(props.editData);
        } else {
          resetCreateFormData();
        }
      };
      await runParamConfigLoad(bootstrap);
      // 打开时清除校验状态，避免立即显示错误提示
      nextTick(() => {
        formRef.value?.clearValidate();
        // 再次确保清除（解决某些情况下 clearValidate 不生效的问题）
        setTimeout(() => {
          formRef.value?.clearValidate();
        }, 100);
      });
    } else {
      paramConfigLoadSeq += 1;
      paramConfigLoading.value = false;
    }
  });

  // 监听 editData 变化（双重保障，解决 isShow 与 editData 更新时序竞态问题）
  watch(() => props.editData, async (data) => {
    if (props.isShow && data) {
      await runParamConfigLoad(async () => {
        fillEditFormData(data);
        if (data.bkvisionReport) {
          await loadShareDetailVariables(data.bkvisionReport);
        } else {
          inputVariables.value = [];
          reportListsPanels.value = [];
        }
        await loadEditParamOverrides(data);
      });
    } else if (props.isShow && !data) {
      resetCreateFormData();
      paramConfigLoadSeq += 1;
      paramConfigLoading.value = false;
    }
  });

  // 监听 defaultGroupId 变化（新建分组成功后自动选中新建的分组）
  watch(() => props.defaultGroupId, (newId) => {
    if (props.isShow && newId !== null && !props.editData) {
      formData.value.groupId = newId;
    }
  });

  // 监听 chartLists 加载完成，编辑模式下设置选择器的值
  // bkvisionReport 直接存储 uid，无需额外处理

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
      await runParamConfigLoad(async () => {
        await loadShareDetailVariables(value);
      });
    } else {
      formData.value.bkvisionReport = '';
      formData.value.name = '';
      inputVariables.value = [];
      reportListsPanels.value = [];
      paramConfigLoadSeq += 1;
      paramConfigLoading.value = false;
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

  // 提交
  const handleSubmit = async () => {
    formRef.value?.validate().then(() => {
      // 从 groupList 中查找选中分组的名称
      const selectedGroup = props.groupList.find(g => g.id === formData.value.groupId);
      const groupId = selectedGroup?.id || '';
      // 直接使用 bkvisionReport 作为 vision_id
      const visionId = formData.value.bkvisionReport;
      const defaultValueOverrides = buildDefaultValueOverridesFromVariables(inputVariables.value);

      if (isEditMode.value && formData.value.id) {
        // 编辑模式，调用 updatePanel API
        updatePanel({
          id: formData.value.id,
          scene_id: getSceneSystemParams().scope_id,
          group_id: typeof groupId === 'number' ? groupId : Number(groupId),
          panel_id: formData.value.id,
          vision_id: visionId,
          name: formData.value.name,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description || undefined,
          default_value_overrides: defaultValueOverrides,
        });
      } else {
        // 创建模式，调用 createPanel API
        createPanel({
          vision_id: visionId,
          name: formData.value.name,
          group_id: groupId,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description,
          scene_id: getSceneSystemParams().scope_id,
          default_value_overrides: defaultValueOverrides,
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
  padding: 24px 40px;
}

.ml4 {
  margin-left: 4px;
}

.mr4 {
  margin-right: 4px;
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

  .status-tip {
    display: flex;
    align-items: center;
    margin-right: 16px;
    font-size: 12px;
    color: #979ba5;
  }

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

.param-config-loading {
  min-height: 120px;
  margin-bottom: 24px;
}

.param-config-loading-placeholder {
  min-height: 120px;
}
</style>
