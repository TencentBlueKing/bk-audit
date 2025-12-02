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
  <card-part-vue :title="t('查询结果设置')">
    <template #content>
      <div class="group-box">
        <span>{{ t('是否分组') }}</span>
        <bk-switcher
          v-model="isGroup"
          class="group"
          theme="primary" />
        <span v-if="!isGroup">
          <audit-icon
            class="info-fill"
            type="info-fill" />
          <span class="info-fill-tex">{{ t('开启后，查询结果将按字段分组展示') }}</span>
        </span>
        <span v-else>
          <span class="group-button">
            <audit-icon
              class="plus-circle"
              type="plus-circle" />
            <span class="plus-circle-tex">{{ t('添加分组') }}</span>
          </span>
          <span class="line" />
          <span>
            <audit-icon
              class="plus-circle"
              type="plus-circle" />
            <span class="plus-circle-tex">{{ t('添加分组') }}</span>
          </span>
        </span>
      </div>
      <content
        v-if="!isGroup"
        :resultData="resultData" />
      <group-content
        v-else
        :result-data="resultData" />
    </template>
  </card-part-vue>
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../../card-part.vue';

  import content from './content.vue';
  import groupContent from './group-content.vue';


  interface Props {
    resultData: any,
  }
  defineProps<Props>();
  const { t } = useI18n();
  const isGroup = ref(false);

</script>

<style lang="postcss" scoped>
.group-box {
  display: flex;
  font-size: 12px;
  color: #4d4f56;
}

.group {
  margin-left: 10px;
}

.info-fill {
  margin-left: 10px;
  font-size: 14px;
  color: #979ba5;
}

.info-fill-tex {
  margin-left: 10px;
  font-size: 12px;
  color: #979ba5;
}

.group-button {
  margin-left: 10px;
  font-size: 12px;
  color: #3a84ff;
}

.plus-circle {
  margin-left: 10px;
  font-size: 14px;
  color: #3a84ff;
  cursor: pointer;

}

.plus-circle-tex {
  margin-left: 5px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
}

.line {
  display: inline-block;
  width: 1px;
  height: 16px;
  margin-left: 10px;
  vertical-align: middle;
  background: #dcdee5;
}
</style>
