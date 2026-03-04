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
  <div class="strategy-customize">
    <auth-collapse-panel
      is-active
      :label="t('规则配置')"
      style="margin-bottom: 14px">
      <div class="customize-rule">
        <bk-form-item
          label=""
          label-width="0"
          required>
          <span
            v-bk-tooltips="{
              content: t(
                '审计规则的数据来源，联动后续步骤字段结构。如需组合数据，请提前创建并选择联表数据'
              ),
              extCls: 'strategy-config-type-tooltips',
              placement: 'top-start'
            }"
            class="label-is-required"
            style="
              color: #63656e;
              cursor: pointer;
              border-bottom: 1px dashed #979ba5;
            ">
            {{ t('数据源') }}
          </span>
          <bk-loading :loading="typeTableLoading">
            <div
              class="select-group"
              :class="formData.configs.config_type === 'EventLog' ? 'select-group-grid' : ''">
              <bk-form-item
                v-if="allConfigTypeTable.length"
                class="no-label"
                label-width="0"
                property="configs.config_type">
                <bk-cascader
                  v-slot="{data, node}"
                  v-model="tableId"
                  :filter-method="configTypeTableFilter"
                  filterable
                  id-key="value"
                  :list="allConfigTypeTable"
                  name-key="label"
                  :placeholder="t('搜索数据名称、别名、数据ID等')"
                  trigger="hover"
                  @change="handleChangeTable">
                  <p
                    v-bk-tooltips="{
                      disabled: !data.disabled || !data.leaf,
                      content: node.pathNames[0] === '资产数据'
                        ? t('该系统暂未上报资源数据')
                        : t('审计无权限，请前往BKBase申请授权'),
                      delay: 400,
                    }">
                    {{ node.name }}
                  </p>
                </bk-cascader>
              </bk-form-item>
              <template v-if="formData.configs.config_type === 'EventLog'">
                <event-log-component
                  ref="eventLogRef"
                  @update-system="handleUpdateSystem" />
              </template>
            </div>
          </bk-loading>
          <!-- 联表详情 -->
          <link-data-detail-component
            v-if="formData.configs.data_source.link_table
              && formData.configs.data_source.link_table.uid
            "
            :join-type-list="joinTypeList"
            :link-data-detail="linkDataDetail"
            @refresh-link-data="handleRefreshLinkData" />
          <!-- 其他数据表详情 -->
          <other-table-detail-component
            v-if="formData.configs.data_source.rt_id?.length"
            :rt-id="formData.configs.data_source.rt_id"
            @show-structure-preview="handleShowStructureView" />
          <!-- 查看表字段详情 -->
          <structure-preview-component
            v-model:show-structure="showStructure"
            :current-view-field="currentViewField"
            :rt-id="currentViewRtId" />
        </bk-form-item>
        <bk-form-item
          label=""
          label-width="160">
          <template #label>
            <span
              v-bk-tooltips="{
                content: t(
                  '需要哪些字段作为结果，每行记录可生成一个风险事件，展示在风险单内；也可用于第2步”单据展示“的字段映射；点击下方”预览“可提前预览风险单展示内容；'
                ),
                extCls: 'strategy-config-type-tooltips',
                placement: 'top-start'
              }"
              style="
                color: #63656e;
                cursor: pointer;
                border-bottom: 1px dashed #979ba5;
              ">
              {{ t('预期结果') }}
            </span>
          </template>
          <expected-results
            ref="expectedResultsRef"
            :aggregate-list="aggregateList"
            :config-type="formData.configs.config_type"
            :table-fields="tableFields"
            @update-expected-result="handleUpdateExpectedResult" />
        </bk-form-item>
        <bk-form-item
          label=""
          label-width="160"
          required>
          <template #label>
            <span
              v-bk-tooltips="{
                content: t(
                  '配置对应的字段与规则，筛选出我们期望的数据；可能是风险数据。'
                ),
                extCls: 'strategy-config-type-tooltips',
                placement: 'top-start'
              }"
              style="
                color: #63656e;
                cursor: pointer;
                border-bottom: 1px dashed #979ba5;
              ">
              {{ t('风险发现规则') }}
            </span>
          </template>
          <rules-component
            ref="rulesComponentRef"
            :aggregate-list="aggregateList"
            :config-type="formData.configs.config_type"
            :configs-data="formData.configs"
            :expected-result="formData.configs.select"
            :table-fields="tableFields"
            @show-structure-preview="handleShowStructureView"
            @update-where="handleUpdateWhere" />
        </bk-form-item>
      </div>
    </auth-collapse-panel>
    <auth-collapse-panel
      is-active
      :label="t('调度配置')"
      style="margin-bottom: 12px">
      <div class="dispatch-wrap">
        <bk-form-item
          :label="t('调度方式')"
          property="configs.data_source.source_type"
          style="margin-bottom: 12px">
          <bk-radio-group
            v-model="formData.configs.data_source.source_type"
            class="source-type-radio-group"
            :disabled="isEditMode"
            @change="handleSourceTypeChange">
            <bk-radio
              v-bk-tooltips="{
                content: getSourceTypeStatus('batch_join_source').tips,
                placement: 'top-start',
                disabled: !getSourceTypeStatus('batch_join_source').disabled
              }"
              :disabled="getSourceTypeStatus('batch_join_source').disabled"
              label="batch_join_source" />
            <span
              v-bk-tooltips="{
                content: t(
                  '按天则下一调度时间为当天0点；按小时则为下一调度时间为下个小时整点；并作为固定发起时间；'
                ),
                extCls: 'strategy-config-type-tooltips',
                placement: 'top-start',
              }"
              :style="{
                color: (isEditMode || getSourceTypeStatus('batch_join_source').disabled) ? '#c4c6cc' : '#63656e',
                cursor: (isEditMode || getSourceTypeStatus('batch_join_source').disabled) ? 'not-allowed' : 'pointer',
                borderBottom: `1px dashed ${(isEditMode || getSourceTypeStatus('stream_source').disabled)
                  ? '#c4c6cc' : '#979ba5'}`,
                marginLeft: '6px',
                lineHeight: '12px',
              }">
              {{ t('固定周期调度') }}
            </span>
            <bk-radio
              v-bk-tooltips="{
                content: getSourceTypeStatus('stream_source').tips,
                placement: 'top-start',
                disabled: !getSourceTypeStatus('stream_source').disabled
              }"
              :disabled="getSourceTypeStatus('stream_source').disabled"
              label="stream_source" />
            <span
              v-bk-tooltips="{
                content: t('策略实时运行'),
                placement: 'top-start',
              }"
              :style="{
                color: (isEditMode || getSourceTypeStatus('stream_source').disabled) ? '#c4c6cc' : '#63656e',
                cursor: (isEditMode || getSourceTypeStatus('stream_source').disabled) ? 'not-allowed' : 'pointer',
                borderBottom: `1px dashed ${(isEditMode || getSourceTypeStatus('stream_source').disabled)
                  ? '#c4c6cc' : '#979ba5'}`,
                marginLeft: '6px',
                lineHeight: '12px',
              }">
              {{ t('实时调度') }}
            </span>
          </bk-radio-group>
        </bk-form-item>
        <template
          v-if="
            formData.configs.data_source.source_type === 'batch_join_source'
          ">
          <span
            v-bk-tooltips="t('策略运行的周期')"
            class="label-is-required circle">
            {{ t('调度周期') }}
          </span>
          <div class="flex-center">
            <bk-form-item
              class="is-required no-label"
              label-width="0"
              property="configs.schedule_config.count_freq"
              style="margin-bottom: 12px">
              <bk-input
                v-model="formData.configs.schedule_config.count_freq"
                class="schedule-input"
                :min="1"
                onkeypress="return( /[\d]/.test(String.fromCharCode(event.keyCode) ) )"
                :placeholder="t('请输入')"
                type="number" />
            </bk-form-item>
            <bk-form-item
              class="is-required no-label"
              label-width="0"
              property="configs.schedule_config.schedule_period"
              style="margin-bottom: 12px">
              <bk-select
                v-model="formData.configs.schedule_config.schedule_period"
                class="schedule-select"
                :clearable="false"
                style="width: 68px">
                <bk-option
                  v-for="(item, index) in commonData.offset_unit"
                  :key="index"
                  :label="item.label"
                  :value="item.value" />
              </bk-select>
            </bk-form-item>
          </div>
        </template>
      </div>
    </auth-collapse-panel>
  </div>
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import {
    computed,
    h,
    nextTick,
    onMounted,    ref,
    watch,
    watchEffect } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import LinkDataManageService from '@service/link-data-manage';
  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import ExpectedResults from './components/expected-results/index.vue';
  import LinkDataDetailComponent from './components/link-table-detail/index.vue';
  import OtherTableDetailComponent from './components/other-table-detail/index.vue';
  import RulesComponent from './components/rules/index.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import StructurePreviewComponent from './components/structure-preview/index.vue';

  import useRequest from '@/hooks/use-request';

  interface Where {
    connector: 'and' | 'or'
    conditions: Array<{
      connector: 'and' | 'or',
      index: number,
      conditions: Array<{
        condition: {
          field: DatabaseTableFieldModel | ''
          filter: string
          filters: string[]
          operator: string
        }
      }>
    }>
  }
  interface IFormData {
    configs: {
      data_source: {
        display_name?: string
        system_ids: string[]
        source_type: string
        rt_id: string | string[]
        link_table: {
          uid: string
          version: number
        }
      }
      config_type: string
      select: Array<DatabaseTableFieldModel>
      where: Where
      having?: Where
      schedule_config: {
        count_freq: string
        schedule_period: string
      }
    }
  }
  interface ConfigTypeTableItem {
    label: string
    value: string
    children: Array<{
      label: string
      value: string
      version?: number
      children?: Array<{
        label: string
        value: string
      }>
    }>
  }
  interface Emits {
    (e: 'updateFormData', value: IFormData): void
  }
  interface Expose {
    getFields: () => IFormData;
    typeTableLoading: boolean;
  }
  interface Props {
    editData: any
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const rulesComponentRef = ref();
  const expectedResultsRef = ref();
  const eventLogRef = ref();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const tableId = ref<Array<string>>([]);
  const previousTableId = ref<Array<string>>([]);
  let isInit = false;

  const formData = ref<IFormData>({
    configs: {
      data_source: {
        system_ids: [],
        source_type: '',
        rt_id: [],
        link_table: {
          uid: '',
          version: 0,
        },
      },
      config_type: '',
      select: [],
      where: {
        connector: 'and',
        conditions: [],
      },
      having: {
        connector: 'and',
        conditions: [],
      },
      schedule_config: {
        count_freq: '',
        schedule_period: 'hour',
      },
    },
  });
  const ruleAuditConfigType = ref<Array<{
    label: string,
    value: string
  }>>([]);
  const aggregateList = ref<Array<Record<string, any>>>([]);
  const tableFields = ref<Array<DatabaseTableFieldModel>>([]);
  const joinTypeList = ref<Array<Record<string, any>>>([]);
  const allConfigTypeTable = ref<Array<ConfigTypeTableItem>>([]);
  const typeTableLoading = ref(false);
  const originSourceType = ref<'batch_join_source' | 'stream_source' | ''>('');
  const availableSourceTypes = ref<Array<string>>([]);

  const showStructure = ref(false);
  const currentViewRtId = ref<string | Array<string>>([]);
  const currentViewField = ref<string>('');

  const hasData = computed(() => Boolean(formData.value.configs.select.length
    || (formData.value.configs.where.conditions.length
      && formData.value.configs.where.conditions[0].conditions.length
      && formData.value.configs.where.conditions[0].conditions[0].condition.field
      && formData.value.configs.where.conditions[0].conditions[0].condition.field.raw_name)));

  const getSourceTypeStatus = computed(() => (type: 'batch_join_source' | 'stream_source') => {
    // 检查该类型是否在支持列表中，或者对于stream_source类型是否存在聚合字段有不为null的aggregate，或者是编辑模式
    if (isEditMode
      || !sourceType.value.support_source_types.includes(type)
      || (type === 'stream_source' && formData.value.configs.select.some(item => item.aggregate))) {
      return {
        disabled: true,
        // eslint-disable-next-line no-nested-ternary
        tips: isEditMode
          ? t('编辑状态下不能编辑调度方式')
          : !sourceType.value.support_source_types.includes(type)
            ? t('不可选择，如仍需使用此数据，请联系系统管理员')
            : t('当前"预期结果"中包含"聚合算法"，不支持使用当前调度方式'),
      };
    }

    return {
      disabled: false,
      tips: '',
    };
  });

  // 获取公共数据(字典)
  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess() {
      ruleAuditConfigType.value = commonData.value.rule_audit_config_type;
      joinTypeList.value = commonData.value.link_table_join_type;
      aggregateList.value = [
        {
          label: t('不聚合'),
          value: null,
        },
        ...commonData.value.rule_audit_aggregate_type,
      ];
      // 获取到数据源类别后，获取所有tableid
      getAllConfigTypeTable();
    },
  });

  // 获取tableid
  const {
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  // 获取联表tableid
  const {
    run: fetchLinkTableAll,
  } = useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
  });

  // 获取全部tableid
  const getAllConfigTypeTable = () => {
    typeTableLoading.value = true;
    const requests = ruleAuditConfigType.value.map((item) => {
      if (item.value === 'LinkTable') {
        return async () => {
          const LinkTableData = await fetchLinkTableAll();
          return [{
            ...item,
            children: LinkTableData.map(tableItem => ({
              label: tableItem.name,
              value: tableItem.uid,
              version: tableItem.version,
            })),
          }];
        };
      }
      return async () => {
        const data = await fetchTable({
          table_type: item.value,
        });
        return [{
          ...item,
          children: data.map(tableItem => ({
            ...tableItem,
            leaf: true,
            disabled: !(tableItem.children && tableItem.children.length) && item.value !== 'EventLog',
          })),
        }];
      };
    });
    // 获取全部table
    Promise.all(requests.map(fn => fn()))
      .then((results) => {
        const flattenedResults = results.reduce((acc, curr) => acc.concat(curr), [] as Array<ConfigTypeTableItem>);
        allConfigTypeTable.value = flattenedResults;
        typeTableLoading.value = false;
      });
  };

  // 搜索数据源
  const configTypeTableFilter = (node: Record<string, any>, key: string) => {
    // 转换searchKey为小写以支持大小写不敏感的搜索
    const lowercaseSearchKey = key.toLowerCase();
    // 只匹配叶子节点
    const isLeaf = !Array.isArray(node.children) || node.children.length === 0;
    if (!isLeaf) return false;
    return node.data.label.toLowerCase().includes(lowercaseSearchKey)
      || node.data.value.toLowerCase().includes(lowercaseSearchKey);
  };

  // 选择tableid后，获取该table的可用调度方式
  const {
    run: fetchSourceType,
    data: sourceType,
  } = useRequest(StrategyManageService.fetchSourceType, {
    defaultValue: {
      support_source_types: ['batch_join_source', 'stream_source'],
    },
    onSuccess: () => {
      // 获取所有可用的调度方式
      availableSourceTypes.value = sourceType.value.support_source_types.filter((type) => {
        if (type === 'stream_source') {
          // stream_source模式下:
          // 存在聚合算法的数据不能使用该模式
          return !formData.value.configs.select.some(item => item.aggregate);
        }
        return true; // 其他类型都可用
      });

      // 如果是编辑模式，当originSourceType存在且在可用列表中，保持不变
      if (isEditMode && originSourceType.value && availableSourceTypes.value.includes(originSourceType.value)) {
        formData.value.configs.data_source.source_type = originSourceType.value;
      }

      // 如果没有可用类型或当前选择的类型不在可用列表中，则重置source_type
      if (!availableSourceTypes.value.length
        || !availableSourceTypes.value.includes(formData.value.configs.data_source.source_type as 'batch_join_source' | 'stream_source')) {
        formData.value.configs.data_source.source_type = '';
      }
    },
  });

  const setTableFields = (
    data: Array<{
      field_type: string
      label: string
      value: string
      spec_field_type: string
      property?: Record<string, any>
    }>,
    displayOrRtId: string,
  ) => data.map(item => ({
    table: displayOrRtId, // 别名，单表时为rt_id
    raw_name: item.value,
    display_name: item.label,
    field_type: item.field_type,
    aggregate: null,
    spec_field_type: item.spec_field_type,
    remark: '',
    property: item.property || {},
  }));

  // 选择tableid后，获取表字段
  const fetDatabaseTableFields = (rtId: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: rtId,
    }).then((data) => {
      tableFields.value = setTableFields(data, rtId);
    });
  };

  // 选择tableid后，获取联表表字段
  const fetchLinkTableFields = async (
    rtIdArr: string[][],
    rtIdArrDisplay: string[][],
  ) => {
    // rt_id
    const idArr = Array.from(new Set(rtIdArr.reduce((acc, curr) => acc.concat(curr), [])));
    // 别名
    const displayArr = Array.from(new Set(rtIdArrDisplay.reduce((acc, curr) => acc.concat(curr), [])));
    StrategyManageService.fetchBatchTableRtFields({
      table_ids: idArr.join(','),
    }).then((data) => {
      tableFields.value = [];
      data.forEach((item: Record<string, any>, index) => {
        tableFields.value.push(...setTableFields(item.fields, displayArr[index]));
      });
    });
  };

  // 获取关联表详情
  const {
    data: linkDataDetail,
    run: fetchLinkDataSheetDetail,
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
    onSuccess: () => {
      // 设置联表version
      formData.value.configs.data_source.link_table.version = linkDataDetail.value.version;
      const rtIdArr = linkDataDetail.value.config.links.map(item => [
        item.left_table.rt_id,
        item.right_table.rt_id,
      ]) as string[][];
      // 表别名
      const rtIdArrDisplay = linkDataDetail.value.config.links.map(item => [
        item.left_table.display_name,
        item.right_table.display_name,
      ]) as string[][];
      if (rtIdArr.length) {
        // 联表获取表字段
        fetchLinkTableFields(rtIdArr, rtIdArrDisplay);
        // 获取表可用调度方式
        fetchSourceType({
          config_type: formData.value.configs.config_type,
          link_table: {
            uid: linkDataDetail.value.uid,
            version: linkDataDetail.value.version,
          },
        });
      }
    },
  });

  // 刷新联表详情
  const handleRefreshLinkData = () => {
    fetchLinkDataSheetDetail({
      uid: linkDataDetail.value.uid,
    });
    // 重置数据
    formData.value.configs.select = [];
    formData.value.configs.where = {
      connector: 'and',
      conditions: [],
    };
    rulesComponentRef.value.resetFormData();
    expectedResultsRef.value.resetFormData();
  };

  const findRtIdByDisplayName = (rtId: string | Array<string>) => {
    const { links } = linkDataDetail.value.config;
    const found = links.find(link => link.left_table.display_name === rtId || link.right_table.display_name === rtId);
    if (!found) return '';
    if (found.left_table.display_name === rtId) return found.left_table.rt_id;
    return found.right_table.rt_id;
  };

  const handleShowStructureView = (rtId: string | Array<string>, presentViewField: string) => {
    if (presentViewField) {
      currentViewField.value = presentViewField;
    }
    // 如果是联表，获取联表的rt_id
    if (formData.value.configs.config_type === 'LinkTable') {
      const firstRtId = findRtIdByDisplayName(rtId);
      currentViewRtId.value = firstRtId;
    } else {
      currentViewRtId.value = rtId;
    }
    showStructure.value = true;
  };

  const getFirstAndLast = (arr: Array<string>) => {
    if (!arr || arr.length === 0) {
      return { config_type: undefined,  rt_id_or_uid: undefined };
    }
    return {
      config_type: arr[0],
      rt_id_or_uid: arr[arr.length - 1],
    };
  };
  const removeTreeData = () => {
    sessionStorage.removeItem('storage-tree-data');
  };
  const createInfoBoxConfig = (overrides: {
    onConfirm: () => void
    onClose: () => void
  }): any => ({
    type: 'warning',
    title: t('切换数据源请注意'),
    subTitle: () => h(
      'div',
      {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          padding: '12px 16px',
          borderRadius: '2px',
          fontSize: '14px',
          textAlign: 'left',
        },
      },
      t('切换后，已配置的数据将被清空。是否继续？'),
    ),
    confirmText: t('继续切换'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    ...overrides,
    onConfirm: () => {
      removeTreeData(); // 无论外部是否传入 onConfirm，都先执行 removeTreeData
      overrides.onConfirm?.(); // 如果外部传入了 onConfirm，再执行它
    },
    onClose: () => {
      removeTreeData(); // 无论外部是否传入 onClose，都先执行 removeTreeData
      overrides.onClose?.(); // 如果外部传入了 onClose，再执行它
    },
  });

  // 重置数据源和表单
  const resetDataSource = () => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...{
        rt_id: '',
        link_table: { uid: '', version: 0 },
        system_ids: [],
      },
    };
    formData.value.configs.select = [];
    formData.value.configs.where = {
      connector: 'and',
      conditions: [],
    };
    formData.value.configs.having = {
      connector: 'and',
      conditions: [],
    };
    [eventLogRef, rulesComponentRef, expectedResultsRef].forEach(ref => ref.value?.resetFormData?.());
  };

  // 选择tableid和数据源类型
  const handleChangeTable = (value: Array<string>) => {
    const handleTableChangeCore = (value: Array<string>) => {
      const typeAndId = getFirstAndLast(value);
      const { config_type: configType, rt_id_or_uid: rtIdOrUid  } = typeAndId;

      // 更新数据源类型
      formData.value.configs.config_type = configType || '';

      // 无有效类型时重置数据
      if (!configType) {
        resetDataSource();
        tableFields.value = [];
        // 更新前次记录
        previousTableId.value = value;
        return;
      }

      // 有填写预期结果、风险发现规则，重置
      if (hasData.value) {
        resetDataSource();
      }

      // 统一处理数据源设置
      if (configType === 'LinkTable') {
        formData.value.configs.data_source.link_table.uid = rtIdOrUid || '';
        formData.value.configs.data_source.rt_id = '';
        formData.value.configs.data_source.system_ids = [];
        rtIdOrUid && fetchLinkDataSheetDetail({ uid: rtIdOrUid });
      } else {
        formData.value.configs.data_source.rt_id = rtIdOrUid || '';
        formData.value.configs.data_source.link_table.uid = '';
        formData.value.configs.data_source.link_table.version = 0;
        if (rtIdOrUid) {
          fetDatabaseTableFields(rtIdOrUid);
          fetchSourceType({ config_type: configType, rt_id: rtIdOrUid });
        }
      }

      // 更新前次记录
      previousTableId.value = value;
    };

    // 相同值返回
    if (previousTableId.value.join(',') === value.join(',')) {
      return;
    }

    // 首次初始化或没有配置数据，直接处理
    if (!formData.value.configs.config_type || !hasData.value) {
      handleTableChangeCore(value);
      return;
    }
    // 已有配置时弹窗确认
    InfoBox(createInfoBoxConfig({
      onConfirm: () => handleTableChangeCore(value),
      onClose: () => {
        tableId.value = previousTableId.value;
      },
    }));
  };

  // 更新系统
  const handleUpdateSystem = (systemIds: Array<string>) => {
    formData.value.configs.data_source.system_ids = systemIds;
  };

  // 更新预期数据
  const handleUpdateExpectedResult = (expectedResult: Array<DatabaseTableFieldModel>) => {
    formData.value.configs.select = expectedResult;
    // 如果当前选中的就是实时调度且预期结果不满足条件，需要重置
    if (formData.value.configs.data_source.source_type === 'stream_source' && formData.value.configs.select.some(item => item.aggregate)) {
      formData.value.configs.data_source.source_type = '';
      return;
    }
    // 如不果是编辑模式，当originSourceType存在且在可用列表中，保持变
    if (isEditMode && originSourceType.value && availableSourceTypes.value.includes(originSourceType.value)) {
      formData.value.configs.data_source.source_type = originSourceType.value;
    }
  };

  // 更新风险规则
  const handleUpdateWhere = (where: Where) => {
    formData.value.configs.where = where;
  };

  const handleSourceTypeChange = () => {
    formData.value.configs.schedule_config = {
      count_freq: '',
      schedule_period: 'hour',
    };
  };

  const changeTableId = () => {
    const tableItem = allConfigTypeTable.value.find(item => item.value === formData.value.configs.config_type);
    if (!tableItem) return;
    // 联表和日志只有两层，直接拼接
    if (tableItem.value === 'EventLog') {
      tableId.value = [formData.value.configs.config_type, formData.value.configs.data_source.rt_id as string];
      previousTableId.value = tableId.value ;
      nextTick(() => {
        eventLogRef.value?.setConfigs(formData.value.configs.data_source.system_ids);
      });
    } else if (tableItem.value === 'LinkTable') {
      tableId.value = [formData.value.configs.config_type, formData.value.configs.data_source.link_table.uid];
      previousTableId.value = tableId.value ;
    } else {
      // 资产和其他数据还需要获取二级父id
      tableItem.children.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === formData.value.configs.data_source.rt_id) {
              const id = [item.value, formData.value.configs.data_source.rt_id];
              tableId.value = [formData.value.configs.config_type, ...id];
              previousTableId.value = tableId.value ;
            }
          });
        }
      });
    }
  };

  // 编辑
  const setFormData = (editData: any) => {
    formData.value.configs.config_type = editData.configs.config_type || '';
    formData.value.configs.schedule_config = editData.configs.schedule_config;
    formData.value.configs.select = editData.configs.select;
    expectedResultsRef.value.setSelect(editData.configs.select);
    rulesComponentRef.value.setWhere(editData.configs.where, editData.configs.having);
    if (editData.configs.data_source) {
      formData.value.configs.data_source = editData.configs.data_source;
      originSourceType.value = editData.configs.data_source.source_type as 'batch_join_source' |'stream_source' | '';
    }
    // 转换tableid,反显
    changeTableId();
    if (formData.value.configs.config_type === 'LinkTable') {
      fetchLinkDataSheetDetail({
        uid: formData.value.configs.data_source.link_table.uid,
        version: formData.value.configs.data_source.link_table.version,
      });
    } else {
      fetDatabaseTableFields(formData.value.configs.data_source.rt_id as string);
      fetchSourceType({
        config_type: formData.value.configs.config_type,
        rt_id: formData.value.configs.data_source.rt_id as string,
      });
    }
  };

  // 监听formData变化，更新数据
  watch(
    () => formData.value,
    (data) => {
      emits('updateFormData', data);
    },
    {
      deep: true,
    },
  );

  watchEffect(() => {
    if ((isEditMode || isCloneMode) && (props.editData.strategy_id && allConfigTypeTable.value.length > 0)) {
      if (isInit) {
        return;
      }
      setFormData(props.editData);
      isInit = true;
    }
  });

  defineExpose<Expose>({
    // 获取提交参数
    getFields() {
      const params = _.cloneDeep(formData.value);
      const tableIdList = params.configs.data_source.rt_id;
      if (params.configs.config_type !== 'EventLog') {
        params.configs.data_source = {
          ...params.configs.data_source,
          rt_id: (_.isArray(tableIdList)
            ? (_.last(tableIdList) || '')
            : tableIdList) as string,
        };
      }
      // 如果select为空数组，传全部
      if (params.configs.select && params.configs.select.length === 0) {
        // 通过一次遍历完成 display_name 的设置和统计
        const displayNameCount = tableFields.value.reduce<Record<string, number>>(
          (acc, item) => {
            const displayName = `${item.display_name}${
              item.aggregate ? `_${item.aggregate}` : ''
            }`;
            acc[displayName] = (acc[displayName] || 0) + 1;
            return acc;
          },
          {},
        );

        // 更新 params.configs.select，使用统计结果调整 display_name
        params.configs.select = tableFields.value.map((item) => {
          const displayName = `${item.display_name}${
            item.aggregate ? `_${item.aggregate}` : ''
          }`;
          return {
            ...item,
            aggregate: null,
            display_name:
              displayNameCount[displayName] > 1
                ? `${item.table}.${item.display_name}`
                : displayName,
          };
        });
        expectedResultsRef.value.setSelect(params.configs.select);
      }
      // 添加having参数
      if (params.configs.where) {
        // 数据结构和where保持一致，将field的aggregate不为null的添加到having中
        const having = {
          connector: params.configs.where.connector,
          conditions: params.configs.where.conditions
            .map(group => ({
              connector: group.connector,
              index: group.index,
              conditions: group.conditions.filter(item => typeof item.condition.field !== 'string' && item.condition.field?.aggregate),
            }))
            // 过滤掉没有聚合条件的组
            .filter(group => group.conditions.length > 0),
        };
        if (having.conditions.length > 0) {
          params.configs.having = having;
          // 将where中符合having的条件删除
          params.configs.where.conditions = params.configs.where.conditions
            .map(group => ({
              connector: group.connector,
              index: group.index,
              conditions: group.conditions.filter(item => typeof item.condition.field !== 'string' && !item.condition.field?.aggregate),
            }))
            // 过滤掉没有聚合条件的组
            .filter(group => group.conditions.length > 0);
        } else {
          delete params.configs.having;
        }
      }
      // 同步display_name
      params.configs.data_source.display_name = (params.configs.data_source.rt_id?.length > 1 ? params.configs.data_source.rt_id : '') as string;
      return params;
    },
    // 暴露 typeTableLoading 状态
    get typeTableLoading() {
      return typeTableLoading.value;
    },
  });
  onMounted(() => {
    sessionStorage.removeItem('storage-tree-data'); // 清除数据
  });
</script>
<style scoped lang="postcss">
.strategy-customize {
  .label-is-required::after {
    position: absolute;
    width: 14px;
    line-height: 32px;
    color: #ea3636;
    text-align: center;
    content: '*';
  }

  .no-label .bk-form-label::after {
    content: '';
  }

  .no-label .bk-form-label {
    padding-right: 0;
  }

  .customize-rule {
    padding: 16px 32px 24px;

    .select-group {
      :deep(.bk-form-item) {
        margin-bottom: 0;
      }
    }

    .select-group-grid {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;
    }

    :deep(.bk-infobox-title) {
      margin-top: 0;
    }
  }

  .dispatch-wrap {
    padding: 16px 24px;

    :deep(.source-type-radio-group) {
      .bk-radio-label {
        display: none;
      }
    }

    .flex-center {
      display: flex;
      align-items: center;
    }

    .circle {
      line-height: 32px;
      color: #63656e;
      cursor: pointer;
      border-bottom: 1px dashed #979ba5;
    }
  }
}
</style>
<style>
.strategy-config-type-tooltips {
  width: 380px;
  word-wrap: break-word;
}
</style>
