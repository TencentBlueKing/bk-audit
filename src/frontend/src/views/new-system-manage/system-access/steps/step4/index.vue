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
  <div class="step4">
    <audit-icon
      class="corret-fill-icon"
      type="corret-fill" />
    <div class="step4-title">
      {{ t('系统接入完成') }}
    </div>
    <div class="step4-desc">
      {{ t('后续在系统管理页，您仍可以随时编辑和管理自己系统下的系统信息、权限模型、日志数据') }}
    </div>
    <div
      class="step4-btn"
      @click="handleRouterChange">
      <audit-icon
        class="right-icon"
        type="right" />
      {{ t('进入系统信息管理页') }}
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

  const handleRouterChange = () => {
    window.changeConfirm = false;
    router.push({
      name: 'nweSystemManage',
      params: {
        id: route.params.id,
      },
    });
  };
</script>
<style scoped lang="postcss">
.step4 {
  position: absolute;
  left: 50%;
  width: 60%;
  height: 330px;
  margin-top: 30px;
  background-color: #fff;
  transform: translateX(-50%);

  .corret-fill-icon {
    position: absolute;
    left: 50%;
    margin-top: 44px;
    font-size: 64px;
    color: #2caf5e;
    transform: translateX(-50%);
  }

  .step4-title {
    position: absolute;
    left: 50%;
    margin-top: 144px;
    font-size: 24px;
    color: #313238;
    transform: translateX(-50%);
  }

  .step4-desc {
    position: absolute;
    width: 100%;
    margin-top: 192px;
    font-size: 14px;
    color: #313238;
    text-align: center;
  }

  .step4-btn {
    position: absolute;
    left: 50%;
    height: 32px;
    padding-right: 10px;
    padding-left: 10px;
    margin-top: 238px;
    font-size: 14px;
    line-height: 32px;
    color: #4d4f56;
    text-align: center;
    cursor: pointer;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    transform: translateX(-50%);

    &:hover {
      background-color: hsl(218deg 100% 61% / 20%); /* 保持色相，透明度设为70% */

    }
  }
}
</style>
