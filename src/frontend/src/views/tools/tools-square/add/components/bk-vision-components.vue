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
  <div class="bk-vision-component">
    <div class="component">
      <div class="lable">
        {{ props.config?.title }}
      </div>
      <div class="content">
        <bk-date-picker
          v-if="props.config?.type === 'time-picker'"
          v-model="dateValue"
          format="yyyy-MM-dd HH:mm:ss"
          :shortcuts="dateShortCut"
          type="datetime"
          use-shortcut-text
          @change="handlePickerChange" />
        <date-picker
          v-if="props.config?.type === 'time-ranger'"
          v-model="pickerValue"
          style="width: 100%;"
          @update:model-value="handleRangeChange" />

        <bk-input
          v-if="props.config?.type === 'inputer'"
          v-model="inputVal"
          @change="handleInputChange" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { ref, watch } from 'vue';


  interface Props {
    config: any;
  }
  interface Emits {
    (e: 'change', value: any): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const now = new Date();
  const dateValue = ref(props.config.value || new Date());
  const pickerValue = ref<Array<string>>(props.config.value || []);
  const inputVal = ref(props.config.value || []);

  const dateShortCut: any = [
    {
      text: '今天',
      value: () => getLastMillisecondOfDate(now.getTime()),
      short: 'now/d',
    },
    {
      text: '昨天',
      value: () => getLastMillisecondOfDate(now.getTime() - 1 * 24 * 60 * 60 * 1000),
      short: 'now-1d/d',
    },
    {
      text: '前天',
      value: () => getLastMillisecondOfDate(now.getTime() - 2 * 24 * 60 * 60 * 1000),
      short: 'now-2d/d',
    },
    {
      text: '一星期前',
      value: () => getLastMillisecondOfDate(now.getTime() - 7 * 24 * 60 * 60 * 1000),
      short: 'now-7d/d',
    },
    {
      text: '一个月前',
      value: () => getLastMillisecondOfDate(now.getTime() - 30 * 24 * 60 * 60 * 1000),
      short: 'now-1M/d',
    },
    {
      text: '一年前',
      value: () => getLastMillisecondOfDate(now.getTime() - 365 * 24 * 60 * 60 * 1000),
      short: 'now-1y/d',
    },
  ];
  const getLastMillisecondOfDate = (ts: any) => {
    const date = new Date(ts);
    date.setHours(0, 0, 0, 0);
    return date;
  };

  const handlePickerChange = (val: Date) => {
    dateValue.value = val;
    emits('change', val || '');
  };
  const handleRangeChange = (val: Array<string>) => {
    pickerValue.value = val;
    emits('change', val || []);
  };
  const handleInputChange = (val: string) => {
    inputVal.value = val;
    emits('change', val || '');
  };
  // 监听 props.config.value 的变化
  watch(() => props.config?.value, (newValue) => {
    dateValue.value = newValue || new Date();
    pickerValue.value = newValue || [];
    inputVal.value = newValue || [];
  });
</script>

<style scoped lang="postcss">
.bk-vision-component {
  width: 100%;
  height: 100%;

  .component {
    .lable {
      padding-bottom: 5px;
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: #4d4f56;
    }
  }
}
</style>
