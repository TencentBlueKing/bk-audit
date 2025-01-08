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
                :disabled="isEditMode || isCloneMode || isUpgradeMode"
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
            :link-data-detail="linkDataDetail"
            :link-data-sheet-id="formData.configs.data_source.link_table.uid"
            @refresh-link-data="handleRefreshLinkData" />
        </bk-form-item>
        <bk-form-item
          :label="t('预期结果')"
          label-width="160"
          property="control_id">
          <expected-results
            :aggregate-list="aggregateList"
            :table-fields="tableFields"
            @update-expected-result="handleUpdateExpectedResult" />
        </bk-form-item>
        <bk-form-item
          :label="t('风险发现规则')"
          label-width="160"
          property="configs.where"
          required>
          <rules-component
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
              property="configs.aiops_config.count_freq"
              style="margin-bottom: 12px;">
              <bk-input
                v-model="formData.configs.aiops_config.count_freq"
                class="schedule-input"
                :min="1"
                onkeypress="return( /[\d]/.test(String.fromCharCode(event.keyCode) ) )"
                :placeholder="t('请输入')"
                type="number" />
            </bk-form-item>
            <bk-form-item
              class="is-required no-label"
              label-width="0"
              property="configs.aiops_config.schedule_period"
              style="margin-bottom: 12px;">
              <bk-select
                v-model="formData.configs.aiops_config.schedule_period"
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
  import { h, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import AuditIcon from '@components/audit-icon';

  import ExpectedResults from './components/expected-results/index.vue';
  import RulesComponent from './components/rules/index.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import LinkDataDetailComponent from './components/scheme-input/link-table/detail.vue';
  import LinkDataComponent from './components/scheme-input/link-table/index.vue';
  import OtherDataComponent from './components/scheme-input/other.vue';
  import ResourceDataComponent from './components/scheme-input/resource-data.vue';

  import useRequest from '@/hooks/use-request';

  interface Where {
    operator: 'and' | 'or' ;
    conditions: Array<{
      operator: 'and' | 'or';
      conditions: Array<{
        field: DatabaseTableFieldModel | '';
        operation: string;
        filter: string;
        filters: string[];
      }>
    }>;
  }
  interface IFormData {
    configs: {
      data_source: {
        system_id: string[],
        source_type: string,
        rt_id: string | string[]
        link_table: {
          uid: number,
          version: string,
        },
      },
      config_type: string,
      select: Array<DatabaseTableFieldModel>,
      where: Where,
      aiops_config: {
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

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const configRef = ref();
  const linkDataDetail = ref<LinkDataDetailModel>(new LinkDataDetailModel());

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';

  const configTypeMap: Record<string, any> = {
    EventLog: EventLogComponent,
    BuildIn: ResourceDataComponent,
    BizRt: OtherDataComponent,
    LinkTable: LinkDataComponent,
  };

  const initDataSource = ref<IFormData['configs']['data_source']>({
    system_id: [],
    source_type: 'batch_join_source',
    rt_id: [],
    link_table: {
      uid: 0,
      version: '',
    },
  });

  const formData = ref<IFormData>({
    configs: {
      data_source: {
        system_id: [],
        source_type: 'batch_join_source',
        rt_id: [],
        link_table: {
          uid: 0,
          version: '',
        },
      },
      config_type: '',
      select: [],
      where: {
        operator: 'and',
        conditions: [],
      },
      aiops_config: {
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
      aggregateList.value = commonData.value.rule_audit_aggregate_type.concat([{
        label: '不聚和',
        value: 'null',
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

  // 获取表字段
  const {
    run: fetDatabaseTableFields,
  } = useRequest(StrategyManageService.fetchTableRtFields, {
    defaultValue: [],
    onSuccess: (data) => {
      const rtId = formData.value.configs.data_source.rt_id;
      tableFields.value = data.map(item => ({
        table: Array.isArray(rtId) ? rtId[rtId.length - 1] : rtId,
        raw_name: item.value,
        display_name: item.label,
        type: item.field_type,
        aggregate: '',
        remark: '',
      }));
    },
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
    InfoBox({
      title: () =>  h('div', [
        h(AuditIcon, {
          type: 'alert',
          style: {
            fontSize: '42px',
            color: '#FFF8C3',
          },
        }),
        h('div', t('切换数据源请注意')),
      ]),
      subTitle: t('切换后，已配置的数据将被清空。是否继续？'),
      confirmText: t('继续切换'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        formData.value.configs.config_type = item;
        // 重置数据
        formData.value.configs.data_source = {
          ...formData.value.configs.data_source,
          ...initDataSource.value,
        };
        if (item !== '' && item !== 'LinkTable') {
          fetchTable({
            table_type: item,
          });
        }
      },
      onClose() {
        configType.value = formData.value.configs.config_type;
      },
    });
  };

  // 更新数据源后，获取对应表字段
  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...dataSource,
    };
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
  };

  // 刷新联表详情
  const handleRefreshLinkData = () => {
    configRef.value?.refreshLinkData();
  };

  const handleSourceTypeChange = (type: string) => {
    if (type === 'stream_source') {
      formData.value.configs.aiops_config = {
        count_freq: '',
        schedule_period: 'hour',
      };
    }
    // 非周期不需要aiops_config
    formData.value.configs.data_source.source_type !== 'stream_source'
      ? formData.value.configs.aiops_config
      : undefined;
  };

  watch(() => formData.value, (data) => {
    emits('updateFormData', data);
  }, {
    deep: true,
  });

  watch(() => formData.value.configs.data_source.rt_id, (rtId) => {
    if (rtId) {
      fetDatabaseTableFields({
        table_id: Array.isArray(rtId) ? rtId[rtId.length - 1] : rtId,
      });
    }
  });

  defineExpose<Expose>({
    // 获取提交参数
    getFields() {
      return formData.value;
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
