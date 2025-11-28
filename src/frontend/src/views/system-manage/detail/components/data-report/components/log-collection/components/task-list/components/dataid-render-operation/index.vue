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
    <template
      v-if="!loading">
      <auth-component
        action-id="edit_system"
        class="operation-btn"
        :permission="dataCheckMap.edit_system"
        :resource="data.system_id">
        <audit-icon
          v-bk-tooltips="t('查看')"
          class="operation-icon"
          type="audit"
          @click.stop="handleDetail" />
      </auth-component>
      <auth-component
        action-id="edit_system"
        class="operation-btn"
        :permission="dataCheckMap.edit_system"
        :resource="data.system_id">
        <audit-icon
          v-bk-tooltips="t('编辑')"
          class="operation-icon"
          type="edit-fill"
          @click.stop="handleEdit" />
      </auth-component>
      <auth-component
        action-id="edit_system"
        class="operation-btn"
        :permission="dataCheckMap.edit_system"
        :resource="data.system_id">
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
    </template>
  </div>
  <bk-sideslider
    v-model:isShow="isShowDetail"
    :title="t(data.collector_config_name)"
    :width="960">
    <template #default>
      <div class="check-detail-content">
        <!-- 基本信息 -->
        <edit-info
          :data="data"
          width="50%" />
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

  import DataIdManageService from '@service/dataid-manage';
  import IamManageService from '@service/iam-manage';

  import type CollectorModel from '@model/collector/collector';

  import useRequest from '@hooks/use-request';

  import EditInfo from './edit-info/index.vue';

  const props = defineProps<Props>();


  const emit = defineEmits<Emits>();


  interface Props {
    data: CollectorModel;
  }
  interface Emits {
    (e: 'getCollectorLists'): void
  }

  const { t } = useI18n();

  const route = useRoute();
  const router = useRouter();
  const isShowDetail = ref(false);


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

  const handleDetail = () => {
    isShowDetail.value = true;
  };
  const handleEdit = () => {
    router.push({
      name: 'dataIdEdit',
      params: {
        systemId: route.params.id,
        bkDataId: props.data.bk_data_id,
      },
    });
  };

  const handleDelete = () => deleteDataId({
    bk_data_id: props.data.bk_data_id,
  });
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
