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
    <bk-date-picker
      append-to-body
      :clearable="false"
      :disable-date="disableDate"
      :model-value="defaultValue"
      :placeholder="`请选择${config.label}`"
      shortcut-close
      :shortcuts="shortcuts"
      style="width: 100%;"
      type="datetimerange"
      @change="handleChange" />
  </div>
</template>
<script setup lang="ts">
  // import dayjs from 'dayjs';
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '../config';

  interface Props {
    config: IFieldConfig,
    defaultValue?: [string, string],
    name: string,
  }
  interface Emits {
    (e: 'change', name: string, value: Props['defaultValue']): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  interface TShortcut {
    text: string,
    value: () => [Date, Date]
  }

  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }
  const { t } = useI18n();
  const shortcuts: Array<TShortcut> = [
    {
      text: t('近 1 小时'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 1 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 86400000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 3 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 259200000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 7 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 604800000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 30 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 2592000000);
        return [
          start, end,
        ];
      },
    },
  ];

  const disableDate = (date: number | Date): boolean => date.valueOf() > Date.now();

  const handleChange = (value: Props['defaultValue']) => {
    emits('change', props.name, value);
  };
  defineExpose<Exposes>({
    getValue() {
      if (props.config.validator && !props.config.validator(props.defaultValue)) {
        return Promise.reject(`${props.name} error`);
      }
      return Promise.resolve({
        [props.name]: props.defaultValue,
      });
    },
  });
</script>
<style lang="postcss" scoped>
  .dateranttime-custom-shortcuts {
    line-height: 32px;
    color: rgb(99 101 110);

    .shortcuts-item {
      padding: 0 16px;
      cursor: pointer;

      &:hover {
        color: rgb(58 132 255);
        background-color: rgb(225 236 255);
      }
    }
  }
</style>
