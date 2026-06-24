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
  <div class="top-search">
    <div class="top-search-title">
      {{ t('用户信息') }}
    </div>
    <div class="user-info-content">
      <div class="user-info-left">
        <div class="user-detail">
          <!-- 第1行：企业微信 | 用户名 -->
          <div class="detail-row">
            <div
              class="detail-group"
              @mouseenter="hoverField = 'wecom'"
              @mouseleave="hoverField = ''">
              <span class="detail-label">{{ t('企业微信') }}：</span>
              <span class="detail-value">{{ userInfo.wecom }}</span>
              <audit-icon
                v-if="hoverField === 'wecom'"
                class="copy-icon"
                type="copy"
                @click="handleCopy(userInfo.wecom)" />
            </div>
            <div class="detail-group">
              <span class="detail-label">{{ t('用户名') }}：</span>
              <span class="detail-value">{{ userInfo.username }}</span>
            </div>
          </div>
          <!-- 第2行：微信 | QQ -->
          <div class="detail-row">
            <!-- 微信 -->
            <div
              class="detail-group account-field"
              @mouseenter="hoverField = 'wechat'"
              @mouseleave="hoverField = ''">
              <span class="detail-label">{{ t('微信') }}：</span>
              <span class="account-value-wrap">
                <span class="tag-current">{{ t('当前') }}</span>
                <span
                  v-if="wechatCurrentList.length > 0"
                  class="account-values">{{ wechatCurrentDisplay }}</span>
                <span
                  v-if="wechatCurrentOverflow > 0"
                  v-bk-tooltips="{ content: wechatCurrentOverflowTip, placement: 'top', theme: 'dark' }"
                  class="overflow-count">; +{{ wechatCurrentOverflow }}</span>
                <!-- 当前与历史之间的灰色竖线分隔 -->
                <span
                  v-if="wechatCurrentList.length > 0 && wechatHistoryList.length > 0"
                  class="divider-line">|</span>
                <span
                  v-if="wechatHistoryList.length > 0"
                  class="tag-history">{{ t('历史') }}</span>
                <span
                  v-if="wechatHistoryList.length > 0"
                  class="account-values">{{ wechatHistoryDisplay }}</span>
                <span
                  v-if="wechatHistoryOverflow > 0"
                  v-bk-tooltips="{ content: wechatHistoryOverflowTip, placement: 'top', theme: 'dark' }"
                  class="overflow-count">; +{{ wechatHistoryOverflow }}</span>
              </span>
              <audit-icon
                class="eye-icon"
                :type="wechatVisible ? 'view' : 'unview'"
                @click="wechatVisible = !wechatVisible" />
              <!-- 复制浮层（hover 整个区域时显示，紧跟在眼睛图标后） -->
              <div class="account-copy-wrap">
                <div
                  v-show="hoverField === 'wechat' && (userInfo.wechat || wechatHistoryList.length > 0)"
                  class="account-copy-panel">
                  <span
                    v-if="userInfo.wechat"
                    class="copy-link"
                    @click="handleCopy(wechatRawCurrent)">{{ t('复制当前') }}</span>
                  <span
                    v-if="wechatHistoryList.length > 0"
                    class="copy-link"
                    @click="handleCopy(wechatRawHistory)">{{ t('复制历史') }}</span>
                </div>
              </div>
            </div>
            <!-- QQ -->
            <div
              class="detail-group account-field"
              @mouseenter="hoverField = 'qq'"
              @mouseleave="hoverField = ''">
              <span class="detail-label">QQ：</span>
              <span class="account-value-wrap">
                <span class="tag-current">{{ t('当前') }}</span>
                <span
                  v-if="qqCurrentList.length > 0"
                  class="account-values">{{ qqCurrentDisplay }}</span>
                <span
                  v-if="qqCurrentOverflow > 0"
                  v-bk-tooltips="{ content: qqCurrentOverflowTip, placement: 'top', theme: 'dark' }"
                  class="overflow-count">; +{{ qqCurrentOverflow }}</span>
                <!-- 当前与历史之间的灰色竖线分隔 -->
                <span
                  v-if="qqCurrentList.length > 0 && qqHistoryList.length > 0"
                  class="divider-line">|</span>
                <span
                  v-if="qqHistoryList.length > 0"
                  class="tag-history">{{ t('历史') }}</span>
                <span
                  v-if="qqHistoryList.length > 0"
                  class="account-values">{{ qqHistoryDisplay }}</span>
                <span
                  v-if="qqHistoryOverflow > 0"
                  v-bk-tooltips="{ content: qqHistoryOverflowTip, placement: 'top', theme: 'dark' }"
                  class="overflow-count">; +{{ qqHistoryOverflow }}</span>
              </span>
              <audit-icon
                class="eye-icon"
                :type="qqVisible ? 'view' : 'unview'"
                @click="qqVisible = !qqVisible" />
              <!-- 复制浮层（hover 整个区域时显示，紧跟在眼睛图标后） -->
              <div class="account-copy-wrap">
                <div
                  v-show="hoverField === 'qq' && (userInfo.qq || qqHistoryList.length > 0)"
                  class="account-copy-panel">
                  <span
                    v-if="userInfo.qq"
                    class="copy-link"
                    @click="handleCopy(qqRawCurrent)">{{ t('复制当前') }}</span>
                  <span
                    v-if="qqHistoryList.length > 0"
                    class="copy-link"
                    @click="handleCopy(qqRawHistory)">{{ t('复制历史') }}</span>
                </div>
              </div>
            </div>
          </div>
          <!-- 第3行：在职状态 | 部门 -->
          <div class="detail-row">
            <div class="detail-group">
              <span class="detail-label">{{ t('在职状态') }}：</span>
              <bk-tag
                :class="{ 'status-resigned': userInfo.status !== '在职' }"
                :theme="userInfo.status === '在职' ? 'success' : ''">
                {{ userInfo.status }}
              </bk-tag>
            </div>
            <div class="detail-group">
              <span class="detail-label">{{ t('部门') }}：</span>
              <span class="detail-value">{{ userInfo.department }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="user-info-right">
        <div class="stat-card responsibility">
          <div class="stat-label">
            {{ t('责任单数') }}
            <span
              class="view-detail"
              @click="handleViewDetail">
              {{ t('查看详情') }}
              <audit-icon type="jump-link" />
            </span>
          </div>
          <div class="stat-value-row">
            <div class="stat-value">
              {{ userInfo.responsibilityCount }}
            </div>
          </div>
          <img
            class="stat-icon"
            :src="danjvIcon">
        </div>
        <div
          class="stat-card risk"
          :class="riskLevelClass">
          <div class="stat-label">
            {{ t('风险系数') }}
          </div>
          <div class="stat-value-row">
            <div
              class="stat-value risk-level"
              :class="riskLevelClass">
              {{ userInfo.riskLevel }}
            </div>
          </div>
          <img
            class="stat-icon"
            :src="riskWarningIcon">
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import danjvIcon from '@images/danjv.svg';
  import warningHighIcon from '@images/warning-high.svg';
  import warningLowIcon from '@images/warning-low.svg';
  import warningMediumIcon from '@images/warning-medium.svg';

  import { execCopy } from '@utils/assist';

  const props = withDefaults(defineProps<Props>(), {
    historyAccounts: () => [],
  });

  const emit = defineEmits<Emits>();

  // 最大显示的账号数量（超出则显示 +n）
  const MAX_DISPLAY_COUNT = 3;

  interface HistoryAccountItem {
    type: string;   // 'wechat' | 'qq' | '微信' | 'QQ'
    account: string;
  }

  interface UserInfo {
    avatar: string;
    wecom: string;
    username: string;
    wechat: string;
    qq: string;
    status: string;
    department: string;
    responsibilityCount: number;
    riskLevel: string;
  }

  interface Props {
    userInfo: UserInfo;
    historyAccounts?: HistoryAccountItem[];
  }

  interface Emits {
    (e: 'viewDetail'): void;
  }

  const { t } = useI18n();

  // 眼睛图标控制显示/隐藏
  const wechatVisible = ref(false);
  const qqVisible = ref(false);

  // hover 状态（用于控制复制浮层显示）
  const hoverField = ref('');

  // ========== 脱敏 / 格式化工具函数 ==========

  // 脱敏单个账号
  const maskSingle = (value: string) => {
    if (!value) return '';
    if (value.length <= 2) return value;
    return `${value[0]}${'*'.repeat(value.length - 2)}${value[value.length - 1]}`;
  };

  // 将原始字符串按分号拆分为数组并清理
  const splitAccounts = (raw: string): string[] => {
    if (!raw) return [];
    return raw.split(';').map(v => v.trim())
      .filter(Boolean);
  };

  // 从历史列表中按类型筛选（兼容 企业微信/wechat/微信/QQ/qq 等多种命名）
  const filterHistoryByType = (type: string): HistoryAccountItem[] => {
    const wechatTypes = ['wechat', '微信', '企业微信', 'wecom'];
    const qqTypes = ['qq', 'QQ'];
    const targetTypes = type === 'wechat' ? wechatTypes : qqTypes;
    return props.historyAccounts.filter(item => targetTypes.includes(item.type));
  };

  // 截断显示（最多 MAX_DISPLAY_COUNT 个）
  const truncateList = (
    list: string[],
    maxCount: number,
  ): { display: string[]; overflow: number } => {
    if (list.length <= maxCount) return { display: list, overflow: 0 };
    return { display: list.slice(0, maxCount), overflow: list.length - maxCount };
  };

  // ========== 微信数据计算 ==========
  const wechatHistoryList = computed(() => filterHistoryByType('wechat'));
  const wechatCurrentList = computed(() => splitAccounts(props.userInfo.wechat));

  const wechatCurrentTruncated = computed(() => truncateList(wechatCurrentList.value, MAX_DISPLAY_COUNT));
  const wechatHistoryTruncated = computed(() => truncateList(
    wechatHistoryList.value.map(i => i.account),
    MAX_DISPLAY_COUNT,
  ));

  const wechatCurrentDisplay = computed(() => {
    const fn = wechatVisible.value ? (v: string) => v : maskSingle;
    return wechatCurrentTruncated.value.display.map(fn).join(' ; ');
  });

  const wechatHistoryDisplay = computed(() => {
    const fn = wechatVisible.value ? (v: string) => v : maskSingle;
    return wechatHistoryTruncated.value.display.map(fn).join(' ; ');
  });

  const wechatCurrentOverflow = computed(() => wechatCurrentTruncated.value.overflow);
  const wechatHistoryOverflow = computed(() => wechatHistoryTruncated.value.overflow);

  // 用于复制的原始文本（明文，分号拼接）
  const wechatRawCurrent = computed(() => wechatCurrentList.value.join(';'));
  const wechatRawHistory = computed(() => wechatHistoryList.value.map(i => i.account).join(';'));

  // +n tooltip 内容：仅展示溢出的数据（不含前导分号）
  const wechatCurrentOverflowTip = computed(() => {
    if (wechatCurrentOverflow.value <= 0) return '';
    const overflowItems = wechatCurrentList.value.slice(MAX_DISPLAY_COUNT);
    return overflowItems.join(';');
  });
  const wechatHistoryOverflowTip = computed(() => {
    if (wechatHistoryOverflow.value <= 0) return '';
    const overflowItems = wechatHistoryList.value.map(i => i.account).slice(MAX_DISPLAY_COUNT);
    return overflowItems.join(';');
  });

  // ========== QQ数据计算 ==========
  const qqHistoryList = computed(() => filterHistoryByType('qq'));
  const qqCurrentList = computed(() => splitAccounts(props.userInfo.qq));

  const qqCurrentTruncated = computed(() => truncateList(qqCurrentList.value, MAX_DISPLAY_COUNT));
  const qqHistoryTruncated = computed(() => truncateList(
    qqHistoryList.value.map(i => i.account),
    MAX_DISPLAY_COUNT,
  ));

  const qqCurrentDisplay = computed(() => {
    const fn = qqVisible.value ? (v: string) => v : maskSingle;
    return qqCurrentTruncated.value.display.map(fn).join(' ; ');
  });

  const qqHistoryDisplay = computed(() => {
    const fn = qqVisible.value ? (v: string) => v : maskSingle;
    return qqHistoryTruncated.value.display.map(fn).join(' ; ');
  });

  const qqCurrentOverflow = computed(() => qqCurrentTruncated.value.overflow);
  const qqHistoryOverflow = computed(() => qqHistoryTruncated.value.overflow);

  const qqRawCurrent = computed(() => qqCurrentList.value.join(';'));
  const qqRawHistory = computed(() => qqHistoryList.value.map(i => i.account).join(';'));

  // +n tooltip 内容：仅展示溢出的数据（不含前导分号）
  const qqCurrentOverflowTip = computed(() => {
    if (qqCurrentOverflow.value <= 0) return '';
    const overflowItems = qqCurrentList.value.slice(MAX_DISPLAY_COUNT);
    return overflowItems.join(';');
  });
  const qqHistoryOverflowTip = computed(() => {
    if (qqHistoryOverflow.value <= 0) return '';
    const overflowItems = qqHistoryList.value.map(i => i.account).slice(MAX_DISPLAY_COUNT);
    return overflowItems.join(';');
  });

  // ========== 复制功能 ==========
  const handleCopy = (text: string) => {
    execCopy(text, t('复制成功'));
  };

  const riskLevelClass = computed(() => {
    const level = props.userInfo.riskLevel;
    if (level === '高') return 'high';
    if (level === '中') return 'medium';
    return 'low';
  });

  // 根据风险等级选择对应的警告图标
  const riskWarningIcon = computed(() => {
    const level = props.userInfo.riskLevel;
    if (level === '高') return warningHighIcon;
    if (level === '中') return warningMediumIcon;
    return warningLowIcon;
  });

  // 查看详情
  const handleViewDetail = () => {
    emit('viewDetail');
  };
</script>

<style scoped lang="postcss">
.top-search {
  padding: 16px 24px 22px;
  margin-top: 12px;
  background: #fff;

  .top-search-title {
    display: flex;
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: #313238;
    align-items: center;
    gap: 8px;
  }
}

/* 用户信息区域 */
.user-info-content {
  display: flex;
  gap: 80px;
}

.user-info-left {
  display: flex;
  flex: 1;
  min-width: 0;
  gap: 16px;
}

.user-detail {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 16px;
}

.detail-row {
  display: flex;
  font-size: 14px;
  line-height: 22px;
  align-items: center;

  .detail-group {
    display: flex;
    width: 50%;
    min-width: 0;
    align-items: center;
    gap: 4px;
  }

  .detail-label {
    display: inline-block;
    width: 80px;
    font-size: 12px;
    color: #4d4f56;
    text-align: right;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .detail-value {
    font-size: 12px;
    color: #313238;
  }

  .eye-icon {
    margin-left: 8px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;
    flex-shrink: 0;

    &:hover {
      color: #3a84ff;
    }
  }

  .copy-icon {
    margin-left: 8px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }
}

/* 微信 / QQ 账号字段样式 */
.account-field {
  position: relative;

  .account-value-wrap {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    max-width: calc(100% - 180px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* 当前标签 - 蓝紫色 */
  .tag-current {
    display: inline-flex;
    width: 32px;
    height: 16px;
    font-size: 10px;
    line-height: 16px;
    color: #3a84ff;
    white-space: nowrap;
    background: #e1efff;
    border-radius: 2px;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  /* 历史标签 - 灰色 */
  .tag-history {
    display: inline-flex;
    width: 32px;
    height: 16px;
    font-size: 10px;
    line-height: 16px;
    color: #4d4f56;
    white-space: nowrap;
    background: #f0f1f5;
    border-radius: 2px;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .account-values {
    font-size: 12px;
    color: #313238;
    white-space: nowrap;
  }

  /* 当前/历史之间的灰色竖线分隔 */
  .divider-line {
    margin: 0 4px;
    font-size: 12px;
    color: #c4c6cc;
    flex-shrink: 0;
  }

  .overflow-count {
    font-size: 12px;
    color: #313238;
    white-space: nowrap;
    flex-shrink: 0;
  }

  /* 复制浮层包裹容器 - 紧跟在眼睛图标后面 */
  .account-copy-wrap {
    position: relative;
    flex-shrink: 0;
    filter: drop-shadow(0 1px 4px rgb(0 0 0 / 15%));
  }

  /* 复制浮层 - 带尖头的白色气泡，紧跟在包裹容器右侧 */
  .account-copy-panel {
    position: absolute;
    top: 50%;
    left: 4px;
    z-index: 100;
    display: inline-flex;
    padding: 8px 12px;
    white-space: nowrap;
    background: #fff;
    border-radius: 2px;
    transform: translateY(-50%);
    gap: 16px;

    /* 左侧尖头（三角形） */
    &::before {
      position: absolute;
      top: 50%;
      left: -5px;
      width: 0;
      height: 0;
      border-top: 5px solid transparent;
      border-right: 5px solid #fff;
      border-bottom: 5px solid transparent;
      content: '';
      transform: translateY(-50%);
    }

    .copy-link {
      position: relative;
      font-size: 12px;
      line-height: 20px;
      color: #3a84ff;
      white-space: nowrap;
      cursor: pointer;

      /* 两个链接之间用灰色竖线分隔 */
      &:not(:last-child)::after {
        position: absolute;
        top: 50%;
        right: -8px;
        width: 1px;
        height: 12px;
        background: #dcdee5;
        content: '';
        transform: translateY(-50%);
      }

      &:hover {
        color: #1768ef;
      }
    }
  }
}

:deep(.status-resigned) {
  color: #c4c6cc !important;
}

.user-info-right {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.stat-card {
  position: relative;
  display: flex;
  width: 240px;
  min-width: 200px;
  padding: 10px 16px;
  overflow: hidden;
  border-radius: 2px;
  flex-direction: column;

  &.responsibility {
    background: #f0f5ff;
  }

  &.risk {
    background: #fff0f0;


    &.high {
      background: #fff0f0;
    }

    &.medium {
      background: #fff8ed;
    }

    &.low {
      background: #f5f7fa;
    }
  }

  .stat-label {
    position: relative;
    z-index: 2;
    display: flex;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    align-items: center;
    justify-content: space-between;

    .view-detail {
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;

      &:hover {
        color: #1768ef;
      }
    }
  }

  .stat-value-row {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-top: 8px;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 700;
    line-height: 40px;
    color: #313238;

    &.risk-level {
      &.high {
        color: #ea3636;
      }

      &.medium {
        color: #ff9c01;
      }

      &.low {
        color: #2dcb56;
      }
    }
  }

  .stat-icon {
    position: absolute;
    top: 50%;
    right: 16px;
    width: 52px;
    height: 56px;
    pointer-events: none;
    opacity: 80%;
    transform: translateY(-50%);
  }
}
</style>
