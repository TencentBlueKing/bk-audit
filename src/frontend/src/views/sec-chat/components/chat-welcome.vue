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
  <div class="chat-welcome">
    <div class="welcome-body">
      <div class="welcome-column">
        <!-- 标题区 -->
        <div class="welcome-hero">
          <img
            alt="AI助手"
            class="logo-icon"
            :src="aiAssistantIcon">
          <h1 class="hero-title">
            AI助手
          </h1>
          <p class="hero-desc">
            审计中心智能助手 — 分析审计风险、解读告警、检索日志、生成报告
          </p>
        </div>

        <!-- 功能卡片 -->
        <div class="prompt-grid">
          <div
            v-for="item in promptCards"
            :key="item.title"
            class="prompt-card"
            :class="{ 'is-disabled': item.disabled }"
            :title="item.disabled ? '暂未开放' : undefined"
            @click="handleCardClick(item)">
            <div class="card-icon">
              <img
                v-if="item.iconSrc"
                alt=""
                class="card-icon-img"
                :src="item.iconSrc">
              <audit-icon
                v-else
                :type="item.icon" />
            </div>
            <div class="card-content">
              <div class="card-title">
                {{ item.title }}
              </div>
              <div class="card-desc">
                {{ item.desc }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="welcome-footer">
      <div class="welcome-column">
        <chat-input
          hide-shortcuts
          @attach="$emit('attach')"
          @send="handleInputSend" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import ChatInput from './chat-input.vue';
  import type { ChatSceneType, SelectPromptPayload } from '../types';

  import aiAssistantIcon from '@images/ai-assistant.svg';
  import aiSettingIcon from '@images/ai-setting.svg';
  import biaobiaoIcon from '@images/biaobiao-icon.svg';
  import fengxianIcon from '@images/fengxian-icon.svg';
  import shiyongIcon from '@images/shiyong-icon.svg';

  const emit = defineEmits<{
    'select-prompt': [payload: SelectPromptPayload];
    attach: [];
  }>();

  const promptCards = [
    {
      icon: 'audit',
      title: '审计日志检索',
      desc: '用对话查询与统计各系统审计日志',
      prompt: '请帮我检索审计日志',
      sceneType: 'log' as ChatSceneType,
      disabled: false,
    },
    {
      icon: 'shujutongji',
      title: '风险分析',
      desc: '分析当前审计风险分布与趋势',
      prompt: '请帮我分析当前审计风险分布与趋势',
      disabled: true,
    },
    {
      icon: '',
      iconSrc: fengxianIcon,
      title: '风险解读',
      desc: '解读未处理的高危风险告警',
      prompt: '帮我解读未处理的高危风险告警',
      disabled: true,
    },
    {
      icon: '',
      iconSrc: biaobiaoIcon,
      title: '报表解读',
      desc: '解读审计报表数据与趋势分析',
      prompt: '请帮我解读审计报表数据与趋势',
      disabled: true,
    },
    {
      icon: '',
      iconSrc: aiSettingIcon,
      title: '场景配置',
      desc: '了解如何配置审计场景与检测策略',
      prompt: '请介绍如何配置审计场景与检测策略',
      disabled: true,
    },
    {
      icon: '',
      iconSrc: shiyongIcon,
      title: '使用帮助',
      desc: '了解审计中心功能配置与使用方法',
      prompt: '请介绍审计中心的功能配置与使用方法',
      disabled: true,
    },
  ];

  const handleCardClick = (item: typeof promptCards[0]) => {
    if (item.disabled) return;
    emit('select-prompt', {
      prompt: item.prompt,
      sceneType: item.sceneType,
    });
  };

  const handleInputSend = (prompt: string) => {
    // 当前仅开放审计日志检索，欢迎页发送一律进入该场景
    emit('select-prompt', {
      prompt,
      sceneType: 'log',
    });
  };
</script>

<style lang="postcss" scoped>
  .chat-welcome {
    display: flex;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: #f5f7fa;
    box-sizing: border-box;
    flex: 1;
    flex-direction: column;
  }

  .welcome-body {
    display: flex;
    min-height: 0;
    padding: 40px 24px 24px;
    overflow: auto;
    flex: 1;
    align-items: center;
    justify-content: center;
  }

  .welcome-footer {
    display: flex;
    flex-shrink: 0;
    width: 100%;
    padding: 0 24px 20px;
    box-sizing: border-box;
    justify-content: center;
  }

  /* 标题 / 卡片 / 输入 同一宽度，与对话区 900 对齐 */
  .welcome-column {
    display: flex;
    width: 900px;
    max-width: 100%;
    min-width: 0;
    flex-direction: column;
    flex-shrink: 0;
  }

  .welcome-hero {
    display: flex;
    margin-bottom: 32px;
    flex-direction: column;
    align-items: center;

    .logo-icon {
      display: block;
      width: 64px;
      height: 64px;
      margin-bottom: 16px;
    }

    .hero-title {
      margin: 0 0 16px;
      font-size: 48px;
      font-weight: 800;
      line-height: 40px;
      color: #313238;
    }

    .hero-desc {
      margin: 0;
      font-size: 16px;
      line-height: 22px;
      color: #4D4F56;
      text-align: center;
    }
  }

  .prompt-grid {
    display: grid;
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;

    .prompt-card {
      display: flex;
      min-width: 0;
      min-height: 98px;
      padding: 16px;
      cursor: pointer;
      background: #fff;
      border: 1px solid #eaebf0;
      border-radius: 4px;
      transition: box-shadow .2s;
      align-items: center;
      gap: 12px;
      box-sizing: border-box;

      &:hover {
        box-shadow: 0 2px 10px 0 rgb(0 0 0 / 16%);
      }

      &.is-disabled {
        cursor: not-allowed;
      }

      .card-icon {
        display: flex;
        width: 50px;
        height: 50px;
        background: #f0f5ff;
        border-radius: 4px;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;

        i,
        .audit-icon,
        .card-icon-img {
          font-size: 20px;
          color: #3a84ff;
        }

        .card-icon-img {
          display: block;
          width: 20px;
          height: 20px;
        }
      }

      .card-content {
        flex: 1;
        min-width: 0;

        .card-title {
          margin-bottom: 5px;
          font-size: 16px;
          font-weight: 700;
          line-height: 22px;
          color: #000;
        }

        .card-desc {
          font-size: 14px;
          line-height: 20px;
          color: #4D4F56;
        }
      }
    }
  }
</style>
