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
  <div class="form-item-common">
    <div
      v-for="(item, index) in modelValue"
      :key="index"
      class="collector-path-row">
      <bk-input
        :model-value="item"
        :placeholder="t('请输入采集路径')"
        @input="(value: any) => handlePathChange(value as string, index)" />
      <div class="path-actions">
        <div
          v-bk-tooltips="t('添加一个')"
          class="path-btn"
          style="margin-left: 5px;">
          <audit-icon
            type="add-fill"
            @click="handleAddPath(index)" />
        </div>
        <div
          v-if="modelValue.length > 1"
          v-bk-tooltips="t('删除')"
          class="path-btn">
          <audit-icon
            type="reduce-fill"
            @click="handleRemovePath(index)" />
        </div>
      </div>
    </div>
    <div
      ref="footerRef"
      class="collector-path-tips">
      {{ t('日志文件的绝对路径，可使用') }}
      <bk-button
        text
        theme="primary"
        @click="handleWildcardShow">
        {{ t('通配符') }}
      </bk-button>
    </div>
    <teleport to="body">
      <transition>
        <wildcard
          v-if="isShow"
          @change="handleIsShow" />
      </transition>
    </teleport>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import Wildcard from './wild-card.vue';

  interface Props {
    modelValue: Array<string>
  }
  interface Emits {
    (e: 'change', value: Array<string>): void;
    (e: 'update:modelValue', value: Array<string>): void;
  }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const isShow = ref(false);

  const footerRef = ref();

  const handlePathChange = (value: string, index: number) => {
    const paths = [...props.modelValue];
    paths[index] = _.trim(value);

    emits('change', paths);
    emits('update:modelValue', paths);
  };
  const handleAddPath = (index: number) => {
    const paths = [...props.modelValue];
    paths.splice(index + 1, 0, '');
    emits('change', paths);
    emits('update:modelValue', paths);
    setTimeout(() => {
      footerRef.value.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 100);
  };

  const handleRemovePath = (index: number) => {
    const paths = [...props.modelValue];
    paths.splice(index, 1);
    emits('change', paths);
    emits('update:modelValue', paths);
  };

  const handleWildcardShow = () => {
    isShow.value = !isShow.value;
  };
  const handleIsShow = (value: boolean) => {
    isShow.value = value;
  };
</script>
<style lang="postcss" scoped>
.collector-path-row {
  position: relative;

  &:nth-child(n+2) {
    margin-top: 8px;
  }

  .path-actions {
    position: absolute;
    top: 0;
    right: -50px;
    display: flex;
    width: 50px;
  }

  .path-btn {
    display: flex;
    height: 32px;
    padding: 0 5px;
    font-size: 14px;
    color: #c4c6cc;
    cursor: pointer;
    align-items: center;
    justify-content: center;

    &:hover {
      color: #979ba5;
    }
  }
}

.collector-path-tips {
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;
}

/* 进入之前和离开后的样式 */
.v-enter-from,
.v-leave-to {
  opacity: 0%;
  transform: translateX(100px);
}

/* 离开和进入过程中的样式 */
.v-enter-active,
.v-leave-active {
  transition: all .3s ease-out;
}

</style>
