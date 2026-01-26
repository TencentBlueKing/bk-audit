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
  <div class="wild-card-content">
    <div class="wild-card-header">
      <div class="wild-card-title">
        {{ t('通配符使用说明') }}
      </div>
      <div
        class="close-icon"
        @click="handleClose">
        <audit-icon type="close" />
      </div>
    </div>
    <scroll-faker style="height: calc(100% - 72px);padding: 16px;">
      <div
        v-for="(item, index) in lists"
        :key="index"
        class="wild-card-item">
        <p class="wild-card-value">
          {{ item.title }}
        </p>
        <div class="wild-card-text">
          {{ t(item.meaning) }}
        </div>
        <div class="wild-card-text">
          {{ t(item.example, {string: '{abc,xyz,123}'}) }}
        </div>
      </div>
    </scroll-faker>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  const emits = defineEmits<Emits>();
  const lists = [
    {
      title: ' *',
      meaning: '【含义】匹配 0 或多个字符',
      example: '【示例】a*b, a 与 b 之间可以有任意长度的任意字符, 也可以一个也没有, 如 aabcb, axyzb, a012b, ab',
    },
    {
      title: ' ?',
      meaning: '【含义】匹配任意一个字符',
      example: '【示例】a?b, a 与 b 之间必须也只能有一个字符, 可以是任意字符, 如 aab, abb, acb, a0b',
    },
    {
      title: ' [list]',
      meaning: '【含义】匹配 list 中的任意单一字符',
      example: '【示例】a[xyz]b, a 与 b 之间必须也只能有一个字符, 但只能是 x 或 y 或 z, 如: axb, ayb, azb',
    },
    {
      title: ' [!list]',
      meaning: '【含义】匹配 除 list 中的任意单一字符',
      example: '【示例】a[!0-9]b, a 与 b 之间必须也只能有一个字符, 但不能是阿拉伯数字, 如 axb, aab, a-b',
    },
    {
      title: ' [c1-c2]',
      meaning: '【含义】匹配 c1-c2 中的任意单一字符',
      example: '【示例】[0-9] [a-z], a[0-9]b, 0 与 9 之间必须也只能有一个字符 如 a0b, a1b... a9b',
    },
    {
      title: ' {string1,string2,...}',
      meaning: '【含义】匹配 sring1 或 string2 (或更多)其一字符串',
      example: '【示例】a{abc,xyz,123}b, a 与 b 之间只能是 abc 或 xyz 或 123 这三个字符串之一',
    },
  ];
  interface Emits {
    (e: 'change', value: boolean): void;
  }

  const { t } = useI18n();
  const handleClose = () => {
    emits('change', false);
  };
</script>
<style lang="postcss">
.wild-card-content {
  position: fixed;
  top: 52px;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: block;
  width: 320px;
  height: calc(100% - 52px);
  background: white;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 12%);

  .wild-card-header {
    display: flex;
    padding: 12px 16px;
    border-bottom: 1px solid #f0f1f5;

    .wild-card-title {
      font-size: 16px;
      color: #313238;
    }

    .close-icon {
      margin-left: auto;
      color: #c4c6cc;
      cursor: pointer;
    }
  }

  .wild-card-item {
    margin-bottom: 24px;

    .wild-card-value {
      font-size: 14px;
      font-weight: bold;
      line-height: 22px;
      color: #313238;
    }

    .wild-card-text {
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }
  }
}
</style>
