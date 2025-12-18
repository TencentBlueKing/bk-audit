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
  <div class="storage-operation-box">
    <storage-base-data
      ref="baseDataRef"
      v-model="baseInfoFormData"
      v-model:connectivityDetect="isConnectivityDetect"
      :is-edit="isEdit" />
    <storage-manage-data
      v-if="isConnectivityDetect"
      ref="manageDataRef"
      v-model="manageFormData"
      :base-info="baseInfoFormData" />
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StorageService from '@service/storage-manage';

  import type StorageModel from '@model/storage/storage';

  import useMessage from '@hooks/use-message';

  import StorageBaseData from './components/storage-base-data.vue';
  import StorageManageData from './components/storage-manage-data.vue';

  interface Emits {
    (e: 'change'): void
    (e: 'update:disabled', value: boolean): void
    (e: 'update:btnLoading', value: boolean): void
  }
  const props = defineProps<{
    data: StorageModel
  }>();
  const emit = defineEmits<Emits>();
  const genBaseInfoFormData = () => ({
    cluster_id: 0,
    cluster_name: '',
    bkbase_cluster_en_name: '',
    domain_name: '',
    source_type: '',
    port: 80,
    schema: 'http',
    auth_info: {
      username: '',
      password: '',
    },
  });

  const genManageFormData = () => ({
    enable_hot_warm: false,
    hot_attr_name: '',
    hot_attr_value: '',
    warm_attr_name: '',
    warm_attr_value: '',
    setup_config: {
      retention_days_default: 7,
      number_of_replicas_default: 1,
    },
    admin: [],
    allocation_min_days: 0,
    description: '',
  });

  const baseDataRef = ref();
  const manageDataRef = ref();
  const editClusterId = ref(0);

  const baseInfoFormData = ref(genBaseInfoFormData());
  const manageFormData = ref(genManageFormData());
  const isConnectivityDetect = ref(false);
  const isEdit = ref(false);

  const { messageSuccess } = useMessage();
  const { t } = useI18n();

  watch(() => props.data, (data) => {
    if (!data.cluster_config) {
      isEdit.value = false;
      return;
    }
    isEdit.value = true;
    const {
      auth_info: authInfo,
      cluster_config: {
        cluster_id: clusterId,
        cluster_name: clusterName,
        domain_name: domainName,
        port,
        schema,
        custom_option: {
          admin,
          bkbase_cluster_id: bkbaseClusterId,
          hot_warm_config: hostWarmConfig,
          setup_config: setupConfig,
          source_type: sourceType,
          allocation_min_days,
          description,
        },
      },
    } = data;

    editClusterId.value = clusterId;

    baseInfoFormData.value = {
      cluster_id: clusterId,
      cluster_name: clusterName,
      bkbase_cluster_en_name: bkbaseClusterId,
      domain_name: domainName,
      source_type: sourceType,
      port,
      schema,
      auth_info: authInfo,
    };

    manageFormData.value = {
      enable_hot_warm: hostWarmConfig.is_enabled,
      hot_attr_name: hostWarmConfig.hot_attr_name,
      hot_attr_value: hostWarmConfig.hot_attr_value,
      warm_attr_name: hostWarmConfig.warm_attr_name,
      warm_attr_value: hostWarmConfig.warm_attr_value,
      setup_config: setupConfig,
      admin,
      allocation_min_days,
      description,
    };
  }, {
    immediate: true,
  });

  watch(() => isConnectivityDetect, (data) => {
    emit('update:disabled', data.value);
  }, {
    immediate: true,
    deep: true,
  });

  defineExpose({
    submit() {
      const tastQueue = [baseDataRef.value.getData()];
      if (manageDataRef.value) {
        tastQueue.push(manageDataRef.value.getData());
      }
      emit('update:btnLoading', true);
      if (isEdit.value) {
        // 编辑状态
        if (!manageDataRef.value) {
          // 没有进行任务编辑操作直接保存
          tastQueue.push(Promise.resolve(manageFormData.value));
        }
        return Promise.all(tastQueue).then(([baseData, manageData]) => StorageService.update({
          id: props.data.cluster_config.cluster_id,
          ...baseData,
          ...manageData,
        }))
          .then(() => {
            messageSuccess(t('编辑成功'));
            emit('change');
            emit('update:btnLoading', false);
          });
      }
      return Promise.all(tastQueue).then(([baseData, manageData]) => StorageService.create({
        ...baseData,
        ...manageData,
      }))
        .then(() => {
          messageSuccess(t('新建成功'));
          emit('change');
          emit('update:btnLoading', false);
        });
    },
  });
</script>
<style lang="postcss">
  .storage-operation-box {
    padding: 28px 40px;

    .form-item-row {
      display: flex;
    }

    .form-item-col {
      flex: 1;

      &:nth-child(2) {
        margin-left: 24px;
      }
    }
  }
</style>
