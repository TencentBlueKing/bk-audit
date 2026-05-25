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
          <!-- 第2行：微信（脱敏） | QQ（脱敏） -->
          <div class="detail-row">
            <div
              class="detail-group"
              @mouseenter="hoverField = 'wechat'"
              @mouseleave="hoverField = ''">
              <span class="detail-label">{{ t('微信') }}：</span>
              <span class="detail-value">{{ wechatDisplay }}</span>
              <audit-icon
                class="eye-icon"
                :type="wechatVisible ? 'view' : 'unview'"
                @click="wechatVisible = !wechatVisible" />
              <audit-icon
                v-if="hoverField === 'wechat'"
                class="copy-icon"
                type="copy"
                @click="handleCopy(userInfo.wechat)" />
            </div>
            <div
              class="detail-group"
              @mouseenter="hoverField = 'qq'"
              @mouseleave="hoverField = ''">
              <span class="detail-label">QQ：</span>
              <span class="detail-value">{{ qqDisplay }}</span>
              <audit-icon
                class="eye-icon"
                :type="qqVisible ? 'view' : 'unview'"
                @click="qqVisible = !qqVisible" />
              <audit-icon
                v-if="hoverField === 'qq'"
                class="copy-icon"
                type="copy"
                @click="handleCopy(userInfo.qq)" />
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
  }

  interface Emits {
    (e: 'viewDetail'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  // 眼睛图标控制显示/隐藏
  const wechatVisible = ref(false);
  const qqVisible = ref(false);

  // hover 状态
  const hoverField = ref('');

  // 脱敏单个账号
  const maskSingle = (value: string) => {
    if (!value) return '';
    if (value.length <= 2) return value;
    return `${value[0]}${'*'.repeat(value.length - 2)}${value[value.length - 1]}`;
  };

  // 脱敏显示（支持多账号，仅使用英文分号 ; 分隔，输出以 "; " 拼接）
  const maskValue = (value: string) => {
    if (!value) return '';
    const parts = String(value)
      .split(';')
      .map(v => v.trim())
      .filter(Boolean);
    if (parts.length <= 1) return maskSingle(parts[0] || '');
    return parts.map(maskSingle).join(' ; ');
  };

  // 明文显示时，仅按 ; 分隔并统一以 " ; " 拼接（与脱敏态保持一致）
  const formatValue = (value: string) => {
    if (!value) return '';
    const parts = String(value)
      .split(';')
      .map(v => v.trim())
      .filter(Boolean);
    return parts.join(' ; ');
  };

  // 计算微信/QQ 的最终展示文本（控制行长度）
  const wechatDisplay = computed(() => (
    wechatVisible.value ? formatValue(props.userInfo.wechat) : maskValue(props.userInfo.wechat)
  ));
  const qqDisplay = computed(() => (
    qqVisible.value ? formatValue(props.userInfo.qq) : maskValue(props.userInfo.qq)
  ));

  // 复制功能
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
