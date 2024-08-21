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
  <div class="task-switch">
    <auth-component
      action-id="manage_global_setting"
      :permission="data.permission.manage_global_setting">
      <audit-popconfirm
        v-if="status === 'running'"
        :confirm-handler="handleSubmit"
        :content="t('任务停止后, 所有与该任务有关的清洗、入库任务都会停止。同时, 引用了该数据源的其他任务也会受到影响')"
        :title="t('请确认是否停止任务')">
        <bk-button
          v-bk-tooltips="t('停用后, 资源的详细数据将会失效')"
          text
          theme="primary">
          {{ t('停用') }}
        </bk-button>
      </audit-popconfirm>
      <bk-button
        v-if="status === 'closed' || status === 'failed'"
        v-bk-tooltips="t('启用后, 资源的详细数据将会生效')"
        text
        theme="primary"
        @click="handleJoinData(true)">
        {{ t('启用') }}
      </bk-button>
    </auth-component>
    <a
      v-if="bkbaseUrl"
      v-bk-tooltips="t('查看计算平台的任务详情')"
      class="ml8"
      :href="bkbaseUrl"
      target="_blank">
      {{ t('数据详情') }}
    </a>
  </div>
</template>
<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import JoinDataModel from '@model/collector/join-data';

  import useRequest from '@hooks/use-request';

  interface Props{
    data: Record<string, any>;
    status: string,
    bkbaseUrl: string,
  }
  interface Emits {
    (e: 'changeStatus'): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const route = useRoute();
  const { t } = useI18n();

  // 更改数据录入任务
  const {
    run: fetchJoinData,
  }  = useRequest(CollectorManageService.fetchJoinData, {
    defaultValue: new JoinDataModel(),
    onSuccess: () => {
      emits('changeStatus');
    },
  });

  const handleSubmit = () => Promise.resolve()
    .then(() => {
      handleJoinData(false);
    });
  const handleJoinData = (value: boolean) => {
    fetchJoinData({
      system_id: route.params.id,
      resource_type_id: props.data.resource_type_id,
      is_enabled: value,
      pull_type: 'partial', // 操作栏操作默认增量更新
    });
  };

</script>
