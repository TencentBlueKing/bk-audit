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
  <div class="collector-detail">
    {{ t('采集下发中') }},
    <span
      class="check-detail"
      @click.stop="handleDetail"> {{ t('查看详情') }}</span>
    <auth-component
      action-id="manage_collection_v2_bk_log"
      class="operation-btn"
      :permission="data.permission.manage_collection_v2_bk_log"
      :resource="data.collector_config_id">
      <audit-popconfirm
        :confirm-handler="handleDelete"
        :content="t('删除后将不可找回')"
        :title="t('确认删除采集日志？')">
        <audit-icon
          v-bk-tooltips="t('删除')"
          class="operation-icon"
          type="delete" />
      </audit-popconfirm>
    </auth-component>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import type CollectorModel from '@model/collector/collector';

  import useRequest from '@hooks/use-request';

  interface Props {
    data: CollectorModel;
  }

  interface Emits {
    (e: 'getCollectorLists'): void
  }
  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  const router = useRouter();
  const route = useRoute();

  const handleDetail = () => {
    router.push({
      name: 'collectorEdit',
      params: {
        systemId: route.params.id,
        collectorConfigId: props.data.collector_config_id,
      },
    });
  };

  /**
   * 删除采集接口
   */
  const {
    run: deleteCollector,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.deleteCollector, {
    defaultParams: {
      collector_config_id: props.data.collector_config_id,
    },
    defaultValue: {},
    onSuccess: () => {
      emit('getCollectorLists');
    },
  });

  const handleDelete = () => deleteCollector({
    collector_config_id: props.data.collector_config_id,
  });

</script>
<style lang="postcss" scoped>
  .collector-detail {
    .check-detail {
      color: #3a84ff;
    }

    .operation-icon {
      margin-left: 18px;
      font-size: 16px;
    }
  }
</style>
