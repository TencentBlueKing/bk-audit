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
  <div class="api-push-operation">
    <auth-component
      action-id="edit_system"
      class="operation-btn"
      :resource="route.params.id">
      <audit-icon
        v-bk-tooltips="t('查看')"
        class="operation-icon"
        type="audit"
        @click.stop="handleDetail" />
    </auth-component>
  </div>
  <bk-sideslider
    v-model:isShow="isShowDetail"
    :title="t('日志采集详情')"
    :width="960">
    <template #default>
      <div class="check-detail-content">
        <edit-info :data="data" />
      </div>
    </template>
  </bk-sideslider>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import EditInfo from './edit-info/index.vue';

  interface Props {
    data: {
      token: string;
      hosts: string[];
      collector_config_name: string;
    };
  }

  defineProps<Props>();

  const { t } = useI18n();
  const route = useRoute();
  const isShowDetail = ref(false);

  const handleDetail = () => {
    isShowDetail.value = true;
  };
</script>
<style lang="postcss" scoped>
  .api-push-operation {
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
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }
    }
  }

  .check-detail-content {
    height: calc(100vh - 114px);
    padding: 22px 40px;
  }
</style>

