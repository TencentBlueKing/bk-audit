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
  <div>
    <notice-component
      v-if="showNotice.enabled"
      :api-url="apiUrl"
      @show-alert-change="showAlertChange" />
  </div>
  <div
    class="audit-navigation"
    :class="{
      'is-fixed': isSideMenuFixed,
      'show-notice-navigation': showNotice.enabled && showAlert
    }">
    <div
      class="audit-navigation-side"
      :style="sideStyles">
      <div
        class="audit-navigation-header"
        :class="{
          'show-notice-navigation-header': showNotice.enabled && showAlert
        }">
        <div class="audit-logo">
          <slot name="logo" />
        </div>
        <div>
          <slot name="headerCenter" />
        </div>
        <div class="audit-navigation-body-header-right">
          <slot name="headerRight" />
        </div>
      </div>
      <slot name="sideAppendBefore" />
      <div
        v-if="route.meta?.nodeSideContent"
        class="none-side">
        <slot name="nodeSideContent" />
      </div>
      <div
        v-if="!route.meta?.nodeSideContent"
        class="audit-side-menu"
        :class="{
          'show-notice-side-menu': showNotice.enabled && showAlert
        }"
        @mouseenter="handleSideMouseenter"
        @mouseleave="handleSideMouseleave">
        <scroll-faker theme="dark">
          <slot name="side" />
        </scroll-faker>
      </div>
      <div
        v-if="!route.meta?.nodeSideContent"
        class="audit-side-toggle-btn">
        <audit-icon
          class="fixed-flag"
          :class="{'is-open': isSideMenuFixed}"
          type="navi-expand"
          @click.stop="handleSideFlodToggle" />
      </div>
    </div>
    <div
      class="audit-navigation-main"
      :class="{
        'show-notice-navigation-main': showNotice.enabled
      }"
      :style="mainStyles">
      <div
        id="headerTips"
        ref="headerTipsRef">
        <slot name="headerTips" />
      </div>
      <div class="page-title">
        <slot name="header" />
      </div>
      <!-- <div
        class="audit-navigation-body-header"
        :style="bodyHeaderStyles">
        <slot name="header" />
      </div> -->
      <scroll-faker
        id="auditNavigationContent"
        ref="contentScroll"
        :style="scrollStyles">
        <div
          class="audit-navigation-content"
          :style="contentStyles">
          <div class="navigation-content-wrapper">
            <slot />
          </div>
        </div>
      </scroll-faker>
    </div>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import { useRoute } from 'vue-router';

  import useEventBus from '@hooks/use-event-bus';
  import useFeature from '@hooks/use-feature';

  import NoticeComponent from '@blueking/notice-component';

  interface Emits{
    (e: 'menu-flod', value: boolean):void
  }
  const emit = defineEmits<Emits>();
  const { emit: emits } = useEventBus();
  const { feature: showNotice } = useFeature('bknotice');
  const route = useRoute();
  const apiUrl = `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/api/v1/bk-notice/announcements/`;
  // const TOGGLE_CACHE = 'navigation_toggle_status';
  const PAGE_MIN_WIDTH = 1366;
  const PAGE_MIDDLE_WIDTH = 1920;
  const SIDE_LEFT_EXPAND_SMALL_WIDTH = 220;
  const SIDE_LEFT_EXPAND_BIG_WIDTH = 280;
  const SIDE_LEFT_INEXPAND_WIDTH = 60;

  // const isSideMenuFixed = ref(Boolean(localStorage.getItem(TOGGLE_CACHE)));
  const isSideMenuFixed = ref(true);

  const isSideMenuHover = ref(false);
  const pageWidth = ref(PAGE_MIN_WIDTH);
  const sideLeftExpandWidth = ref();

  const realSideWidth = computed(() => (
    isSideMenuFixed.value
      ? sideLeftExpandWidth.value
      : SIDE_LEFT_INEXPAND_WIDTH));
  const zIndex = ref(1999);
  const sideStyles = computed(() => {
    if (isSideMenuHover.value) {
      return {
        width: `${sideLeftExpandWidth.value}px`,
        zIndex: zIndex.value,
      };
    }
    return {
      width: `${realSideWidth.value}px`,
      zIndex: zIndex.value,
    };
  });

  const mainStyles = computed(() => ({
    paddingTop: '52px',
    marginLeft: `${realSideWidth.value}px`,
    zIndex: 1999,
  }));
  // const bodyHeaderStyles = computed(() => ({
  //   left: `${realSideWidth.value}px`,
  // }));
  // 在 script setup 部分添加
  const headerTipsRef = ref<HTMLElement | null>(null);


  const scrollStyles = computed(() => {
    let headerTipsHeight = 0;
    if (headerTipsRef.value) {
      headerTipsHeight = 32;
    }

    const contentHeaderHeight = showNotice.value.enabled && showAlert.value ? 144 : 104;
    return {
      width: `calc(100vw - ${realSideWidth.value}px)`,
      height: `calc(100vh - ${contentHeaderHeight + headerTipsHeight}px)`,
    };
  });


  const contentStyles = computed(() => ({
    width: `${pageWidth.value - realSideWidth.value}px`,
  }));

  const init = () => {
    const windowInnerWidth = window.innerWidth;
    pageWidth.value = windowInnerWidth < PAGE_MIN_WIDTH ? PAGE_MIN_WIDTH : windowInnerWidth;
    sideLeftExpandWidth.value = windowInnerWidth < PAGE_MIDDLE_WIDTH
      ? SIDE_LEFT_EXPAND_SMALL_WIDTH
      : SIDE_LEFT_EXPAND_BIG_WIDTH;
  };
  /**
   * @desc 鼠标移入
   */
  let hoverTimer = 0;
  let delayIndexTimer = 0;
  const handleSideMouseenter = () => {
    if (isSideMenuFixed.value) {
      return;
    }
    clearTimeout(hoverTimer);
    zIndex.value = 4000;
    hoverTimer = setTimeout(() => {
      isSideMenuHover.value = true;
      emit('menu-flod', false);
    }, 50);
  };
  /**
   * @desc 鼠标移出
   */
  const handleSideMouseleave = () => {
    if (isSideMenuFixed.value) {
      return;
    }
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      isSideMenuHover.value = false;
      emit('menu-flod', true);

      clearTimeout(delayIndexTimer);
      delayIndexTimer = setTimeout(() => {
        zIndex.value = 1999;
      }, 20);
    }, 50);
  };
  /**
   * @desc 切换左侧面板是否固定的状态
   */
  const handleSideFlodToggle = () => {
    isSideMenuFixed.value = !isSideMenuFixed.value;
    // if (isSideMenuFixed.value) {
    //   localStorage.setItem(TOGGLE_CACHE, 'true');
    // } else {
    //   localStorage.setItem(TOGGLE_CACHE, '');
    // }
    if (!isSideMenuFixed.value) {
      emit('menu-flod', isSideMenuFixed.value);
    }
  };
  const resizeHandler = _.throttle(init, 100);

  onMounted(() => {
    init();
    emit('menu-flod', !isSideMenuFixed.value);
    window.addEventListener('resize', resizeHandler);
  });
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeHandler);
  });

  const showAlert = ref(false);
  const showAlertChange = (isShow: boolean) => {
    showAlert.value = isShow;
    // 发送通知中心状态两个条件：1.拥有enable权限，2.通知中心有内容
    emits('show-notice', showNotice.value.enabled && isShow);
  };
</script>
<style lang="postcss">
.audit-navigation {
  line-height: 19px;

  &.is-field {
    .fixed-flag {
      transform: rotateZ(180deg) !important;
    }

    .audit-navigation-side {
      transition: none;
    }

    .audit-navigation-main {
      margin-left: 220px;
    }
  }

  .page-title {
    /* 解决投影被遮挡问题 */
    position: relative;
    z-index: 1;
    display: flex;
    height: 52px;
    padding: 0 20px;
    margin-left: 1px;
    font-size: 16px;
    line-height: 52px;
    color: #313238;
    background: #fff;
    transform: translate3d(0, 0, 0);

    /* box-shadow: 0 1px 0 0 #eaebf0; */
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
    align-items: center;
  }

  .audit-navigation-header {
    position: fixed;
    top: 0;
    right: 0;
    left: 0;
    display: flex;
    height: 52px;
    min-width: 1200px;
    padding-right: 24px;
    font-size: 14px;
    color: #96a2b9;
    background: #182132;
    box-shadow: 0 1px 0 0 rgb(255 255 255 / 10%);
    align-items: center;
  }

  .audit-navigation-side {
    position: fixed;
    top: 52px;
    bottom: 0;
    left: 0;
    z-index: 2000;
    display: flex;
    width: 220px;
    font-size: 14px;
    background: #2c354d;
    transition: all .3s;
    flex-direction: column;

    .audit-side-menu {
      width: 100%;
      overflow: hidden;
      flex: 1 1 auto;
    }

    .audit-side-toggle-btn {
      display: flex;
      height: 56px;
      margin-top: auto;
      margin-left: 16px;
      font-size: 16px;
      color: #747e94;
      align-items: center;

      .fixed-flag {
        padding: 8px;
        cursor: pointer;
        border-radius: 50%;
        transform: rotateZ(0deg);
        transition: all .15s;

        &:hover {
          color: #d3d9e4;
          background: linear-gradient(270deg, #253047, #263247);
        }
      }

      .is-open {
        transform: rotateZ(180deg) !important;
      }
    }
  }

  .audit-navigation-body-header {
    position: fixed;
    top: 0;
    right: 0;
    left: 220px;
    z-index: 1999;
    display: flex;
    align-items: center;
    height: 52px;
    padding-right: 24px;
    padding-left: 24px;
    font-size: 16px;
    color: #313238;
    background: #fff;
    box-shadow: 0 2px 4px 0 rgb(0 0 0 / 10%);
  }

  .audit-navigation-body-header-right {
    display: flex;
    align-items: center;
    margin-left: auto;
  }

  .audit-navigation-content {
    .navigation-content-wrapper {
      position: relative;
      padding: 20px 24px 0;
    }
  }

  .audit-logo {
    display: flex;
    align-items: center;
    min-width: 238px;
  }
}

.show-notice-navigation {
  height: calc(100vh - 40px);
  overflow: hidden;
}

.show-notice-navigation-main {
  height: calc(100vh - 40px);
}

.show-notice-side-menu {
  padding-top: 40px;
}

.show-notice-navigation-header {
  top: 40px !important;
}

.none-side {
  width: 100vw;
  height: 100%;
  background: #fff;
}
</style>
