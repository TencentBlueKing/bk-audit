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
<!-- eslint-disable vue/no-v-html -->
<template>
  <div class="risk-content-item">
    <div class="risk-content-title">
      <span style="color: #63656E;">{{ data.created_by }} {{ t('添加风险总结') }}</span>
      <span style=" margin-left: 8px;color: #979BA5;">{{ data.created_at }}</span>
      <audit-icon
        v-if="showEditBtn"
        style="margin-left: 10px;color: #3A84FF;cursor: pointer;"
        type="edit-fill"
        @click="handleEdit" />
    </div>
    <div
      class="rich-html"
      style="padding: 8px;margin-top: 8px;background: #F5F7FA;border-radius: 4px;"
      v-html="data.content" />
  </div>
</template>

<script setup lang='ts'>
  import {
    useI18n,
  } from 'vue-i18n';

  import type RiskExperienceManageModel from '@model/risk-experience/experience';

  interface Emits{
    (e:'edit'):void,
  }

  interface Props{
    data: RiskExperienceManageModel,
    showEditBtn: boolean,
  }
  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const handleEdit = () => {
    emits('edit');
  };
</script>
<style lang="postcss">
.rich-html{
  ul{
    padding-left: 15px;

    li{
      list-style: disc !important;
    }
  }

  ol{
    padding-left: 13px;

    li{
      list-style: decimal;
    }
  }
}

.risk-content-item{
  padding: 10px 16px;
  background: #FFF;
  border: 1px solid #EAEBF0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;

  .risk-content-title{
    display: flex;
    font-size: 12px;
    align-items: center;
  }
}
</style>
