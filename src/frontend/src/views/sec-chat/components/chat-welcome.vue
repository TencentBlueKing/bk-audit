<template>
  <div class="chat-welcome">
    <!-- 可滚动内容区 -->
    <div class="welcome-content">
      <!-- Logo + 标题区域 -->
      <div class="welcome-hero">
        <div class="hero-logo">
          <div class="logo-block">
            <audit-icon type="audit" />
          </div>
        </div>
        <h1 class="hero-title">
          SecChat
        </h1>
        <p class="hero-desc">
          HIDS 安全智能助手 — 分析主机行为、解读风险告警、调查安全事件
        </p>
      </div>

      <!-- 功能卡片网格 -->
      <div class="prompt-grid">
        <div
          v-for="item in promptCards"
          :key="item.title"
          class="prompt-card"
          @click="$emit('select-prompt', item.prompt)">
          <div class="card-icon">
            <audit-icon :type="item.icon" />
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

    <!-- 底部输入区（固定不被压缩） -->
    <chat-input
      @attach="$emit('attach')"
      @send="$emit('select-prompt', $event)" />
  </div>
</template>

<script lang="ts" setup>
  import ChatInput from './chat-input.vue';

  defineEmits<{
    'select-prompt': [prompt: string];
    attach: [];
  }>();

  const promptCards = [
    {
      icon: 'analysis',
      title: '分析主机行为',
      desc: '分析目标主机的一场行为与安全风险',
      prompt: '请帮我分析主机的异常行为',
    },
    {
      icon: 'alert',
      title: '解读风险告警',
      desc: '解读当前未处理的主机风险告警',
      prompt: '帮我解读主机的风险告警',
    },
    {
      icon: 'view',
      title: '查看安全事件',
      desc: '查看近期未处理的安全事件',
      prompt: '请帮我查看近期未处理的安全事件',
    },
    {
      icon: 'check-line',
      title: '主机健康检查',
      desc: '对目标主机进行安全基线合规检查',
      prompt: '请对主机进行安全基线合规检查',
    },
    {
      icon: 'chart',
      title: '安全态势总览',
      desc: '了解当前全网安全态势概况',
      prompt: '请帮我了解当前全网安全态势概况',
    },
    {
      icon: 'help-document-fill',
      title: 'HIDS 使用帮助',
      desc: '了解 HIDS 功能配置与使用方法',
      prompt: '请介绍 HIDS 的功能配置与使用方法',
    },
  ];
</script>

<style lang="postcss" scoped>
  .chat-welcome {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;

    .welcome-content {
      padding: 60px 24px 0;
      overflow-y: auto;
      background: #f5f7fa;
      flex: 1;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #dcdee5;
        border-radius: 2px;
      }
    }

    /* Logo + 标题 */
    .welcome-hero {
      display: flex;
      width: 100%;
      max-width: 900px;
      margin-right: auto;
      margin-bottom: 40px;
      margin-left: auto;
      flex-direction: column;
      align-items: center;

      .hero-logo {
        margin-bottom: 20px;

        .logo-block {
          display: flex;
          width: 64px;
          height: 64px;
          background: #e1ecff;
          border-radius: 16px;
          align-items: center;
          justify-content: center;

          i {
            font-size: 32px;
            color: #3a84ff;
          }

          .audit-icon {
            font-size: 32px;
            color: #3a84ff;
          }
        }
      }

      .hero-title {
        margin: 0 0 12px;
        font-size: 32px;
        font-weight: 600;
        letter-spacing: 1px;
        color: #313238;
      }

      .hero-desc {
        margin: 0;
        font-size: 14px;
        line-height: 22px;
        color: #63656e;
        text-align: center;
      }
    }

    /* 功能卡片 */
    .prompt-grid {
      display: grid;
      width: 100%;
      max-width: 900px;
      margin-right: auto;
      margin-bottom: 40px;
      margin-left: auto;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;

      .prompt-card {
        display: flex;
        padding: 18px 20px;
        cursor: pointer;
        background: #fff;
        border: 1px solid #e6e9f0;
        border-radius: 8px;
        transition: border-color .2s, box-shadow .2s;
        align-items: flex-start;
        gap: 14px;

        &:hover {
          border-color: #3a84ff;
          box-shadow: 0 2px 8px rgb(58 132 255 / 12%);
        }

        .card-icon {
          display: flex;
          width: 40px;
          height: 40px;
          background: #f0f5ff;
          border-radius: 8px;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;

          i,
          .audit-icon {
            font-size: 20px;
            color: #3a84ff;
          }
        }

        .card-content {
          flex: 1;
          min-width: 0;

          .card-title {
            margin-bottom: 4px;
            font-size: 14px;
            font-weight: 500;
            line-height: 22px;
            color: #313238;
          }

          .card-desc {
            font-size: 12px;
            line-height: 20px;
            color: #979ba5;
          }
        }
      }
    }
  }
</style>
