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
    v-if="!loading"
    class="collector-config">
    <!-- {{ t('采集已完成') }},
    <auth-component
      action-id="edit_system"
      class="operation-btn"
      :permission="dataCheckMap.edit_system"
      :resource="data.bk_data_id">
      <span
        class="route-config"
        @click.stop="handleConfig">{{ t('立即配置') }}</span>
    </auth-component> -->
    <auth-component
      action-id="edit_system"
      class="operation-btn"
      :permission="dataCheckMap.edit_system"
      :resource="data.bk_data_id">
      <audit-popconfirm
        :confirm-handler="handleDelete"
        :content="t('删除后不可直接找回，需要重新接入')"
        :title="t('确认删除采集任务？')">
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

  // import {
  //   useRoute,
  //   useRouter,
  // } from 'vue-router';
  import DataIdManageService from '@service/dataid-manage';
  import IamManageService from '@service/iam-manage';

  import type CollectorModel from '@model/collector/collector';

  import useRequest from '@hooks/use-request';


  const props = defineProps<Props>();

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  interface Props {
    data: CollectorModel;
  }
  interface Emits {
    (e: 'getCollectorLists'): void
  }
  // const router = useRouter();
  // const route = useRoute();

  const {
    loading,
    data: dataCheckMap,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(IamManageService.check, {
    defaultValue: {},
    defaultParams: {
      action_ids: 'edit_system',
      resources: props.data.system_id,
    },
    manual: true,
  });

  // const {
  //   run: fecthDetail,
  // } = useRequest(DataIdManageService.fecthDetail, {
  //   defaultValue: null,
  //   onSuccess: () => {
  //     router.push({
  //       name: 'dataIdEdit',
  //       params: {
  //         systemId: route.params.id,
  //         bkDataId: props.data.bk_data_id,
  //       },
  //       query: {
  //         step: 3,
  //       },
  //     });
  //   },
  // });

  /**
   * 删除采集接口
   */
  const {
    run: deleteDataId,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(DataIdManageService.deleteDataId, {
    defaultParams: {
      bk_data_id: props.data.bk_data_id,
    },
    defaultValue: {},
    onSuccess: () => {
      emit('getCollectorLists');
    },
  });

  const handleDelete = () => deleteDataId({
    bk_data_id: props.data.bk_data_id,
  });

  // const handleConfig = () => {
  //   fecthDetail({
  //     bk_data_id: props.data.bk_data_id,
  //   });
  // };
</script>
<!-- .route-config::after {
    position: absolute;
    right: -6px;
    width: 6px;
    height: 6px;
    background: #ea3536;
    border: 1px solid #f5f7fa;
    border-radius: 50%;
    content: "";
  } -->
<style lang="postcss" scoped>
.collector-config {
  padding-right: 12px;
  color: #979ba5;

  .route-config {
    position: relative;
    color: #3a84ff;
  }

  .operation-icon {
    margin-left: 18px;
    font-size: 16px;
  }
}
</style>
