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
    aria-busy="true"
    aria-live="polite"
    class="retrieval-card-skeleton">
    <div class="skeleton-status">
      <span class="loading-dot" />
      <span class="loading-dot" />
      <span class="loading-dot" />
      <span class="status-text">{{ statusText }}</span>
    </div>

    <div class="skeleton-paragraphs">
      <div
        v-for="(group, groupIndex) in lineGroups"
        :key="`group-${groupIndex}`"
        class="skeleton-paragraph">
        <div
          v-for="(width, lineIndex) in group"
          :key="`line-${groupIndex}-${lineIndex}`"
          class="bone bone-line"
          :style="{ width }" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  withDefaults(defineProps<{
    statusText?: string;
  }>(), {
    statusText: '加载中…',
  });

  /** 长短不一的文本行，模拟段落层次，避免等宽通栏堆叠 */
  const lineGroups = [
    ['72%', '100%', '88%'],
    ['100%', '64%', '92%'],
    ['78%', '54%'],
  ];
</script>

<style lang="postcss" scoped>
  .retrieval-card-skeleton {
    width: 100%;
    max-width: 900px;
    min-height: 280px;
    padding: 20px 24px 28px;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
  }

  .skeleton-status {
    display: flex;
    margin-bottom: 20px;
    align-items: center;
    gap: 6px;
    color: #63656e;
  }

  .status-text {
    margin-left: 4px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
  }

  .loading-dot {
    width: 6px;
    height: 6px;
    background: #3a84ff;
    border-radius: 50%;
    opacity: 40%;
    animation: chat-loading-dot 1s ease-in-out infinite;
  }

  .loading-dot:nth-child(1) {
    animation-delay: 0s;
  }

  .loading-dot:nth-child(2) {
    animation-delay: .15s;
  }

  .loading-dot:nth-child(3) {
    animation-delay: .3s;
  }

  .skeleton-paragraphs {
    display: flex;
    flex-direction: column;
    gap: 22px;
  }

  .skeleton-paragraph {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .bone {
    position: relative;
    overflow: hidden;
    background: #ebecf3;
    border-radius: 2px;

    &::after {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgb(246 247 251 / 80%) 50%,
        transparent 100%
      );
      content: '';
      transform: translateX(-100%);
      animation: skeleton-shimmer 1.6s ease-in-out infinite;
    }
  }

  .bone-line {
    height: 10px;
  }

  @keyframes chat-loading-dot {
    0%,
    100% {
      opacity: 40%;
      transform: scale(1);
    }

    50% {
      opacity: 100%;
      transform: scale(1.15);
    }
  }

  @keyframes skeleton-shimmer {
    100% {
      transform: translateX(100%);
    }
  }
</style>
