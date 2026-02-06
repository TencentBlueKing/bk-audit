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
    <bk-button
      class="storage-manage-info-toggle"
      text
      theme="primary"
      @click="handleShowForm">
      <span>{{ t('ES 集群管理') }}</span>
      <audit-icon
        v-if="isShowForm"
        type="angle-double-up" />
      <audit-icon
        v-else
        type="angle-double-down" />
    </bk-button>
    <audit-form
      v-if="isShowForm"
      ref="formRef"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <div class="form-item-row">
        <bk-form-item
          class="form-item-col"
          :label="t('过期时间')"
          property="setup_config.retention_days_default"
          required>
          <!-- <template #labelAppend>
            <span style="font-size: 12px; color: #979ba5;">（默认&lt;= 最大）</span>
          </template> -->
          <div class="form-item-row">
            <bk-input
              v-model="formData.setup_config.retention_days_default"
              class="form-item-col"
              :placeholder="t('输入过期时间天数')"
              :suffix="t('天')"
              type="number" />
            <!-- <BkInput
              v-model="formData.setup_config.retention_days_max"
              class="form-item-col"
              placeholder="输入过期时间最大天数"
              prefix="最大"
              suffix="天"
              type="number" /> -->
          </div>
        </bk-form-item>
        <bk-form-item
          class="form-item-col"
          :label="t('副本数')"
          property="setup_config.number_of_replicas_default"
          required>
          <!-- <template #labelAppend>
            <span style="font-size: 12px; color: #979ba5;">（默认&lt;= 最大）</span>
          </template> -->
          <div class="form-item-row">
            <bk-input
              v-model="formData.setup_config.number_of_replicas_default"
              class="form-item-col"
              type="number" />
            <!-- <BkInput
              v-model="formData.setup_config.number_of_replicas_max"
              class="form-item-col"
              prefix="最大"
              type="number" /> -->
          </div>
        </bk-form-item>
      </div>
      <bk-form-item :label="t('冷热分离')">
        <bk-switcher
          v-model="formData.enable_hot_warm"
          :disabled="nodeAttrList.length <=1 ? true : false"
          theme="primary" />
        <span
          v-if="nodeAttrList.length <=1"
          class="notice-info">{{ t('当前存储的标签数') }}&lt;=1,{{ t('无法开启') }}</span>
      </bk-form-item>
      <div
        v-if="formData.enable_hot_warm"
        class="form-item-row">
        <bk-form-item
          class="form-item-col"
          :label="t('热数据标签')"
          property="hot_attr_value"
          required>
          <template #label>
            <span>{{ t('热数据标签') }}</span>
            <node-attr-detail
              v-if="hotAttr"
              :data="hotAttrRelateList" />
          </template>
          <bk-loading :loading="isNodeAttrLoading">
            <bk-select v-model="hotAttr">
              <bk-option
                v-for="item in nodeAttrList"
                :key="item.key"
                :label="`${item.attr}:${item.value}(${item.num})`"
                :value="item.key" />
            </bk-select>
          </bk-loading>
        </bk-form-item>
        <bk-form-item
          class="form-item-col"
          :label="t('冷数据标签')"
          property="warm_attr_value"
          required>
          <template #label>
            <span>{{ t('冷数据标签') }}</span>
            <node-attr-detail
              v-if="warmAttr"
              :data="warmAttrRealteList" />
          </template>
          <bk-loading :loading="isNodeAttrLoading">
            <bk-select v-model="warmAttr">
              <bk-option
                v-for="item in nodeAttrList"
                :key="item.key"
                :label="`${item.attr}:${item.value}(${item.num})`"
                :value="item.key" />
            </bk-select>
          </bk-loading>
        </bk-form-item>
      </div>
      <bk-form-item
        v-if="formData.enable_hot_warm"
        class="form-item-col"
        :label="t('数据降冷时间')"
        property="allocation_min_days"
        required>
        <bk-input
          v-model="formData.allocation_min_days"
          class="form-item-col"
          :placeholder="t('输入数据降冷时间天数')"
          :suffix="t('天')"
          type="number" />
      </bk-form-item>
      <bk-form-item
        :label="t('集群负责人')"
        property="admin"
        required>
        <audit-user-selector-tenant v-model="formData.admin" />
      </bk-form-item>
      <bk-form-item
        :label="t('集群说明')"
        property="description"
        required>
        <bk-input
          v-model="formData.description"
          :maxlength="255"
          :placeholder="t('请输入集群说明')"
          type="textarea" />
      </bk-form-item>
    </audit-form>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import NodeAttrDetail from '../../node-attr-detail/index.vue';
  import useNodeAttr, {
    genNodeAttrKey,
    parseNodeAttrKey,
  } from '../hooks/use-node-attr';
  import useNodeAttrRealteList from '../hooks/use-node-attr-related-list';

  interface Props {
    modelValue: {
      enable_hot_warm: boolean,
      hot_attr_name: string,
      hot_attr_value: string,
      warm_attr_name: string,
      warm_attr_value: string,
      setup_config: {
        retention_days_default: number,
        number_of_replicas_default: number,
      },
      allocation_min_days: number,
      admin: Array<string>,
      description: string,
    },
    baseInfo: {
      [key: string]: any
    }
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const rules = {
    hot_attr_value: [
      {
        validator: () => formData.value.enable_hot_warm && hotAttr.value !== '',
        message: t('热数据标签不能为空'),
      },
    ],
    warm_attr_value: [
      {
        validator: () => formData.value.enable_hot_warm && warmAttr.value !== '',
        message: t('冷数据标签不能为空'),
      },
    ],
    'setup_config.retention_days_default': [
      {
        validator: () => formData.value.setup_config.retention_days_default > 0,
        message: t('过期时间需 > 0'),
      },
    ],
    'setup_config.number_of_replicas_default': [
      {
        validator: () => formData.value.setup_config.number_of_replicas_default > 0,
        message: t('副本数需 > 0'),
      },
    ],
    allocation_min_days: [
      {
        validator: () => formData.value.allocation_min_days >= 0
          && formData.value.allocation_min_days <= formData.value.setup_config.retention_days_default,
        message: t('数据降冷时间需 >= 0 且不能大于过期时间'),
      },
    ],
    admin: [
      {
        validator: () => formData.value.admin.length > 0,
        message: t('集群负责人不能为空'),
      },
    ],
    description: [
      {
        validator: () => formData.value.description !== '',
        message: t('集群说明不能为空'),
      },
    ],
  };

  const formRef = ref();

  // 热数据
  const hotAttr = ref('');
  // 冷数据
  const warmAttr = ref('');

  const isShowForm = ref(true);

  const formData = ref({} as Props['modelValue']);

  const {
    loading: isNodeAttrLoading,
    nodeAttrList,
    fetchNodeAttrList,
  } = useNodeAttr();


  const hotAttrRelateList = useNodeAttrRealteList(nodeAttrList, hotAttr);
  const warmAttrRealteList = useNodeAttrRealteList(nodeAttrList, warmAttr);

  watch(() => props.modelValue, (modelValue) => {
    formData.value = _.cloneDeep(modelValue);
    // fix: hot_attr_value, warm_attr_name 通过其它字段验证，初始时给个默认值
    formData.value.hot_attr_value = ' ';
    formData.value.warm_attr_value = ' ';
    // 热数据处理
    hotAttr.value = genNodeAttrKey({
      attr: modelValue.hot_attr_name,
      value: modelValue.hot_attr_value,
    });
    // 冷数据处理
    warmAttr.value = genNodeAttrKey({
      attr: modelValue.warm_attr_name,
      value: modelValue.warm_attr_value,
    });
  }, {
    immediate: true,
  });

  const handleShowForm = () => {
    isShowForm.value = !isShowForm.value;
  };


  onMounted(() => {
    fetchNodeAttrList({
      ...props.baseInfo,
    });
  });


  defineExpose({
    getData():Promise<Props['modelValue']> {
      return formRef.value.validate()
        .then(() => {
          const {
            enable_hot_warm,
            setup_config,
            admin,
            description,
            allocation_min_days,
          } = formData.value;

          const {
            name: hotAttrName,
            value: hotAttrValue,
          } = parseNodeAttrKey(hotAttr.value);
          const {
            name: warmAttrName,
            value: warmAttrValue,
          } = parseNodeAttrKey(warmAttr.value);

          return {
            enable_hot_warm,
            hot_attr_name: hotAttrName,
            hot_attr_value: hotAttrValue,
            warm_attr_name: warmAttrName,
            warm_attr_value: warmAttrValue,
            setup_config,
            admin,
            description,
            allocation_min_days,
          };
        });
    },
  });
</script>
<style lang="postcss">
  .storage-manage-info-toggle {
    margin-top: 20px;
    margin-bottom: 24px;
  }

  .notice-info {
    margin-left: 10px;
    font-size: 12px;
    font-weight: 500;
    font-weight: normal;
    color: #979ba5;
  }
</style>
