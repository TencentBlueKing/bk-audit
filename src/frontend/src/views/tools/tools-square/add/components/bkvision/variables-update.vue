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
  <bk-sideslider
    v-model:isShow="isShow"
    :esc-close="false"
    :quick-close="false"
    :show-mask="false"
    :title="t('更新变量')"
    width="30%">
    <div class="head-tip">
      <audit-icon
        class="info-fill"
        type="info-fill" />
      <span
        class="tip-title title-add">{{ t('新增') }}：<span class="add">{{ addArrays.length }}</span> </span>
      <span
        class="tip-title">{{ t('更新') }}：<span class="update">{{ updateArrays.length }}</span></span>
      <span
        class="tip-title">{{ t('删除') }}： <span class="del">{{ delArrays.length }}</span> </span>
    </div>

    <div class="table">
      <bk-table
        ref="refTable"
        :border="['outer','col','row']"
        :columns="columns"
        :data="updateVariables"
        height="auto"
        max-height="100%"
        show-overflow-tooltip
        stripe />
    </div>
    <div class="footer">
      <bk-button
        class="primary"
        theme="primary"
        @click="handleSubmit">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        class="close"
        @click="isShow = false">
        {{ t('取消') }}
      </bk-button>
    </div>
  </bk-sideslider>
</template>

<script setup lang="tsx">
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';


  type InputVariable = Array<{
    raw_name: string;
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    default_value: string | Array<string>;
    old_default_value?: string | Array<string>;
    type?: string;
    choices: Array<{
      key: string,
      name: string
    }>;
    is_default_value?: boolean;
  }>

  interface Exposes {
    show: (tool: InputVariable, bkv: InputVariable, oldCom: InputVariable, newCom: InputVariable) => void;
  }
  interface Emits  {
    (event: 'changeSubmit', value: any): void;
  }

  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const isShow = ref(false);

  const oldVariable = ref<InputVariable>([]);
  const newVariable = ref<InputVariable>([]);
  const addArrays = ref<InputVariable>([]);
  const delArrays = ref<InputVariable>([]);
  const updateArrays = ref<InputVariable>([]);
  const updateVariables = ref<InputVariable>([]);
  const columns = [
    {
      label: t('更新类型'),
      field: 'type',
      width: '90px',
      render: ({ data }: { data: any }) => {
        // eslint-disable-next-line no-nested-ternary
        const typeLabel = data.type === 'add' ? t('新增') : data.type === 'update' ? t('更新') : t('删除');
        // eslint-disable-next-line no-nested-ternary
        const theme = data.type === 'add' ? 'success' : data.type === 'update' ? 'warning' : 'danger';
        return (
          <div>
            <bk-tag type="filled" theme={theme}>
              {typeLabel}
            </bk-tag>
          </div>
        );
      },
    },
    {
      label: t('参数名'),
      field: 'raw_name',
      render: ({ data }: { data: any }) => <div>{data.raw_name}</div>,
    },
    {
      label: t('默认值'),
      field: 'default_value',
      render: ({ data }: { data: any }) => <div>{columnText(data)}</div>,
    },
    {
      label: t('参数类型'),
      field: '',
      width: '120px',
      render: ({ data }: { data: any }) => <div>
             <bk-tag
     type="stroke"
     theme={data.field_category === 'variable' ? '' : 'info'}>
      {data.field_category === 'variable' ? '变量' : '交互组件'}
      </bk-tag>
        </div>,
    },
  ];

  const columnText = (data: any) => (data.type === 'update' ?  (`${data.old_default_value}->${data.default_value}`)  : '--') ;
  const handleSubmit = () => {
    const updataList = {
      addArrays: addArrays.value,
      delArrays: delArrays.value,
      updateArrays: updateArrays.value,
    };
    isShow.value = false;
    emits('changeSubmit', updataList);
  };

  defineExpose<Exposes>({
    show(tool: InputVariable, variables: InputVariable, comList: InputVariable, bkVisionComList: InputVariable) {
      nextTick(() => {
        isShow.value = true;
        // eslint-disable-next-line no-param-reassign
        oldVariable.value = tool.concat(comList);
        // eslint-disable-next-line no-param-reassign
        newVariable.value = variables.concat(bkVisionComList);
        // 对比旧数组 oldVariable 与新数组 newVariable
        const compareVariables = (oldVars: InputVariable, newVars: InputVariable) => {
          const addAry: InputVariable = [];
          const delAry: InputVariable = [];
          const updateAry: InputVariable = [];

          // 检查新增和修改的项
          newVars.forEach((newVar) => {
            const oldVar = oldVars.find(item => item.raw_name === newVar.raw_name);
            if (!oldVar) {
              // 新增
              addAry.push({
                ...newVar,
                type: 'add',
              });
            } else if (JSON.stringify(oldVar) !== JSON.stringify(newVar)) {
              // 修改 不使用默认值时不处理
              if (oldVar.default_value && !deepEqual(oldVar, newVar)) {
                updateAry.push({
                  ...newVar,
                  type: 'update',
                  old_default_value: oldVar.default_value,
                });
              }
            }
          });

          // 检查删除的项
          oldVars.forEach((oldVar) => {
            if (!newVars.find(item => item.raw_name === oldVar.raw_name)) {
              delAry.push({
                ...oldVar,
                type: 'delete',
              });
            }
          });

          return { addAry, delAry, updateAry };
        };
        const { addAry, delAry, updateAry } = compareVariables(oldVariable.value, newVariable.value);
        addArrays.value = addAry;
        delArrays.value = delAry;
        updateArrays.value = updateAry;
        updateVariables.value = addAry.concat(updateAry).concat(delAry);
      });
    },
  });

  // 深比较两个对象
  const deepEqual = (obj1: any, obj2: any) => {
    // 如果两个对象是同一个引用，直接返回 true
    if (obj1 === obj2) return true;
    // 如果其中一个为 null 或 undefined，另一个必须也是 null 或 undefined
    if (obj1 === null || obj2 === null) return obj1 === obj2;
    // 检查类型是否一致
    if (typeof obj1 !== 'object' || typeof obj2 !== 'object') return obj1 === obj2;
    // 获取对象的键名数组
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);
    // 如果键的数量不一致，直接返回 false
    if (keys1.length !== keys2.length) return false;
    // 遍历每个键，递归比较值
    for (const key of keys1) {
      if (!keys2.includes(key)) return false;
      if (!deepEqual(obj1[key], obj2[key])) return false;
    }
    return true;
  };
</script>

<style lang="postcss" scoped>
.head-tip {
  width: 96%;
  height: 32px;
  margin-top: 10px;
  margin-left: 2%;
  line-height: 32px;
  background: #f0f5ff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;

  .info-fill {
    margin-left: 5px;
    font-size: 14px;
    color: #3a84ff;
  }

  .tip-title {
    margin-left: 5px;
    font-size: 12px;

    .add {
      color: #2caf5e;
    }

    .del {
      color: #e02020;
    }

    .update {
      color: #f59500;
    }
  }

  .title-add {
    margin-left: 10px;
    font-size: 12px;
  }

}

.table {
  width: 96%;
  height: auto;
  max-height: 85vh;
  margin-top: 10px;
  margin-left: 2%;
  overflow: auto;
}

.footer {
  position: fixed;
  bottom: 20px;
  width: 100%;
  height: 48px;
  background: #fafbfd;
  box-shadow: 0 -1px 0 0 #dcdee5;

  .primary {
    height: 32px;
    padding-right: 20px;
    padding-left: 20px;
    margin-top: 20px;
    margin-left: 20px;
  }

  .close {
    height: 32px;
    padding-right: 20px;
    padding-left: 20px;
    margin-top: 20px;
    margin-left: 20px;
  }
}
</style>
