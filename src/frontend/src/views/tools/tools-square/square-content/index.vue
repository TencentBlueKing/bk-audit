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
  <div class="square-content">
    <div class="heard-tag">
      <div
        class="heard-left"
        :class="{ 'collapsed': isCollapsed }">
        <bk-tag
          v-for="tag in tags"
          :key="tag"
          checkable
          :checked="checkedTags.includes(tag)"
          :style="checkedTags.includes(tag) ? tagStyle : checkedTagStyle"
          @change="(checked: any) => handleCheckChange(checked, tag)">
          {{ tag }}
        </bk-tag>
      </div>
      <div
        class="heard-right"
        @click="toggleCollapse">
        <span v-if="!isCollapsed"> {{ t('收起') }} <audit-icon type="angle-double-up" /></span>
        <span v-else> {{ t('展开') }} <audit-icon type="angle-double-down" /></span>
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Emits {
    (e: 'handle-checked-tags', tags: Array<string>): void;
  }
  interface Exposes {
    checkedTags: Array<string>;
    clearCheckedTags: () => void;
  }
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const isCollapsed = ref(true);
  const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
  };
  const tags = ref([
    '企业邮箱', '腾讯视频', '蓝鲸智云', '企业微信', '场景1', '场景2', '场景3',
    '场景4', '场景5', '场景6', '场景7', '场景8', '场景9', '场景10', '场景11', '场景12', '场景13',
    '场景14', '场景15', '场景16', '场景17', '场景18', '场景19', '场景20', '场景21', '场景22',
    '场景23', '场景24', '场景25', '场景26', '场景27', '场景28', '场景29', '场景30', '场景31', '场景32',
    '场景33', '场景34', '场景35', '场景36',
  ]);
  const checkedTags = ref<string[]>([]);
  const tagStyle = ref({
    background: '#E1ECFF',
    color: '#1768EF',
  });

  const checkedTagStyle = ref({
    background: '#ffffff',
    color: '#4D4F56',
  });

  const handleCheckChange = (checked: any, tag: string) => {
    if (checked && !checkedTags.value.includes(tag)) {
      checkedTags.value.push(tag);
    } else {
      checkedTags.value = checkedTags.value.filter(tagItem => tagItem !== tag);
    }
  };

  watch(() => checkedTags.value, (val) => {
    emit('handle-checked-tags', val);
  }, {
    deep: true,
    immediate: true,
  });

  defineExpose<Exposes>({
    get checkedTags() {
      return [...checkedTags.value]; // 返回副本避免直接修改
    },
    clearCheckedTags() {
      checkedTags.value = [];
      emit('handle-checked-tags', []); // 明确传递空数组
    },
  });
</script>

<style scoped lang="postcss">
.square-content {
  .heard-tag {
    display: flex;
    justify-content: space-between;

    .heard-left {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;

      &.collapsed {
        max-height: 30px;
        overflow: hidden;
      }
    }

    .heard-right {
      display: flex;
      width: 120px;
      color: #3a84ff;
      text-align: right;
      cursor: pointer;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #1768ef;
      }
    }
  }

  :deep(.bk-tag) {
    &:hover {
      background-color: #f0f1f5 !important;
    }
  }
}
</style>
