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
  <card-part-vue :title="t('工具类型')">
    <template #content>
      <bk-form-item
        :label="t('工具类型')"
        label-width="160"
        property="tool_type"
        required>
        <bk-radio-group v-model="formData.tool_type">
          <template
            v-for="(item, index) in toolTypeList"
            :key="index">
            <bk-radio
              :disabled="isEditMode"
              :label="item.id">
              <div style="display: flex; align-items: center; line-height: 16px;">
                <audit-icon
                  style=" margin-right: 5px;font-size: 16px;"
                  svg
                  :type="iconMap[item.id as keyof typeof iconMap]" />
                <span
                  v-bk-tooltips="{
                    disabled: !item.tips,
                    content: item.tips || '',
                  }"
                  :style="item.tips ? { 'border-bottom': '1px dashed #979ba5' } : {}">{{ item.name }}</span>
              </div>
            </bk-radio>
          </template>
        </bk-radio-group>
      </bk-form-item>

      <!-- 数据查询 -->
      <template v-if="formData.tool_type === 'data_search'">
        <bk-form-item
          :label="t('配置方式')"
          label-width="160"
          property="data_search_config_type"
          required>
          <bk-button-group>
            <bk-button
              v-for="item in searchTypeList"
              :key="item.value"
              :disabled="item.disabled"
              :selected="formData.data_search_config_type === item.value"
              @click="() => formData.data_search_config_type = item.value">
              {{ item.label }}
            </bk-button>
          </bk-button-group>
          <div>
            <bk-tag v-if="formData.data_search_config_type === 'simple'">
              {{ t('用于复杂的 SQL 查询，先编写 SQL，再根据 SQL 内的结果与变量配置前端样式') }}
            </bk-tag>
            <bk-tag v-else>
              {{ t('用于单一数据表，先配置的输入与输出字段，默认生成查询语句') }}
            </bk-tag>
          </div>
        </bk-form-item>
        <bk-form-item
          v-if="formData.data_search_config_type === 'simple'"
          :label="t('选择数据源')"
          label-width="160"
          property="source"
          required>
          <bk-input
            v-model="formData.source"
            :placeholder="t('请输入数据源名称、表名、ID 等，或可直接按分类筛选')" />
        </bk-form-item>
      </template>

      <!-- BKVision 图表 -->
      <div v-else-if="formData.tool_type === 'bk_vision'">
        <bk-form-item
          :label="t('选择报表')"
          label-width="160"
          property="config.uid"
          required>
          <div v-if="hasPermission">
            <div class="chart-cascade">
              <bk-cascader
                v-model="configUid"
                children-key="share"
                id-key="uid"
                :list="Array.isArray(chartLists) ? chartLists : []"
                :multiple="false"
                :show-complete-name="false"
                :style="spacePermission ? `width: 50%;border: 1px solid #e71818;` : `width: 50%;`"
                trigger="click"
                @change="handleSpaceChange" />
              <bk-button
                v-show="goBkVisionBtn && configUid.length > 0"
                class="ml8"
                @click="handleGoBkvision">
                {{ t('跳转至 BKVision') }}
              </bk-button>
              <audit-icon
                v-bk-tooltips="t('刷新报表')"
                class="vision-refresh"
                :class="{ rotating: isRefreshing }"
                type="refresh"
                @click="handleRefreshClick" />
            </div>
            <div
              v-if="spacePermission"
              class="permission">
              {{ t('该报表无权限，请') }} <span
                class="permission-link"
                @click="$emit('apply-permission')">{{ t('申请权限') }}</span>
            </div>
          </div>
          <div v-else>
            <bk-input
              disabled
              :model-value="t('当前图表你没有权限，请申请权限后再操作')" />
          </div>
        </bk-form-item>
      </div>
    </template>
  </card-part-vue>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import type { ChartListModel, FormData } from '../types';

  import CardPartVue from './card-part.vue';

  const props = defineProps<{
    isEditMode: boolean;
    comRef: any;
  }>();

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'apply-permission'): void;
    (e: 'update:is-show-component', value: boolean): void;
    (e: 'update:is-first-edit', value: boolean): void;
    (e: 'update:is-update', value: boolean): void;
    (e: 'update:report-lists-panels', value: any): void;
    (e: 'update:bk-vision-update-time', value: string): void;
  }>();

  const formData = defineModel<FormData>('formData', { required: true });

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const searchTypeList = [{
    label: t('简易模式'),
    value: 'simple',
    disabled: true,
  }, {
    label: t('SQL模式'),
    value: 'sql',
  }];

  const toolTypeList = ref<Array<{
    id: string;
    name: string;
    tips?: string;
  }>>([{
    id: 'data_search',
    name: t('数据查询'),
    tips: t('根据输入条件，使用 SQL 查询数据库以获得结果；可定义输入与输出'),
  }, {
    id: 'api',
    name: t('API接口'),
    tips: t('根据输入条件，使用 API 接口调用以获得结果。可定义输入与输出'),
  }, {
    id: 'bk_vision',
    name: t('BKVision图表'),
  }]);

  const iconMap = {
    data_search: 'sqlxiao',
    api: 'apixiao',
    bk_vision: 'bkvisonxiao',
  };

  const configUid = ref<string[]>([]);
  const hasPermission = ref(true);
  const spacePermission = ref(false);
  const goBkVisionBtn = ref(false);
  const isRefreshing = ref(false);
  const dashboardUid = ref('');
  const clickSpaceChange = ref(0);

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 跳转到BKVision
  const handleGoBkvision = () => {
    window.open(`${configData.value.third_party_system.bkvision_web_url}#/${configUid.value[0]}/dashboards/detail/root/${dashboardUid.value}`);
  };

  // 获取图表列表
  const {
    data: chartLists,
    run: fetchChartLists,
  } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: new Array<ChartListModel>(),
    onSuccess: (data) => {
      if (isRefreshing.value) {
        return;
      }
      if (data === 'error') {
        hasPermission.value = false;
        chartLists.value = [];
        return;
      }
      if (props.isEditMode) {
        if (Array.isArray(data)) {
          hasPermission.value = true;
          configUid.value = data.map((item: any) => {
            let ids = '';
            item.share.forEach((sh: any) => {
              if (sh.uid === formData.value.config.uid) {
                ids = `${item.uid},${sh.uid}`;
              }
            });
            return ids;
          }).filter(item => item !== '')[0].split(',');
        }
      }
    },
  });

  const bkVisionUpdateTime = ref('');
  const {
    run: fetchReportLists,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: {},
    onSuccess: (res) => {
      if (isRefreshing.value) {
        return;
      }
      if (res) {
        dashboardUid.value = res.data.dashboard_uid;
        const configInputVariable = _.cloneDeep(formData.value.config.input_variable);
        const { panels, variables } = res.data;
        emit('update:report-lists-panels', panels);
        const filters = [...new Set(Object.keys(res.filters))];

        // eslint-disable-next-line max-len
        const getInputVariableConfig = (isVariables: boolean, com: any, isEdit: boolean, originalDefaultValue?: string | Array<string>) => ({
          raw_name: (isVariables ? com?.flag : com?.chartConfig?.flag) || '',
          display_name: (isVariables ? com?.description : com.title) || '',
          description: com.uid || '',
          field_category: com.type || '',
          required: true,
          is_default_value: false,
          raw_default_value: '',
          default_value: isEdit ? originalDefaultValue : (originalDefaultValue || ''),
          choices: [],
        });

        // 编辑模式下第一次进入检查更新
        if (props.isEditMode && clickSpaceChange.value === 1) {
          emit('update:is-first-edit', true);
          emit('update:is-update', formData.value.is_bkvision);
          formData.value.config.input_variable = formData.value.config.input_variable.map((item) => {
            if (item.field_category === 'variable') {
              let variablesDescription = '';
              variables.forEach((variable: any) => {
                if (variable.uid === item.description) {
                  variablesDescription = variable.description;
                }
              });
              return {
                ...item,
                raw_default_value: res.constants[item.raw_name],
                display_name: variablesDescription,
                default_value: item.default_value,
                choices: [],
              };
            }
            return {
              ...item,
              default_value: item.default_value,
              choices: [],
            };
          });
        } else {
          emit('update:is-first-edit', false);
          emit('update:is-update', false);
          formData.value.config.input_variable = filters
            .map((item) => {
              const com = panels.find((p: any) => p.uid === item);
              if (!com) return null;

              let originalDefaultValue: string | Array<string> = '';
              if (props.isEditMode && configInputVariable.length > 0) {
                const originalItem = configInputVariable.find((original: any) => original.description === com.uid);
                if (originalItem) originalDefaultValue = originalItem.default_value;
              } else {
                originalDefaultValue = res.filters[com.uid];
              }
              return getInputVariableConfig(false, com, props.isEditMode, originalDefaultValue);
            })
            .filter((item): item is NonNullable<typeof item> => item !== null);

          if (variables.length > 0) {
            variables.forEach((com: any) => {
              if (com.build_in) return;
              let originalDefaultValue: string | Array<string> = '';
              if (props.isEditMode && configInputVariable.length > 0) {
                const originalItem = configInputVariable.find((original: any) => original.description === com.uid);
                if (originalItem) originalDefaultValue = originalItem.default_value;
              } else {
                originalDefaultValue = res.constants[com.flag];
              }
              formData.value.config.input_variable.push({
                ...getInputVariableConfig(true, com, props.isEditMode, originalDefaultValue),
                is_default_value: false,
                raw_default_value: originalDefaultValue || '',
              });
            });
          }
        }

        bkVisionUpdateTime.value = res.data.updated_time || null;
        emit('update:bk-vision-update-time', bkVisionUpdateTime.value);

        // 设置组件配置
        nextTick(() => {
          const bkVisionCom = filters
            .map((item) => {
              const com = panels.find((p: any) => p.uid === item);
              if (!com) return null;
              return getInputVariableConfig(false, com, true, res.filters[item]);
            })
            .filter((item): item is NonNullable<typeof item> => item !== null);
          const updatedBkVisionCom = bkVisionCom.map((comItem) => {
            // eslint-disable-next-line max-len
            const formItemMatch = formData.value.config.input_variable.find(formItem => formItem.description === comItem.description);
            if (formItemMatch) {
              return {
                ...comItem,
                is_default_value: formItemMatch.is_default_value,
              };
            }
            return comItem;
          });
          props.comRef?.setConfigs(formData.value.config.input_variable);
          props.comRef?.setVariablesConfig(res.data.variables, updatedBkVisionCom, res);
        });
        goBkVisionBtn.value = true;
      } else {
        spacePermission.value = true;
        goBkVisionBtn.value = false;
      }
    },
  });

  // 刷新图标点击事件
  const handleRefreshClick = async () => {
    if (isRefreshing.value) return;
    isRefreshing.value = true;
    try {
      fetchChartLists().then(() => {
        messageSuccess(t('刷新成功'));
      });
      if (configUid.value.length > 0) {
        await fetchReportLists({
          share_uid: configUid.value[configUid.value.length - 1],
        });
      }
    } finally {
      isRefreshing.value = false;
    }
  };

  // 选择报表
  const handleSpaceChange = (val: string) => {
    isRefreshing.value = false;
    clickSpaceChange.value += 1;
    spacePermission.value = false;
    if (val.length === 0) {
      return;
    }
    fetchReportLists({
      share_uid: val[val.length - 1],
    }).then((r) => {
      if (!r) {
        emit('update:is-show-component', false);
      } else {
        emit('update:is-show-component', true);
      }
    });
  };

  // 监听 configUid 变化
  watch(() => configUid.value, (val) => {
    if (val.length === 0) {
      formData.value.config.uid = '';
      emit('update:is-show-component', false);
    } else {
      formData.value.config.uid = val[val.length - 1];
      emit('update:is-show-component', true);
    }
  }, {
    deep: true,
  });

  // 监听工具类型变化，获取图表列表
  watch(() => formData.value.tool_type, (val) => {
    if (val === 'bk_vision') {
      fetchChartLists();
    }
  });

  // 暴露方法供父组件调用
  defineExpose({
    configUid,
    getBkVisionUpdateTime: () => bkVisionUpdateTime.value,
  });
</script>

<style lang="postcss" scoped>
  .chart-cascade {
    display: flex;
  }

  .vision-refresh {
    display: flex;
    margin-left: 10px;
    font-size: 18px;
    color: #87888f;
    cursor: pointer;
    transition: transform .3s ease;
    align-items: center;
    justify-content: center;

    &.rotating {
      animation: refresh 1s linear infinite;
    }
  }

  @keyframes refresh {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .permission {
    font-size: 12px;
    color: #e71818;

    .permission-link {
      color: #3a84ff;
      cursor: pointer;
    }
  }
</style>
