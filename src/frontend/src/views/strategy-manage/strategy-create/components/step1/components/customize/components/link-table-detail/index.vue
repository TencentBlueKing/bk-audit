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
  <div
    v-if="linkDataDetail.config?.links && linkDataDetail.config.links.length"
    class="link-data-detail">
    <bk-alert
      v-if="!(linkDataDetail.version >= (linkTableMaxVersionMap[linkDataDetail.uid] || 1))"
      theme="warning">
      <template #title>
        {{ t('该联表数据有更新，请确认是否刷新同步') }}
        <bk-button
          style="margin: 0 16px;"
          text
          theme="primary"
          @click="handleRefreshLinkData">
          {{ t('刷新') }}
        </bk-button>
        <router-link
          target="_blank"
          :to="{
            name: 'linkDataManage',
            query: {
              uid: linkDataDetail.uid,
            },
          }">
          {{ t('前往查看详情') }}
        </router-link>
      </template>
    </bk-alert>
    <div class="detail-wrapper">
      <div style="display: flex; justify-content: space-between;">
        <div>
          <span>{{ t('联表预览') }}</span>
          <audit-icon
            v-bk-tooltips="{
              content: t('联表中，将自动生成各个原始表的字母别名，用于后续选择字段的简略标识'),
              extCls:'link-data-detail-tooltips'
            }"
            style=" margin-left: 9px; font-size: 14px;color: #c4c6cc; cursor: pointer;"
            type="help-fill" />
        </div>
        <div class="operation">
          <span>{{ t('找不到合适的数据？') }}</span>
          <bk-button
            style="margin: 0 16px;"
            text
            theme="primary"
            @click="create">
            <audit-icon
              style="margin-right: 5px; color: #3a84ff;"
              type="add-fill" />
            <span> {{ t('立即新建联表') }}</span>
          </bk-button>
          <router-link
            target="_blank"
            :to="{
              name: 'linkDataManage',
            }">
            <audit-icon
              style="margin-right: 5px; color: #3a84ff;"
              type="jump-link" />
            <span> {{ t('前往联表管理') }}</span>
          </router-link>
        </div>
      </div>
      <div
        v-for="(item, index) in linkDataDetail.config.links"
        :key="index"
        style="margin-bottom: 10px;">
        <div class="detail-table">
          <div class="detail-table-head">
            <div class="left-name">
              <span
                style="
                  color: #3a84ff;
                  background: #f0f1f5;
                  border-radius: 2px;">
                {{ item.left_table.display_name }}
              </span>
              <span style="margin-left: 5px;">{{ commonData.link_table_table_type.
                find(tableType => tableType.value === item.left_table.table_type)?.label }}/</span>
              <span>{{ getDataSourceText(item.left_table) }}</span>
            </div>
            <div
              v-bk-tooltips="joinTypeList.find(type => type.value === item.join_type)?.label || item.join_type"
              class="join-type">
              <relation-ship
                :join-type="item.join_type"
                type="gray" />
            </div>
            <div class="right-name">
              <span
                style="
                  color: #3a84ff;
                  background: #f0f1f5;
                  border-radius: 2px;">
                {{ item.right_table.display_name }}
              </span>
              <span style="margin-left: 5px;">{{ commonData.link_table_table_type.
                find(tableType => tableType.value === item.right_table.table_type)?.label }}/</span>
              <span>{{ getDataSourceText(item.right_table) }}</span>
            </div>
          </div>
          <template
            v-for="(field, fieldIndex) in item.link_fields"
            :key="fieldIndex">
            <div class="detail-table-body">
              <div class="left-field">
                {{ field.left_field.display_name }}
              </div>
              <div style="width: 40px; text-align: center;">
                =
              </div>
              <div class="right-field">
                {{ field.right_field.display_name }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
    <create-link-data
      ref="createRef" />
  </div>
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { h, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';

  import AuditIcon from '@components/audit-icon';

  import CreateLinkData from '@views/link-data-manage/link-data-create/index.vue';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'refreshLinkData'): void;
  }
  interface Props {
    linkDataDetail: LinkDataDetailModel
    joinTypeList: Array<Record<string, any>>
  }
  interface TableData {
    label: string;
    value: string;
    children: Array<{
      label: string;
      value: string;
    }>;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const createRef = ref();
  const linkTableMaxVersionMap = ref<Record<string, number>>({});
  const tableTypeData = ref<Record<'BizRt' | 'BuildIn' | 'EventLog', Array<TableData>>>({
    BizRt: [],
    BuildIn: [],
    EventLog: [],
  });
  const uniqueTableTypes = ref<Array<'BizRt' | 'BuildIn' | 'EventLog'>>([]);

  const fetchTableTypeData = () => {
    // 获取tableData
    for (const type of uniqueTableTypes.value) {
      StrategyManageService.fetchTable({
        table_type: type,
      }).then((data) => {
        tableTypeData.value[type] = data;
      });
    }
  };

  const extractUniqueTableTypes = (links: LinkDataDetailModel['config']['links']) => {
    const tableTypes = new Set();
    links.forEach((link) => {
      if (link.left_table && link.left_table.table_type) {
        tableTypes.add(link.left_table.table_type);
      }
      if (link.right_table && link.right_table.table_type) {
        tableTypes.add(link.right_table.table_type);
      }
    });
    return Array.from(tableTypes) as Array<'BizRt' | 'BuildIn' | 'EventLog'>;
  };

  // 获取全部联表版本信息
  useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      linkTableMaxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  // 获取系统
  const {
    data: systemList,
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
  });

  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });

  const findLabelByValue = (data: Array<{
    label: string,
    value: string,
    children?: Array<{
      label: string,
      value: string,
    }>
  }>, searchValue = '', parentLabel = '') => {
    for (const item of data) {
      // 如果当前项的值匹配，返回当前项的标签
      if (item.value === searchValue) {
        return parentLabel ? `${parentLabel}/${item.label}` : item.label;
      }

      // 如果有子项，递归搜索
      if (item.children && item.children.length) {
        const result: string = findLabelByValue(item.children, searchValue, item.label);
        if (result) {
          return result;
        }
      }
    }
    return '';
  };

  const getDataSourceText = (table: LinkDataDetailModel['config']['links'][0]['left_table']) => {
    if (table.table_type === 'BuildIn' || table.table_type === 'BizRt') {
      return findLabelByValue(tableTypeData.value[table.table_type], table.rt_id as string);
    }
    const names = systemList.value
      .filter(item => table.system_ids?.includes(item.id))
      .map(item => item.name);
    // 使用 ' + ' 连接名称
    return names.join(' + ');
  };

  const create = () => {
    createRef.value.show();
  };

  const handleRefreshLinkData = () => {
    InfoBox({
      type: 'warning',
      title: t('刷新数据源请注意'),
      subTitle: () => h('div', {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          height: '46px',
          lineHeight: '46px',
          borderRadius: '2px',
          fontSize: '14px',
        },
      }, t('刷新后，已配置的数据将被清空。是否继续？')),
      confirmText: t('继续刷新'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        emit('refreshLinkData');
      },
    });
  };

  watch(
    () => props.linkDataDetail.config?.links,
    (newLinks: LinkDataDetailModel['config']['links']) => {
      if (newLinks) {
        // 获取系统
        fetchSystemWithAction();
        uniqueTableTypes.value = extractUniqueTableTypes(newLinks);
        fetchTableTypeData();
      }
    },
    { immediate: true },
  );
</script>
<style scoped lang="postcss">
.link-data-detail {
  margin-top: 8px;

  .detail-wrapper {
    padding: 16px;
    margin-top: 8px;
    background-color: #f5f7fa;

    .detail-table {
      display: flex;
      flex-direction: column;
    }

    .detail-table-head,
    .detail-table-body {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 8px;
      flex: 1;

      .right-name,
      .left-name {
        padding: 5px 8px;
        background-color: #eaebf0;
        border: 1px solid #dcdee5;
      }

      .right-field,
      .left-field {
        padding: 5px 8px;
        background-color: #fff;
        border: 1px solid #dcdee5;
      }

      .join-type {
        display: flex;
        height: 80%;
        padding: 0 5px;
        margin: auto;
        background-color: #e1ecff;
        align-items: center
      }
    }
  }
}
</style>
<style>
.link-data-detail-tooltips {
  width: 286px;
  word-wrap: break-word;
}
</style>
