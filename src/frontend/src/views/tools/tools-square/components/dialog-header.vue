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
  <div class="form-item">
    <div
      v-show="isOverflow"
      class="top-icon">
      <audit-icon
        class="left-icon"
        type="angle-line-down"
        @click="handlerClickLeft" />
    </div>
    <div
      ref="itemRef"
      class="item">
      <div
        v-for="item in tabs"
        :key="item.uid">
        <div
          v-bk-tooltips="{
            disabled: !isTextOverflow(item?.name || '', 0, '180px', { isSingleLine: true }),
            content: t(item?.name || ''),
            placement: 'top',
          }"
          :class="activeId === item.uid ? `form-item-label active-item` : `form-item-label`"
          @click="handlerClickItem(item)">
          {{ item.name }}
        </div>
      </div>
    </div>

    <div
      v-show="isOverflow"
      class="top-icon">
      <audit-icon
        class="right-icon"
        type="angle-line-down"
        @click="handlerClickRight" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface tabsItem {
    uid: string;
    name: string;
  }

  interface Exposes {
    initTabsValue: (tabsList: any, id: string) => void;
  }

  interface Props {
    tabs: Array<tabsItem>;
  }

  interface Emits {
    (e: 'clickItem', item: tabsItem): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const activeId = ref('');

  const tabs = ref<Array<tabsItem>>(props.tabs);

  const itemRef = ref();
  const isOverflow = ref(false);
  const resizeObserver = ref();
  const beforeActiveIndex = ref(0);

  // 点击tab
  const handlerClickItem = (itemInfo: any) => {
    activeId.value = itemInfo.uid;
    emit('clickItem', itemInfo);
    if (isOverflow.value) {
      const activeIndex = tabs.value.findIndex(item => item.uid === itemInfo.uid);
      if (beforeActiveIndex.value > activeIndex) {
        itemRef.value.scrollLeft -= 100 * (beforeActiveIndex.value - activeIndex);
      } else {
        itemRef.value.scrollLeft += 100 * (activeIndex - beforeActiveIndex.value);
      }
      setTimeout(() => {
        beforeActiveIndex.value = tabs.value.findIndex(item => item.uid === itemInfo.uid);
      }, 0);
    }
  };

  // 点击右侧按钮
  const handlerClickRight = () => {
    if (itemRef.value && isOverflow.value) {
      itemRef.value.scrollLeft += 150;
    }
  };

  // 点击左侧按钮
  const handlerClickLeft = () => {
    if (itemRef.value && isOverflow.value) {
      itemRef.value.scrollLeft -= 150;
    }
  };

  // 文本溢出检测
  const isTextOverflow = (text: string, maxHeight = 0, width: string, options: {
    isSingleLine?: boolean;
    fontSize?: string;
    fontWeight?: string;
    lineHeight?: string;
  } = {}) => {
    if (!text) return false;

    const {
      isSingleLine = maxHeight === 0, // 默认单行检测
      fontSize = isSingleLine ? '16px' : '14px',
      fontWeight = isSingleLine ? '700' : 'normal',
      lineHeight = '22px',
    } = options;

    const temp = document.createElement('div');
    temp.style.position = 'absolute';
    temp.style.visibility = 'hidden';
    temp.style.width = width;
    temp.style.fontSize = fontSize;
    temp.style.fontWeight = fontWeight;
    temp.style.fontFamily = 'inherit';
    temp.style.lineHeight = lineHeight;
    temp.style.boxSizing = 'border-box';
    temp.textContent = text;

    if (isSingleLine) {
      temp.style.whiteSpace = 'nowrap';
      temp.style.overflow = 'visible';
    } else {
      temp.style.display = '-webkit-box';
      temp.style.webkitLineClamp = '2';
      temp.style.overflow = 'hidden';
    }

    document.body.appendChild(temp);

    const isOverflow = maxHeight > 0
      ? temp.scrollHeight > maxHeight
      : temp.scrollWidth > temp.offsetWidth;

    document.body.removeChild(temp);
    return isOverflow;
  };

  const checkOverflow = () => {
    setTimeout(() => {
      if (itemRef.value) {
        isOverflow.value = itemRef.value.scrollWidth > itemRef.value.clientWidth;
      }
    });
  };

  onMounted(() => {
    resizeObserver.value = new ResizeObserver(() => {
      checkOverflow();
    });
    if (itemRef.value) {
      resizeObserver.value.observe(itemRef.value);
    }
  });

  onUnmounted(() => {
    if (resizeObserver.value && itemRef.value) {
      resizeObserver.value.unobserve(itemRef.value);
      resizeObserver.value.disconnect();
    }
  });

  defineExpose<Exposes>({
    initTabsValue(tabsList: Array<tabsItem>, id: string) {
      tabs.value = tabsList;
      activeId.value = id;
    },
  });
</script>
<style lang="postcss" scoped>
.form-item {
  display: flex;
  width: calc(100% - 70px);
  height: 42px;
  font-size: 14px;
  line-height: 22px;
  letter-spacing: 0;
  color: #4d4f56;
  align-items: center;

  .top-icon {
    position: relative;
    width: 20px;
    height: 42px;
    padding: 0;
    cursor: pointer;
    background: #fafbfd;
    border: 1px solid #dcdee5;
  }

  .left-icon {
    position: absolute;
    top: 50%;
    left: 50%;
    display: inline-block;
    transform: translate(-50%, -50%)  rotate(90deg);
  }

  .right-icon {
    position: absolute;
    top: 50%;
    left: 50%;
    display: inline-block;
    transform: translate(-50%, -50%)  rotate(-90deg);
  }

  .item {
    display: flex;
    width: 100%;
    height: 100%;
    overflow: auto;
    scrollbar-width: none;

    .form-item-label {
      height: 100%;
      max-width: 180px;
      min-width: 100px;
      padding-right: 5px;
      padding-left: 5px;
      overflow: hidden;
      line-height: 42px;
      text-align: center;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
      background: #fafbfd;
      border: 1px solid #dcdee5;
    }

    .active-item {
      color: #3a84ff;
      background: #fff;
      border: 1px solid #dcdee5;
    }
  }

}
</style>
