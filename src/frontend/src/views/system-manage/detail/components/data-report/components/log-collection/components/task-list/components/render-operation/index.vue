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
  <div class="collector-operation">
    <auth-component
      action-id="view_collection_v2_bk_log"
      class="operation-btn"
      :permission="data.permission.view_collection_v2_bk_log"
      :resource="data.collector_config_id">
      <audit-icon
        v-bk-tooltips="t('查看')"
        class="operation-icon"
        type="audit"
        @click.stop="handleDetail" />
    </auth-component>
    <auth-component
      action-id="manage_collection_v2_bk_log"
      class="operation-btn"
      :permission="data.permission.manage_collection_v2_bk_log"
      :resource="data.collector_config_id">
      <audit-icon
        v-bk-tooltips="t('编辑')"
        class="operation-icon"
        type="edit-fill"
        @click.stop="handleEdit" />
    </auth-component>
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
  <bk-sideslider
    v-model:isShow="isShowDetail"
    :title="t('节点管理特殊采集任务')"
    :width="960">
    <template #default>
      <div class="check-detail-content">
        <!-- 基本信息 -->
        <edit-info
          :data="data"
          :status="collectorTaskStatus"
          width="50%"
          @change="handleType" />
        <!-- 采集状态 -->
        <delivery-info
          :data="data"
          :environment="environment"
          @get-status="handleGetCollectorTaskStatus" />
      </div>
    </template>
  </bk-sideslider>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import type CollectorModel from '@model/collector/collector';
  import type ContentModel from '@model/collector/task-status';

  import useRequest from '@hooks/use-request';

  import DeliveryInfo from './delivery-info/index.vue';
  import EditInfo from './edit-info/index.vue';

  interface Props {
    data: CollectorModel;
  }
  interface Emits {
    (e: 'getCollectorLists'): void
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const environment = ref<string|null>(''); // 容器环境
  const { t } = useI18n();

  const router = useRouter();
  const route = useRoute();
  const isShowDetail = ref(false);
  const collectorTaskStatus = ref<ContentModel|undefined>();

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

  const handleDetail = () => {
    isShowDetail.value = true;
  };
  const handleType = (value: string) => {
    environment.value = value;
  };
  const handleEdit = () => {
    router.push({
      name: 'collectorEdit',
      params: {
        systemId: route.params.id,
        collectorConfigId: props.data.collector_config_id,
      },
    });
  };

  const handleDelete = () => deleteCollector({
    collector_config_id: props.data.collector_config_id,
  });

  const handleGetCollectorTaskStatus = (value: any) => {
    collectorTaskStatus.value = value;
  };
</script>
<style lang="postcss" scoped>
  .collector-operation {
    display: flex;
    padding-right: 12px;
    margin-left: auto;
    font-size: 12px;
    color: #979ba5;
    flex-wrap: nowrap;

    .operation-btn {
      padding-left: 18px;

      .operation-icon {
        font-size: 16px;
      }

      .operation-icon:hover {
        color: #3a84ff;
      }
    }
  }

  .check-detail-content {
    height: calc(100vh - 114px);
    padding: 22px 40px;
  }
</style>
