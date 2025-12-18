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
    <bk-input
      :model-value="defaultValue"
      :placeholder="t(`请输入${config.label}`)"
      style="height: 74px;"
      type="textarea"
      @input="(value: any) => handleChange(value as string)" />
    <template v-if="isMounted && teleportParentNode">
      <teleport :to="`#${name}ItemLabelAppend`">
        <bk-popover
          placement="bottom-start"
          theme="light"
          trigger="click">
          <audit-icon
            style="color: #c4c6cc; cursor: pointer;"
            type="help-fill" />
          <template #content>
            <div class="query-string-description">
              <p>
                <span>{{ t('可输入SQL语句进行快速查询') }}</span>
                <a
                  :href="configData.help_info.query_string"
                  target="_blank">
                  <audit-icon type="jump-link" />
                  {{ t('查看语法') }}
                </a>
              </p>
              <h1>{{ t('精确匹配(支持AND、OR)') }}：</h1>
              <p>author:"John Smith" AND age:20</p>
              <h1>{{ t('字段名匹配(*代表通配符)') }}：</h1>
              <p>status:active</p>
              <p>title:(quick brown)</p>
              <h1>{{ t('字段名模糊匹配') }}：</h1>
              <p>vers\*on:(quick brown)</p>
              <h1>{{ t('通配符匹配') }}：</h1>
              <p>qu?ck bro*</p>
              <h1>{{ t('正则匹配') }}：</h1>
              <p>name:/joh?n(ath[oa]n/</p>
              <h1>{{ t('范围匹配') }}：</h1>
              <p>count:[1 TO 5]</p>
              <p>count:[1 TO 5}</p>
              <p>count:[10 TO *]</p>
            </div>
          </template>
        </bk-popover>
      </teleport>
    </template>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: true,
  };
</script>
<script setup lang="ts">
  import {
    computed,
    onMounted,
    ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import type { IFieldConfig } from '../config';

  interface Props {
    config: IFieldConfig,
    defaultValue?: string,
    name: string,
  }

  interface Emits {
    (e: 'change', name: string, value: string): void
  }

  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const isMounted = ref(false);
  const teleportParentNode = computed(() => document.querySelector(`#${props.name}ItemLabelAppend`));
  const handleChange = (value: string) => {
    emits('change', props.name, value);
  };

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  onMounted(() => {
    setTimeout(() => {
      isMounted.value = true;
    });
  });
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
<style lang="postcss">
  .query-string-description {
    max-width: 264px;
    font-size: 12px;
    line-height: 18px;
    color: rgb(99 101 110);
    word-break: keep-all;

    h1 {
      margin: 10px 0 4px;
      font-size: 12px;
      font-weight: 600;
    }
  }
</style>
