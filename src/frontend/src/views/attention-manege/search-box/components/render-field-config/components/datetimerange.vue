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
    <date-picker
      v-model="localValue"
      class="date-picker"
      :placeholder="`请选择${config.label}`"
      @update:model-value="handleChange" />
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { ref, watch } from 'vue';

  import { DateRange } from '@blueking/date-picker';

  import type { IFieldConfig } from '../config';

  interface Props {
    config: IFieldConfig,
    // eslint-disable-next-line vue/no-unused-properties
    defaultValue?: [string, string],
    name: string,
    model: Record<string, any>
  }
  interface Emits {
    (e: 'change', name: string, value: Props['defaultValue']): void
  }

  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const localValue = ref(props.model.datetime_origin);

  const handleChange = (value: [string|number, string|number]) => {
    // 更新datetime_origin，用于刷新页面正确填充对应格式日期
    emits('change', 'datetime_origin', value.map(item => (typeof item === 'number'
      ? dayjs(item).format('YYYY-MM-DD HH:mm:ss') : item)) as Props['defaultValue']);
  };

  watch(() => props.model.datetime_origin, (date) => {
    localValue.value = date;
  });

  defineExpose<Exposes>({
    getValue() {
      if (props.config.validator && !props.config.validator(localValue.value)) {
        return Promise.reject(`${props.name} error`);
      }
      // 每次点击搜索时获取最新的date数据
      const date = new DateRange(localValue.value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
      emits('change', props.name, [date.startDisplayText, date.endDisplayText]);
      return Promise.resolve({
        [props.name]: localValue.value,
      });
    },
  });
</script>
<style lang="postcss" scoped>
  :deep(.date-picker) {
    display: flex;
    width: 100%;

    .date-content {
      flex: 1;
    }
  }
</style>
