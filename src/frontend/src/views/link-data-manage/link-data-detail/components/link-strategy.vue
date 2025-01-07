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
  <div class="link-data-strategy">
    <bk-alert
      theme="warning"
      :title="t('联表已更新，请前往关联的策略进行刷新升级。')" />
    <render-list
      ref="listRef"
      class="audit-highlight-table"
      :columns="tableColumn"
      :data-source="dataSource"
      style="margin-top: 16px" />
  </div>
</template>
<script setup lang="tsx">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  interface Props {
    data: LinkDataDetailModel,
    strategyTagMap: Record<string, string>,
    maxVersionMap: Record<string, number>
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const router = useRouter();
  const listRef = ref();
  const dataSource = StrategyManageService.fetchStrategyList;
  const statusMap = ref<Record<string, string>>({});

  const tableColumn = ref([
    {
      label: () => t('策略ID'),
      field: () => 'strategy_id',
      fixed: 'left',
      width: 120,
    },
    {
      label: () => t('策略名称'),
      fixed: 'left',
      field: () => 'strategy_name',
      render: ({ data }: { data: StrategyModel}) => <bk-badge
          class='edit-badge'
          position="top-right"
          theme="danger"
          visible={data.link_table_version >= (props.maxVersionMap[data.link_table_uid] || 1)}
          dot
      >
        <a
            v-bk-tooltips={{
              content: t('策略使用的方案，有新版本待升级'),
              disabled: data.link_table_version >= (props.maxVersionMap[data.link_table_uid] || 1),
            }}
            onClick={() => handleDetail(data)}>
          {data.strategy_name}
        </a>
      </bk-badge>,
    },
    {
      label: () => t('标签'),
      field: () => 'tags',
      minWidth: 230,
      render: ({ data }: { data: StrategyModel }) => {
        const tags = data.tags.map(item => props.strategyTagMap[item] || item);
        return <EditTag data={tags} key={data.strategy_id} />;
      },
    },
    {
      label: () => t('状态'),
      field: () => 'status',
      width: '170px',
      render: ({ data }: { data: StrategyModel }) => {
        if (!data.isFailed) {
          if (data.isPending) {
            return <p
                style='display: flex; align-items: center;'>
              <audit-icon
                  class="rotate-loading mr4"
                  svg
                  type='loading' />
              <span v-bk-tooltips={{
                content: t('创建数据处理链路中，预计10分钟后策略正式运行'),
                disabled: !['pending', 'starting', 'updating'].includes(data.status),
              }}>  {statusMap.value[data.status] || data.status} </span>
            </p>;
          }
          return <p style='display: flex; align-items: center;max-width: 200px;'>
            <audit-icon
                svg
                class='mr4'
                type={data.statusTag} />
            {statusMap.value[data.status] || data.status}
          </p>;
        }
        // failed
        if (data.status_msg) {
          return <p style='display: flex; align-items: baseline;'>
            <audit-icon
                class='mr4'
                svg
                type={data.statusTag} />
            <span
                style='border-bottom:1px dashed #C4C6CC;height: 32px;cursor: pointer;'
                v-bk-tooltips={data.status_msg}>
              {statusMap.value[data.status] || data.status}
            </span>
          </p>;
        }
        return <div style='display: flex; align-items: center;'>
          <audit-icon
              svg
              class='mr4'
              type={data.statusTag} />
          <span>{statusMap.value[data.status] || data.status}</span>
        </div>;
      },
    },
  ]);

  useRequest(StrategyManageService.fetchStrategyCommon, {
    manual: true,
    defaultValue: new CommonDataModel(),
    onSuccess(data) {
      statusMap.value = data.strategy_status.reduce((res: Record<string, string>, item: {
        label: string;
        value: string
      }) => {
        res[item.value] = item.label;
        return res;
      }, {});
    },
  });

  const handleDetail = (data: StrategyModel) => {
    const to = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: data.strategy_id,
      },
    });
    window.open(to.href, '_blank');
  };

  onMounted(() => {
    listRef.value.fetchData({
      link_table_uid: props.data.uid,
    });
  });
</script>
<style scoped lang="postcss">
.link-data-strategy {
  padding: 0 25px;
}
</style>
