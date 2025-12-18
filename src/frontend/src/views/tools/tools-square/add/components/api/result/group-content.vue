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
            <span class="heard-title"> {{ element.name }}</span>
            <audit-icon
              class="edit-fill"
              type="edit-fill"
              @click.stop="handleEdit(element.key)" />
          </span>
          <span v-else>
            <bk-input
              :model-value="element.name"
              @blur="handleBlur(element.key)"
              @change="(value: any) => handlechange(value, element.key)" />
          </span>
          <audit-icon
            class="delete"
            :style="localValue.length === 1 ? 'color: #979ba5;cursor: not-allowed;' : ''"
            type="delete"
            @click.stop="handleDelete(element.key)" />
        </div>
        <content
          v-if="element.isOpen"
          ref="contentRef"
          :group-key="element.key"
          :group-output-fields="element.output_fields"
          :is-edit-mode="isEditMode"
          :is-grouping="isGrouping"
          :result-data="resultData"
          @group-content-change="handleGroupContentChange" />
      </div>
    </template>
  </vuedraggable>
</template>
<script setup lang='ts'>
  import { nextTick, ref } from 'vue';
  import Vuedraggable from 'vuedraggable';

  import content from './content.vue';

  interface Props {
    resultData: any,
    isEditMode: boolean,
    isGrouping: boolean,
  }
  interface Exposes {
    addGroup:() => void,
    openGroup:(val: boolean) => void,
    handleGetResultConfig: () => void;
    setConfigs:(data: any) => void;
  }

  defineProps<Props>();
  const contentRef = ref();
  const localValue = ref([
    {
      name: '分组',
      isInput: false,
      isOpen: true,
      key: Date.now().toString(),
      config: null,
      output_fields: [],
    },
  ]);
  // 拖拽
  const handelValueDragChange = (dragEvent: any) => {
    console.log('dragEvent', dragEvent);
  };
  const handlechange = (value: string, key: string) => {
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === key) {
        // eslint-disable-next-line no-param-reassign
        item.name = value;
      }
      return item;
    });
  };
  const handleEdit = (val: string) => {
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === val) {
        // eslint-disable-next-line no-param-reassign
        item.isInput = true;
      }
      return item;
    });
  };
  const handleBlur = (val: string) => {
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
    if (localValue.value.length > 1) {
      localValue.value = localValue.value.filter((item: any) => item.key !== val);
    }
  };
  // 监听分组内容改变
  const handleGroupContentChange = (val: any, key: string | number) => {
    // 把val赋值给对应key的 item.config
    localValue.value = localValue.value.map((item: any) => {
      if (item.key === key) {
        // eslint-disable-next-line no-param-reassign
        item.config = val;
      }
      return item;
    });
  };
  defineExpose<Exposes>({
    // 添加组 key 当前时间戳
    addGroup() {
      // 生成不重复的分组名称
      const generateUniqueGroupName = () => {
        const existingNames = localValue.value.map(item => item.name);
        let maxNumber = 0;
        // 查找现有分组名称中的最大数字
        existingNames.forEach((name: string) => {
          const match = name.match(/^分组(\d+)$/);
          if (match) {
            const num = parseInt(match[1], 10);
            if (num > maxNumber) {
              maxNumber = num;
            }
          }
        });
        // 如果没有任何数字分组，从1开始
        if (maxNumber === 0) {
          maxNumber = existingNames.filter(name => name === '分组').length;
        }
        return `分组${maxNumber + 1}`;
      };
      localValue.value.push({
        name: generateUniqueGroupName(),
        isInput: false,
        isOpen: true,
        key: Date.now().toString(),
        config: null,
        output_fields: [],
      });
    },
    openGroup(val: boolean) {
      localValue.value = localValue.value.map((item: any) => {
        // eslint-disable-next-line no-param-reassign
        item.isOpen = !val;
        return item;
      });
    },
    // 提交获取内容
    handleGetResultConfig() {
      return localValue.value;
    },
    setConfigs(data: any) {
      localValue.value = data.map((item: any, index: number) => ({
        name: item.name,
        isInput: false,
        isOpen: true,
        key: Date.now().toString() + index,
        config: null,
        output_fields: item.output_fields,
      }));
      nextTick(() => {
        // console.log('!!!', contentRef.value);
        // contentRef.value?.setGroupConfigs(localValue.value);
      });
    },
  });
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
