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
    class="setting-filed"
    @click="handleSettingField">
    <audit-icon type="setting" />
  </div>
  <audit-sideslider
    v-model:is-show="isShow"
    class="setting-filed-box"
    :show-footer="false"
    title="列表字段显示设置"
    :width="940">
    <setting-field
      v-model="isShow"
      @update-field="handleUpdateField" />
  </audit-sideslider>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';

  import SettingField from './components/setting-field.vue';

  interface Emits {
    (e: 'updateField'):void
  }
  const emit = defineEmits<Emits>();
  const isShow = ref(false);


  const handleSettingField = async () => {
    isShow.value = true;
  };

  const handleUpdateField = () => {
    emit('updateField');
  };


</script>
<style lang="postcss" scoped>
.setting-filed {
  position: absolute;
  top: 26px;
  right: 25px;
  z-index: 3;
  width: 40px;
  height: 40px;
  font-size: 14px;
  line-height: 40px;
  color: #c4c6cc;
  text-align: center;
  cursor: pointer;
  background: #fafbfd;
}

.setting-filed:hover {
  background-color: #f0f1f5;
}
</style>
