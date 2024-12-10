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
    <bk-form-item
      label=""
      label-width="0"
      required>
      <auth-collapse-panel
        is-active
        :label="t('规则配置')"
        style="margin-bottom: 14px;">
        <div class="customize-rule">
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
                v-model="formData.configs.config_type"
                :disabled="isEditMode || isCloneMode || isUpgradeMode"
                filterable
                :placeholder="t('请选择数据源类型')"
                @change="handleDataSourceType">
                <bk-option
                  v-for="item in customizeTableTypeList"
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
            :link-data-sheet-id="formData.configs.data_source.link_data_sheet_id"
            @handle-refresh-link-data="handleRefreshLinkData" />
        </div>
      </auth-collapse-panel>
    </bk-form-item>
  </div>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';

  import EventLogComponent from './components/scheme-input/event-log.vue';
  import LinkDataDetailComponent from './components/scheme-input/link-table/detail.vue';
  import LinkDataComponent from './components/scheme-input/link-table/index.vue';
  import OtherDataComponent from './components/scheme-input/other.vue';
  import ResourceDataComponent from './components/scheme-input/resource-data.vue';

  import useRequest from '@/hooks/use-request';

  interface IFormData {
    configs: {
      data_source: {
        system_id: string[],
        source_type: string,
        result_table_id: string[]
        data_sheet_id: string,
        link_data_sheet_id: string,
      },
      config_type: string,
    },
  }
  interface Emits {
    (e: 'updateFormData', value: IFormData): void;
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
    OtherData: OtherDataComponent,
    LinkData: LinkDataComponent,
  };

  const initDataSource = ref<IFormData['configs']['data_source']>({
    system_id: [],
    source_type: 'batch_join_source',
    result_table_id: [],
    data_sheet_id: '',
    link_data_sheet_id: '',
  });

  const formData = ref<IFormData>({
    configs: {
      data_source: {
        system_id: [],
        source_type: 'batch_join_source',
        result_table_id: [],
        data_sheet_id: '',
        link_data_sheet_id: '',
      },
      config_type: '',
    },
  });
  const customizeTableTypeList = ref<Array<Record<string, any>>>([]);

  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess() {
      customizeTableTypeList.value = commonData.value.customize_table_type || [
        {
          label: '操作记录',
          value: 'EventLog',
          config: {
            table_type: 'EventLog',
            source_type: 'stream_source',
          },
        },
        {
          label: '资源数据',
          value: 'BuildIn',
          config: {
            table_type: 'BuildIn',
            source_type: 'batch_join_source',
          },
        },
        {
          label: '其他数据',
          value: 'OtherData',
          config: {
            table_type: 'OtherData',
            source_type: 'batch_join_source',
          },
        },
        {
          label: '联表数据',
          value: 'LinkData',
          config: {
            table_type: 'LinkData',
            source_type: 'batch_join_source',
          },
        },
      ];
    },
  });

  // 获取tableid
  const {
    data: tableData,
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  // 切换数据源类型： 默认使用离线模式batch_join_source，不切换类型
  const handleDataSourceType = (item: boolean | string | number) => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...initDataSource.value,
    };
    if (item !== '') {
      fetchTable({
        table_type: item,
      });
    }
  };

  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...dataSource,
    };
  };

  const handleUpdateLinkDataDetail = (detail: LinkDataDetailModel) => {
    linkDataDetail.value = detail;
  };

  const handleRefreshLinkData = () => {
    configRef.value?.refreshLinkData();
  };

  watch(() => formData.value, (data) => {
    emits('updateFormData', data);
  }, {
    deep: true,
  });
</script>
<style scoped lang="postcss">
.strategy-customize {
  .customize-rule {
    padding: 16px 32px 24px;

    .label-is-required::after {
      position: absolute;
      width: 14px;
      line-height: 32px;
      color: #ea3636;
      text-align: center;
      content: '*';
    }

    .select-group {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;

      :deep(.bk-form-item) {
        margin-bottom: 8px;
      }

      .no-label .bk-form-label::after {
        content: '';
      }

      .no-label .bk-form-label {
        padding-right: 0;
      }
    }
  }
}
</style>
