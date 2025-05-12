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
  <li
    class="item-list item-list-active"
    @click.stop="(e) => handleClick(item, index, e)">
    <span class="item-name">
      {{ item.description || item.field_alias }}
    </span>
    <template
      v-if="item.is_json &&
        item.property &&
        item.property.sub_keys">
      <bk-popover
        ref="subSelectPopover"
        boundary="parent"
        :is-show="isShow"
        placement="bottom"
        theme="light"
        trigger="manual">
        <audit-icon
          v-if="item.property.sub_keys.length > 0"
          class="sub-select-key-icon"
          type="angle-line-down"
          @click="handleOpenPopover" />
        <audit-icon
          v-else
          class="sub-add-key-icon"
          type="add"
          @click="handleOpenPopover" />
        <template #content>
          <setting-field-item
            v-for="(subItem, subIndex) in item.property.sub_keys"
            :key="subItem.field_name || subIndex"
            :index="subIndex"
            :item="subItem"
            :parent-item="item"
            @select="(...args) => emit('select', ...args)" />
          <!-- 添加字段 -->
          <template v-if="item.property.dynamic_content">
            <div
              v-if="!showAdd"
              style="width: 240px;
                  color: #63656e;
                  text-align: center;
                  flex: 1;
                  cursor: pointer;"
              @click="() => showAdd = true">
              <audit-icon
                style="margin-right: 5px;
                    font-size: 14px;
                    color: #979ba5;"
                type="plus-circle" />
              <span>{{ t('自定义字段') }}</span>
              <audit-icon
                v-bk-tooltips="t('解释doris语法下钻逻辑')"
                style=" margin-left: 5px;color: #c4c6cc; cursor: pointer;"
                type="help-fill" />
            </div>
            <div
              v-else
              style="width: 240px;">
              <bk-input
                v-model="customFields"
                autofocus
                :placeholder="t('输入字段ID，多级字段使用“/”分隔')"
                @enter="confirmAdd" />
              <bk-input
                v-model="remark"
                :placeholder="t('输入备注（非必填）')"
                style="margin-top: 8px;"
                @enter="confirmAdd" />
              <div style="margin-top: 8px; text-align: right;">
                <bk-button
                  class="mr8"
                  :disabled="!customFields"
                  size="small"
                  theme="primary"
                  @click="confirmAdd">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  size="small"
                  @click="() => showAdd = false">
                  {{ t('取消') }}
                </bk-button>
              </div>
            </div>
          </template>
        </template>
      </bk-popover>
    </template>
    <span class="item-icon">
      <audit-icon type="right" />
    </span>
  </li>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Emits {
    (e: 'select', item: any, index: number, parentItem: any, event: MouseEvent): void
    (e:'add-sub-field', parentItem: any, newItem: any): void
  }

  interface Props {
    item: any,
    index: number,
    parentItem?: any
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const showAdd = ref(false);
  const customFields = ref('');
  const remark = ref('');
  // const subSelectPopover = ref();
  const isShow = ref(false);

  const handleOpenPopover = () => {
    isShow.value = !isShow.value;
  };

  const handleClick = (item: any, index: number, event: MouseEvent) => {
    emit('select', item, index, props.parentItem, event);
  };

  const confirmAdd = () => {
    if (!props.parentItem) {
      return;
    }
    const fieldPath = customFields.value.split('/').map(str => str.trim())
      .filter(Boolean);
    if (!fieldPath.length) return;

    // 构造新字段对象
    const newItem = {
      field_name: customFields.value,
      field_alias: remark.value || customFields.value,
      is_json: false,
      property: {},
    };
    // 通过事件通知父组件，由父组件去修改数据
    emit('add-sub-field', props.parentItem, newItem);
    // 清空输入框并关闭弹窗
    customFields.value = '';
    remark.value = '';
    showAdd.value = false;
  };
</script>
<style lang="postcss" scoped>
.item-list {
  position: relative;
  display: flex;
  width: 216px;
  height: 32px;
  line-height: 32px;
  color: #63656e;
  cursor: pointer;
  align-items: center;

  .item-icon {
    display: none;
    margin-left: auto;
    font-size: 14px;
    color: #3a84ff;
  }

  .sub-add-key-icon,
  .sub-select-key-icon {
    margin: 0 5px;
    color: #c4c6cc;
  }
}

.not-allowed {
  margin-left: 16px;
  color: lightgray;
  cursor: not-allowed;
}

.item-list-active:hover {
  color: #3a84ff;
  background-color: #edf4ff;
}

.item-list-active:hover .item-icon {
  display: inline-block;
}
</style>
