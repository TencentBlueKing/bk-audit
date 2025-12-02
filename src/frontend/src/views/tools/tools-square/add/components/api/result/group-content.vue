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
  <vuedraggable
    class="draggable-box"
    :group="{
      name: 'field',
      pull: false,
      push: true
    }"
    item-key="key"
    :list="localValue"
    @change="handelValueDragChange">
    <template #item="{ element }">
      <div
        class="draggable-element">
        <div class="draggable-heard">
          <audit-icon
            class="move"
            type="move" />
          <span v-if="!element.isInput">
            <audit-icon
              class="angle-fill-down"
              :style="element.isOpen ? '' : 'transform: rotate(180deg);' "
              type="angle-fill-down"
              @click.stop="handelOpenUp(element)" />
            <span class="heard-title"> {{ element.val }}</span>
            <audit-icon
              class="edit-fill"
              type="edit-fill"
              @click.stop="handleEdit(element.key)" />
          </span>
          <span v-else>
            <bk-input
              :model-value="element.val"
              @blur="handleBlur(element.key)"
              @change="(value) => handlechange(value, element.key)" />
          </span>
          <audit-icon
            class="delete"
            type="delete"
            @click.stop="handleDelete(element.key)" />
        </div>
        <content
          v-if="element.isOpen"
          :result-data="resultData" />
      </div>
    </template>
  </vuedraggable>
</template>
<script setup lang='ts'>
  import { ref } from 'vue';
  import Vuedraggable from 'vuedraggable';

  import content from './content.vue';


  interface Props {
    resultData: any,
  }
  defineProps<Props>();
  const localValue = ref([
    {
      key: '1',
      val: '分组1',
      isInput: false,
      isOpen: true,
    },
  ]);
  // 拖拽
  const handelValueDragChange = (dragEvent: any) => {
    console.log('dragEvent', dragEvent);
  };
  const handlechange = (value: string, key: string) => {
    console.log('value', value);
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === key) {
        // eslint-disable-next-line no-param-reassign
        item.val = value;
      }
      return item;
    });
  };
  const handleEdit = (val: string) => {
    console.log('val', val);
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === val) {
        // eslint-disable-next-line no-param-reassign
        item.isInput = true;
      }
      return item;
    });
  };
  const handleBlur = (val: string) => {
    console.log('handleBlur', val);
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === val) {
        // eslint-disable-next-line no-param-reassign
        item.isInput = false;
      }
      return item;
    });
  };

  // 打开收起
  const handelOpenUp = (element: any) => {
    console.log('element>>', element);
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === element.key) {
        // eslint-disable-next-line no-param-reassign
        item.isOpen = !item.isOpen;
      }
      return item;
    });
  };

  // 删除
  const handleDelete = (val: string) => {
    console.log('val', val);
  };
</script>

<style lang="postcss" scoped>
.draggable-box {
  .draggable-element {
    position: relative;
    padding-top: 10px;
    cursor: pointer;

    .draggable-heard {
      display: flex;
      height: 32px;
      padding: 0 10px;
      vertical-align: middle;
      background: #f0f1f5;
      border-radius: 2px;
      align-items: center;

      .move {
        color: #c4c6cc;
        cursor: move;
      }

      .angle-fill-down {
        display: inline-block;
        color: #979ba5;
      }

      .heard-title {
        margin-left: 5px;
        font-size: 12px;
        font-weight: 700;
        line-height: 20px;
        letter-spacing: 0;
        color: #313238;
      }

      .edit-fill {
        margin-left: 5px;
        font-size: 16px;
        color: #c4c6cc;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      .delete {
        position: absolute;
        right: 5px;
        font-size: 16px;
        color: #ea3636;
        cursor: pointer;
      }
    }
  }
}
</style>
