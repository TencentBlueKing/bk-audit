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
  <bk-dialog
    class="batch-dialog-wrap"
    dialog-type="show"
    :is-show="isShow"
    theme="primary"
    title=""
    @closed="() => isShow = false"
    @confirm="() => isShow = false">
    <div
      class="batch-prioriry-dialog"
      style="text-align: center;">
      <p class="logo">
        <audit-icon
          style="font-size: 18px;color: #3fc06d;"
          type="check-line" />
      </p>
      <p class="title">
        {{ t('处理规则新建成功') }}
      </p>
      <p>
        {{ t('规则新建后默认') }}<span style="font-weight: bold;">{{ t('不启用') }}</span>,
        {{ t('可在调整') }}
        <span style="font-weight: bold;border-bottom: 1px dashed #63656e">
          {{ t('优先级') }}
        </span>
        {{ t('后手动启用') }}
      </p>
      <div class="btns">
        <auth-button
          action-id="edit_rule"
          class="mr8"
          theme="primary"
          @click="handleSubmit">
          {{ t('去调整规则优先级') }}
        </auth-button>
        <bk-button @click="handleToList">
          {{ t('返回规则列表') }}
        </bk-button>
      </div>
    </div>
  </bk-dialog>
</template>

<script setup lang='ts'>
  import {  ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    // useRoute,
    useRouter,
  } from 'vue-router';

  import useMessage from '@hooks/use-message';

  interface Exposes{
    show():void,
  }
  const router = useRouter();
  const { t } = useI18n();

  const isShow = ref(false);
  const { messageSuccess } = useMessage();

  const handleSubmit = () => {
    router.push({
      name: 'ruleManageList',
      query: {
        batchPriorityIndex: 'true',
      },
    });
    messageSuccess(t('新建成功'));
  };
  const handleToList = () => {
    router.push({
      name: 'ruleManageList',
    });
    messageSuccess(t('新建成功'));
  };
  defineExpose<Exposes>({
    show() {
      isShow.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.batch-dialog-wrap :deep(.bk-modal-content) {
  overflow: visible !important;
}

.batch-prioriry-dialog {
  margin-top: -24px;

  .logo {
    display: flex;
    width: 42px;
    height: 42px;
    margin: 0 auto;
    background: #e5f6ea;
    border-radius: 50%;
    align-items: center;
    justify-content: center;
  }

  .title {
    margin: 15px 0 10px;
    font-size: 20px;
    color: #313238;
  }

  .btns {
    display: flex;
    width: 100%;
    margin-top: 24px;
    align-items: center;
    justify-content: center;
  }
}
</style>
