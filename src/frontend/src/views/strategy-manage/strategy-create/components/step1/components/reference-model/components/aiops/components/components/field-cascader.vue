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
  <div
    ref="rootRef"
    class="select-field-value"
    :class="{
      'is-errored': isError,
      'is-background-errored-tip': theme === 'background'
    }">
    <div
      class="cascader-wrap"
      style="position: relative; ">
      <span
        v-if="(isEditMode || isCloneMode) && !isChange"
        style="position: absolute; top: -4px; left: 10px; z-index: 10; pointer-events: none;">
        {{ localValueMap }}
      </span>
      <bk-cascader
        class="strategy-create-aiops-cascader-item"
        float-mode
        id-key="value"
        is-remote
        :list="rtFields"
        :model-value="localValue"
        name-key="label"
        :remote-method="remoteMethod"
        @change="onChange"
        @update:model-value="onUpdateModelValue" />
      <span
        v-if="isError"
        v-bk-tooltips="{ content: errorTip, placement: 'top' }"
        class="err-tip">
        <audit-icon type="alert" />
      </span>
    </div>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  interface Props {
    rtFields: Array<{
      label: string;
      value: string;
    }>;
    defaultValue: string[];
    systemId: string;
    fieldItem: Record<string, any>;
    selectActionIdMap: Record<string, number>; // 已经选中的actionid列表
    actionId: string;// 自动适配的actionid
    theme?: 'background' | ''
  }

  interface Emits {
    (e: 'change', val: string[]): void
    (e: 'changeActionId', val: string): void
  }

  interface Expose {
    getValue: () => void,
    clearValue: () => void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const isChange = ref(false);
  let isInit = false;
  const { t } = useI18n();
  const route = useRoute();
  const isError = ref(false);
  const localValue = ref<string[]>([]);
  const errorTip = ref('');
  const localValueMap = computed(() => {
    if (!(isEditMode || isCloneMode) || isChange.value) return '';
    const val1 = props.rtFields
      .find(item => item.value === localValue.value[0])?.label || localValue.value[0];
    const val2 = fieldsData.value
      .find(item => item.field_name === localValue.value[1])?.description || localValue.value[1];
    return `${val1}/${val2}`;
  });
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyEdit';
  // 获取参数值
  const {
    run: fetchStrategyFields,
    data: fieldsData,
  } = useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
  });

  const remoteMethod = ({ id }: { id: string }, resolve: any) => {
    fetchStrategyFields({
      action_id: id,
      system_id: props.systemId,
    }).then((data) => {
      const res = data.map(item => ({
        label: item.description,
        value: item.field_name,
        leaf: true,
      }));
      resolve(res);
    });
  };

  const onUpdateModelValue = (val: string[]) => {
    if (val[0] !== props.actionId && localValue.value[0] && !localValue.value[1]) {
      InfoBox({
        title: t('确认修改？'),
        subTitle: t('多个参数的映射值都需要选择拓展字段，则需保持所选操作一致，此处选择其他操作会同步修改其他参数已经映射的操作。请确认是否选择其他操作'),
        cancelText: t('取消'),
        confirmText: t('确定'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          localValue.value = val;
        },
      });
    } else {
      localValue.value = val;
    }
  };

  const onChange = (val: string[]) => {
    emits('change', val);
    if (!val.length) {
      emits('changeActionId', '');
    } else if (localValue.value[0]) {
      emits('changeActionId', localValue.value[0]);
    }
    isChange.value = true;
  };
  const JudgeIsActionIdDuplicated = () => {
    const { selectActionIdMap } = props;
    if (localValue.value[0]) {
      const actionId = localValue.value[0] as keyof typeof selectActionIdMap;
      if (selectActionIdMap[actionId] && selectActionIdMap[actionId] > 1) {
        isError.value = true;
        errorTip.value = t('同组操作ID不可以重复');
        return;
      }
    }
    isError.value = false;
  };
  watch(() => props.selectActionIdMap, () => {
    JudgeIsActionIdDuplicated();
  }, {
    deep: true,
    immediate: true,
  });
  watch(() => props.defaultValue, (value) => {
    if (!isInit) {
      localValue.value = value;
      if (value && value.length) {
        fetchStrategyFields({
          action_id: value[0],
          system_id: props.systemId,
        });
      }
      isInit = true;
    }
  }, {
    deep: true,
    immediate: true,
  });
  watch(() => props.actionId, (id) => {
    if (!isInit || id === undefined) return;
    if (id) {
      if (!localValue.value[0] || localValue.value[0] !== id) {
        localValue.value = [id];
        JudgeIsActionIdDuplicated();
      }
    } else {
      localValue.value = [];
    }
  }, {
    immediate: true,
  });

  defineExpose<Expose>({
    getValue() {
      if (isError.value) {
        return Promise.reject(new Error('同组操作ID不可以重复'));
      }

      const required = props.fieldItem.properties?.is_required;
      if (required && (!localValue.value.length)) {
        isError.value = true;
        errorTip.value = t('必填项');
        return Promise.reject(new Error('必填'));
      }
      if (localValue.value.length && localValue.value.length < 2) {
        isError.value = true;
        errorTip.value = t('必须选择第二级');
        return Promise.reject(new Error('必须选择第二级'));
      }
      isError.value = false;
      return Promise.resolve({
        field_name: props.fieldItem.field_name,
        source_field: localValue.value,
      });
    },
    clearValue() {
      localValue.value = [];
    },
  });
</script>
<style lang="postcss">
.select-field-value {
  position: relative;
  height: 100%;

  .err-tip {
    position: absolute;
    top: 27%;
    right: 30px;
    font-size: 16px;
    line-height: 1;
    color: #ea3636;
  }

  .bk-cascader-wrapper.float-mode {
    height: 42px;
  }

  .bk-cascader {
    width: 100%;
    height: 100%;
    background-color: #fff;
    border: 1px solid #fff;

    .bk-cascader-name {
      height: 42px;
      line-height: 33px;
    }
  }
}

.strategy-create-aiops-cascader-item {
  .bk-input,
  .bk-input:hover {
    height: 42px;
    border-color: white;
  }

  .bk-input.is-focused {
    border-color: #3a84ff;
  }

  .bk-input--large {
    font-size: 12px;
  }

  .bk-cascader.is-hover:not(.is-disabled) {
    border: 1px solid #fff;
  }
}

.is-errored .bk-cascader {
  border-color: #ea3636 !important;
}

.is-errored .cascader-wrap {
  height: 41px;
  padding-top: 4px;
  background-color: #fee;
}

.is-errored.is-background-errored-tip .bk-cascader {
  background-color: #fee !important;
  border-color: #fee !important;

}

</style>
