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
      style="margin-bottom: 14px;">
      <div class="customize-rule">
        <bk-form-item
          label=""
          label-width="0"
          required>
          <span
            class="label-is-required"
            style="color: #63656e;">
            {{ t('数据源') }}
          </span>
          <div class="select-group">
            <bk-form-item
              class="no-label"
              label-width="0"
              property="configs.config_type">
              <bk-select
                v-model="configType"
                filterable
                :placeholder="t('请选择数据源类型')"
                @change="handleDataSourceType">
                <bk-option
                  v-for="item in ruleAuditConfigType"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value" />
              </bk-select>
            </bk-form-item>
            <!-- 四种数据源，对应的输入类型 -->
            <component
              :is="configTypeMap[formData.configs.config_type] || EventLogComponent"
              ref="configRef"
              :source-type="formData.configs.config_type"
              :table-data="tableData"
              @update-data-source="handleUpdateDataSource"
              @update-link-data-detail="handleUpdateLinkDataDetail" />
          </div>
          <!-- 联表详情 -->
          <link-data-detail-component
            v-if="formData.configs.data_source.link_table && formData.configs.data_source.link_table.uid"
            :link-data-detail="linkDataDetail"
            @refresh-link-data="handleRefreshLinkData" />
        </bk-form-item>
        <bk-form-item
          :label="t('预期结果')"
          label-width="160">
          <expected-results
            ref="expectedResultsRef"
            :aggregate-list="aggregateList"
            :config-type="formData.configs.config_type"
            :table-fields="tableFields"
            @update-expected-result="handleUpdateExpectedResult" />
        </bk-form-item>
        <bk-form-item
          :label="t('风险发现规则')"
          label-width="160"
          required>
          <rules-component
            ref="rulesComponentRef"
            :config-type="formData.configs.config_type"
            :table-fields="tableFields"
            @update-where="handleUpdateWhere" />
        </bk-form-item>
      </div>
    </auth-collapse-panel>
    <auth-collapse-panel
      is-active
      :label="t('调度配置')"
      style="margin-bottom: 12px;">
      <div class="dispatch-wrap">
        <bk-form-item
          :label="t('调度方式')"
          property="source_type"
          style="margin-bottom: 12px;">
          <bk-radio-group
            v-model="formData.configs.data_source.source_type"
            :disabled="isEditMode"
            @change="handleSourceTypeChange">
            <bk-radio label="batch_join_source">
              {{ t('固定周期调度') }}
            </bk-radio>
            <bk-radio label="stream_source">
              <span
                v-bk-tooltips="t('策略实时运行')"
                style="color: #63656e; cursor: pointer; border-bottom: 1px dashed #979ba5;">
                {{ t('实时调度') }}
              </span>
            </bk-radio>
          </bk-radio-group>
        </bk-form-item>
        <template v-if="formData.configs.data_source.source_type !== 'stream_source'">
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
              style="margin-bottom: 12px;">
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
              style="margin-bottom: 12px;">
              <bk-select
                v-model="formData.configs.schedule_config.schedule_period"
                class="schedule-select"
                :clearable="false"
                style="width: 68px;">
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
  import { h, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';

  import ExpectedResults from './components/expected-results/index.vue';
  import RulesComponent from './components/rules/index.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import LinkDataDetailComponent from './components/scheme-input/link-table/detail.vue';
  import LinkDataComponent from './components/scheme-input/link-table/index.vue';
  import OtherDataComponent from './components/scheme-input/other.vue';
  import ResourceDataComponent from './components/scheme-input/resource-data.vue';

  import useRequest from '@/hooks/use-request';

  interface Where {
    connector: 'and' | 'or' ;
    conditions: Array<{
      connector: 'and' | 'or';
      conditions: Array<{
        condition: {
          field: DatabaseTableFieldModel | '';
          filter: string;
          filters: string[];
          operator: string,
        }
      }>
    }>;
  }
  interface IFormData {
    configs: {
      data_source: {
        system_ids: string[],
        source_type: string,
        rt_id: string | string[]
        link_table: {
          uid: string,
          version: number,
        },
      },
      config_type: string,
      select: Array<DatabaseTableFieldModel>,
      where: Where,
      schedule_config: {
        count_freq: string,
        schedule_period: string,
      },
    },
  }
  interface Emits {
    (e: 'updateFormData', value: IFormData): void;
  }
  interface Expose {
    getFields: () => IFormData
  }
  interface Props {
    editData: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const configRef = ref();
  const rulesComponentRef = ref();
  const expectedResultsRef = ref();
  const linkDataDetail = ref<LinkDataDetailModel>(new LinkDataDetailModel());

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const configTypeMap: Record<string, any> = {
    EventLog: EventLogComponent,
    BuildIn: ResourceDataComponent,
    BizRt: OtherDataComponent,
    LinkTable: LinkDataComponent,
  };

  const initDataSource = ref<IFormData['configs']['data_source']>({
    system_ids: [],
    source_type: 'batch_join_source',
    rt_id: [],
    link_table: {
      uid: '',
      version: 0,
    },
  });

  const formData = ref<IFormData>({
    configs: {
      data_source: {
        system_ids: [],
        source_type: 'batch_join_source',
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
      schedule_config: {
        count_freq: '',
        schedule_period: 'hour',
      },
    },
  });
  const ruleAuditConfigType = ref<Array<Record<string, any>>>([]);
  const aggregateList = ref<Array<Record<string, any>>>([]);
  const configType = ref('');
  const tableFields = ref<Array<DatabaseTableFieldModel>>([]);

  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess() {
      ruleAuditConfigType.value = commonData.value.rule_audit_config_type;
      aggregateList.value = commonData.value.rule_audit_aggregate_type;
      aggregateList.value = aggregateList.value.concat([{
        label: t('不聚和'),
        value: null,
      }]);
    },
  });

  // 获取tableid
  const {
    data: tableData,
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  const setTableFields = (data: Array<{
    field_type: string,
    label: string,
    value: string,
  }>, displayOrRtId: string) => data.map(item => ({
    table: displayOrRtId, // 别名，单表时为rt_id
    raw_name: item.value,
    display_name: item.label,
    field_type: item.field_type,
    aggregate: null,
    remark: '',
  }));

  // 获取表字段
  const fetDatabaseTableFields = (rtId: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: rtId,
    }).then((data) => {
      tableFields.value = setTableFields(data, rtId);
    });
  };

  // 获取联表表字段
  const fetchLinkTableFields = async (rtIdArr: string[][], rtIdArrDisplay: string[][]) => {
    // rt_id
    const idArr = Array.from(new Set(rtIdArr.reduce((acc, curr) => acc.concat(curr), [])));
    // 别名
    const displayArr = Array.from(new Set(rtIdArrDisplay.reduce((acc, curr) => acc.concat(curr), [])));
    StrategyManageService.fetchBatchTableRtFields({
      table_ids: idArr.join(','),
    }).then((data) => {
      tableFields.value = [];
      data.forEach((item, index) => {
        tableFields.value.push(...setTableFields(item.fields, displayArr[index]));
      });
    });
  };

  const createInfoBoxConfig = (overrides: {onConfirm: () => void, onClose: () => void}): any => ({
    type: 'warning',
    title: t('切换数据源请注意'),
    subTitle: () => h('div', {
      style: {
        color: '#4D4F56',
        backgroundColor: '#f5f6fa',
        padding: '12px 16px',
        borderRadius: '2px',
        fontSize: '14px',
        textAlign: 'left',
      },
    }, t('切换后，已配置的数据将被清空。是否继续？')),
    confirmText: t('继续切换'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    ...overrides,
  });

  // 切换数据源类型： 默认使用离线模式batch_join_source，不切换类型
  const handleDataSourceType = (item: string) => {
    if (formData.value.configs.config_type === '') {
      formData.value.configs.config_type = item;
      if (item !== '' && item !== 'LinkTable') {
        fetchTable({
          table_type: item,
        });
      }
      return;
    }
    InfoBox(createInfoBoxConfig({
      onConfirm() {
        formData.value.configs.config_type = item;
        // 重置数据
        formData.value.configs.data_source = {
          ...formData.value.configs.data_source,
          ...initDataSource.value,
        };
        formData.value.configs.select = [];
        formData.value.configs.where = {
          connector: 'and',
          conditions: [],
        };
        tableFields.value = [];
        configRef.value.resetFormData();
        rulesComponentRef.value.resetFormData();
        expectedResultsRef.value.resetFormData();
        if (item !== '' && item !== 'LinkTable') {
          fetchTable({
            table_type: item,
          });
        }
      },
      onClose() {
        configType.value = formData.value.configs.config_type;
      },
    }));
  };

  // 更新数据源后，获取对应表字段
  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    if (!dataSource.rt_id || !dataSource.rt_id.length || (dataSource.link_table && !dataSource.link_table.uid)) {
      tableFields.value = [];
    }
    if (!formData.value.configs.data_source.rt_id
      || !formData.value.configs.data_source.rt_id.length
      || (formData.value.configs.config_type === 'LinkTable' && formData.value.configs.data_source.link_table && !formData.value.configs.data_source.link_table.uid)) {
      formData.value.configs.data_source = {
        ...formData.value.configs.data_source,
        ...dataSource,
      };
    } else if (Array.isArray(dataSource.rt_id)
      ? formData.value.configs.data_source.rt_id !== dataSource.rt_id[dataSource.rt_id.length - 1]
      : formData.value.configs.data_source.rt_id !== dataSource.rt_id) {
      InfoBox(createInfoBoxConfig({
        onConfirm() {
          formData.value.configs.select = [];
          formData.value.configs.where = {
            connector: 'and',
            conditions: [],
          };
          rulesComponentRef.value.resetFormData();
          expectedResultsRef.value.resetFormData();
          formData.value.configs.data_source = {
            ...formData.value.configs.data_source,
            ...dataSource,
          };
        },
        onClose() {
          configRef.value.setConfigs(formData.value.configs);
        },
      }));
    } else {
      formData.value.configs.data_source = {
        ...formData.value.configs.data_source,
        ...dataSource,
      };
    }
  };

  // 更新预期数据
  const handleUpdateExpectedResult = (expectedResult: Array<DatabaseTableFieldModel>) => {
    formData.value.configs.select = expectedResult;
  };

  // 更新风险规则
  const handleUpdateWhere = (where: Where) => {
    formData.value.configs.where = where;
  };

  // 获取联表详情
  const handleUpdateLinkDataDetail = (detail: LinkDataDetailModel) => {
    linkDataDetail.value = detail;
    // 表id
    // eslint-disable-next-line max-len
    const rtIdArr = linkDataDetail.value.config.links.map(item => [item.left_table.rt_id, item.right_table.rt_id]) as string[][];
    // 表别名
    // eslint-disable-next-line max-len
    const rtIdArrDisplay =  linkDataDetail.value.config.links.map(item => [item.left_table.display_name, item.right_table.display_name]) as string[][];
    if (rtIdArr.length) {
      // 联表获取表字段
      fetchLinkTableFields(rtIdArr, rtIdArrDisplay);
    }
  };

  // 刷新联表详情
  const handleRefreshLinkData = () => {
    configRef.value?.refreshLinkData();
    // 重置数据
    formData.value.configs.select = [];
    formData.value.configs.where = {
      connector: 'and',
      conditions: [],
    };
    rulesComponentRef.value.resetFormData();
    expectedResultsRef.value.resetFormData();
  };

  const handleSourceTypeChange = (type: string) => {
    if (type === 'stream_source') {
      formData.value.configs.schedule_config = {
        count_freq: '',
        schedule_period: 'hour',
      };
    }
  };

  // 编辑
  const  setFormData = (editData: StrategyModel) => {
    configType.value = editData.configs.config_type || '';
    formData.value.configs.config_type = editData.configs.config_type || '';
    formData.value.configs.schedule_config = editData.configs.schedule_config;
    formData.value.configs.select = editData.configs.select;
    expectedResultsRef.value.setSelect(editData.configs.select);
    rulesComponentRef.value.setWhere(editData.configs.where);
    if (editData.configs.data_source) {
      formData.value.configs.data_source = editData.configs.data_source;
    }
    if (formData.value.configs.config_type !== 'LinkTable') {
      fetchTable({
        table_type: formData.value.configs.config_type,
      }).then(() => {
        configRef.value.setConfigs(editData.configs);
      });
    } else {
      nextTick(() => {
        configRef.value.setConfigs(editData.configs);
      });
    }
  };

  watch(() => formData.value, (data) => {
    emits('updateFormData', data);
  }, {
    deep: true,
  });

  // 日志、资源数据、其他数据获取表字段
  watch(() => formData.value.configs.data_source.rt_id, (rtId) => {
    if (rtId && rtId.length) {
      const rtId = formData.value.configs.data_source.rt_id;
      fetDatabaseTableFields(Array.isArray(rtId) ? rtId[rtId.length - 1] : rtId);
    }
  });

  watch(() => props.editData, (data) => {
    if (isEditMode || isCloneMode) {
      setFormData(data);
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
          rt_id: (_.isArray(tableIdList) ?  _.last(tableIdList)  : tableIdList) as string,
        };
      }
      // 如果select为空数组，传全部
      if (params.configs.select && params.configs.select.length === 0) {
        params.configs.select = tableFields.value.map(item => ({
          ...item,
          aggregate: null,
          display_name: `${item.display_name}${item.aggregate ? `_${item.aggregate}` : ''}`,
        }));
        expectedResultsRef.value.setSelect(params.configs.select);
      }
      return params;
    },
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
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;

      :deep(.bk-form-item) {
        margin-bottom: 0;
      }
    }

    :deep(.bk-infobox-title) {
      margin-top: 0;
    }
  }

  .dispatch-wrap {
    padding: 16px 24px;

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
