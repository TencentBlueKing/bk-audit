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
  <div class="scene-sidebar">
    <!-- 场景信息 -->
    <audit-menu-item
      :class="{ active: currentRoute === 'sceneInfo' }"
      index="sceneInfo"
      @click="handleMenuClick('sceneInfo')">
      <audit-icon
        class="menu-item-icon"
        type="rule" />
      {{ t('场景信息') }}
    </audit-menu-item>

    <!-- 审计配置分组 -->
    <div class="side-group">
      <div
        class="side-group-header"
        @click="toggleGroup('auditConfig')">
        <audit-icon
          class="side-group-icon"
          type="setting" />
        <span class="side-group-name">{{ t('审计配置') }}</span>
        <audit-icon
          class="side-group-arrow"
          :class="{ expanded: expandedGroups.includes('auditConfig') }"
          type="angle-line-down" />
      </div>
      <div
        v-show="expandedGroups.includes('auditConfig')"
        class="side-group-children">
        <audit-menu-item
          :class="{ active: currentRoute === 'strategyManage' }"
          index="strategyManage"
          @click="handleMenuClick('strategyManage')">
          <span class="side-child-dot" />
          {{ t('审计策略') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'linkDataManage' }"
          index="linkDataManage"
          @click="handleMenuClick('linkDataManage')">
          <span class="side-child-dot" />
          {{ t('联表管理') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'applicationManage' }"
          index="applicationManage"
          @click="handleMenuClick('applicationManage')">
          <span class="side-child-dot" />
          {{ t('处理套餐') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'ruleManage' }"
          index="ruleManage"
          @click="handleMenuClick('ruleManage')">
          <span class="side-child-dot" />
          {{ t('处理规则') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'noticeGroup' }"
          index="noticeGroup"
          @click="handleMenuClick('noticeGroup')">
          <span class="side-child-dot" />
          {{ t('通知组') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'storageManage' }"
          index="storageManage"
          @click="handleMenuClick('storageManage')">
          <span class="side-child-dot" />
          {{ t('数据存储') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'systemList' }"
          index="systemList"
          @click="handleMenuClick('systemList')">
          <span class="side-child-dot" />
          {{ t('系统列表') }}
        </audit-menu-item>
      </div>
    </div>

    <!-- 场景资源分组 -->
    <div class="side-group">
      <div
        class="side-group-header"
        @click="toggleGroup('sceneResource')">
        <audit-icon
          class="side-group-icon"
          type="baobiao" />
        <span class="side-group-name">{{ t('场景资源') }}</span>
        <audit-icon
          class="side-group-arrow"
          :class="{ expanded: expandedGroups.includes('sceneResource') }"
          type="angle-line-down" />
      </div>
      <div
        v-show="expandedGroups.includes('sceneResource')"
        class="side-group-children">
        <audit-menu-item
          :class="{ active: currentRoute === 'sceneReportConfig' }"
          index="sceneReportConfig"
          @click="handleMenuClick('sceneReportConfig')">
          <span class="side-child-dot" />
          {{ t('报表管理') }}
        </audit-menu-item>
        <audit-menu-item
          :class="{ active: currentRoute === 'sceneToolManege' }"
          index="sceneToolManege"
          @click="handleMenuClick('sceneToolManege')">
          <span class="side-child-dot" />
          {{ t('工具管理') }}
        </audit-menu-item>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import AuditMenuItem from '@components/audit-menu/item.vue';

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();

  // 当前激活的路由
  const currentRoute = computed(() => route.name as string);

  // 展开的分组列表
  const expandedGroups = ref<string[]>(['auditConfig', 'sceneResource']);

  // 切换分组展开/收起
  const toggleGroup = (groupId: string) => {
    const index = expandedGroups.value.indexOf(groupId);
    if (index > -1) {
      expandedGroups.value.splice(index, 1);
    } else {
      expandedGroups.value.push(groupId);
    }
  };

  // 菜单点击处理
  const handleMenuClick = (routeName: string) => {
    router.push({ name: routeName });
  };

  // 监听路由变化，自动展开对应分组
  watch(() => route.name, (newRouteName) => {
    const auditConfigRoutes = ['strategyManage', 'linkDataManage', 'applicationManage', 'ruleManage', 'noticeGroup'];
    const sceneResourceRoutes = ['reportConfig', 'toolsManage'];

    if (auditConfigRoutes.includes(newRouteName as string) && !expandedGroups.value.includes('auditConfig')) {
      expandedGroups.value.push('auditConfig');
    }
    if (sceneResourceRoutes.includes(newRouteName as string) && !expandedGroups.value.includes('sceneResource')) {
      expandedGroups.value.push('sceneResource');
    }
  }, { immediate: true });
</script>

<style lang="postcss" scoped>
  .scene-sidebar {
    width: 100%;
  }

  .menu-item-icon {
    margin-right: 10px;
    font-size: 16px;
  }

  .side-group {
    margin-bottom: 2px;
  }

  .side-group-header {
    display: flex;
    align-items: center;
    height: 40px;
    padding: 0 22px;
    font-size: 14px;
    color: #acb9d1;
    cursor: pointer;

    &:hover {
      background: #253047;
    }
  }

  .side-group-icon {
    margin-right: 10px;
    font-size: 16px;
    color: #acb9d1;
  }

  .side-group-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .side-group-arrow {
    font-size: 12px;
    color: #acb9d1;
    transition: transform .2s ease;

    &.expanded {
      transform: rotate(0deg);
    }

    &:not(.expanded) {
      transform: rotate(-90deg);
    }
  }

  .side-group-children {
    :deep(.audit-menu-item) {
      position: relative;
      padding-left: 36px;
    }
  }

  .side-child-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 12px;
    background: #505562;
    border-radius: 50%;
    flex-shrink: 0;
  }

  :deep(.audit-menu-item.active) {
    .side-child-dot {
      background: #fff;
    }
  }
</style>

