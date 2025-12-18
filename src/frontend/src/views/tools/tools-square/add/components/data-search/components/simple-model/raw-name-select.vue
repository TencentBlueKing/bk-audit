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
    <div class="dialog-content">
      <div class="dialog-content-left">
        <bk-input>
          <template #prefix>
            <audit-icon
              class="search1"
              type="search1" />
          </template>
        </bk-input>
        <div class="list">
          <div class="list-head">
            <div class="list-head-select" />
            <div class="list-head-left">
              {{ t('显示名') }}
            </div>
            <div class="list-head-right">
              {{ t('字段名') }}
            </div>
          </div>
          <div class="list-body">
            <bk-radio-group
              v-model="radioValue"
              class="list-item-select">
              <bk-radio
                v-for="(item, index) in dataList"
                :key="index"
                class="list-item-radio"
                :label="item.name"
                @change="changeRadio(item)" />
            </bk-radio-group>
            <div class="list-item-right">
              <div
                v-for="(item, index) in dataList"
                :key="index"
                class="list-item-text">
                {{ item.value }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="dialog-content-right">
        <div class="right-title">
          {{ t('聚合算法') }}
        </div>
        <bk-radio-group
          v-model="algorithmValue"
          class="algorithm-select">
          <bk-radio
            v-for="(item, index) in algorithmList"
            :key="index"
            class=""
            :label="item.name"
            @change="changeAlgorithmRadio(item)" />
        </bk-radio-group>
      </div>
    </div>
    <div class="dialog-footer">
      <bk-checkbox v-model="isValue">
        {{ t('同时作为查询结果的字段') }}
      </bk-checkbox>
      <div>
        <bk-button
          class="mr8"
          theme="primary"
          type="primary"
          @click="submit">
          {{ t('确定') }}
        </bk-button>
        <bk-button
          type="default"
          @click="cancel">
          {{ t('取消') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  const isValue = ref(false);
  const radioValue = ref();
  const algorithmValue = ref();
  const { t } = useI18n();

  const dataList = ref([
    {
      isRadio: 'username',
      label: false,
      name: '用户名',
      value: 'username',
    }, {
      isRadio: 'username',
      label: false,
      name: 'HAHA',
      value: 'AAA',
    },
    {
      isRadio: 'username',
      label: false,
      name: '用户名',
      value: 'username',
    },
  ]);
  const algorithmList = ref([
    {
      name: '求和',
      value: 'qh',
    },
    {
      name: '平均值4',
      value: 'pj1',
    }, {
      name: '最大值',
      value: 'z1',
    }, {
      name: '最小值',
      value: 'z1',
    }, {
      name: '求和5',
      value: 'qh1',
    }, {
      name: '平均值7',
      value: 'pj1',
    },
  ]);
  const changeRadio = (val: any) => {
    console.log(val);
  };
  const changeAlgorithmRadio = (val: any) => {
    console.log(val);
  };
  const submit = () => {
    console.log('submit');
  };
  const cancel = () => {
    console.log('cancel');
  };
</script>

<style lang="postcss" scoped>
.dialog-content {
  display: flex;
  width: 400px;
  height: 400px;
  margin-top: 0;
  justify-content: space-between;

  .dialog-content-left {
    width: 270px;

    .list-head {
      display: flex;
      height: 40px;
      margin-top: 10px;
      font-size: 12px;
      color: #979ba5;
      background-color: #fafbfd;
      justify-content: space-between;
      align-items: center;

      .list-head-select {
        width: 50px;
        text-align: center;
      }

      .list-head-left {
        width: 150px;
        text-align: left;
      }

      .list-head-right {
        width: 70px;
        margin-right: 10px;
        text-align: right;
      }
    }

    .list-body {
      display: flex;
      height: 300px;
      overflow: auto;

      .list-item-select {
        display: flex;
        width: 250px;
        height: 100%;
        flex-direction: column;

        :deep(.bk-radio.bk-radio) {
          margin-left: 20px;
          font-size: 12px;
          color: #4d4f56;

        }

        :deep(.bk-radio-label) {
          font-size: 12px;
          color: #4d4f56;
        }

        .list-item-radio {
          margin-top: 10px;
          margin-left: 30px;
          font-size: 12px;
          color: #4d4f56;
        }
      }

      .list-item-right {
        display: flex;
        width: 150px;
        height: 100%;
        text-align: left;
        flex-direction: column;

        .list-item-text {
          height: 20px;
          margin-top: 10px;
          margin-right: 5px;
          font-size: 12px;
          color: #979ba5;
          text-align: right;

        }
      }
    }

  }

  .dialog-content-right {
    width: 130px;
    height: 100%;
    overflow: auto;
    background-color: #f5f7fa;

    .right-title {
      margin-top: 10px;
      margin-left: 20px;
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      letter-spacing: 0;
      color: #313238;
    }

    .algorithm-select {
      display: flex;
      flex-direction: column;

      .algorithm-radio {
        margin-top: 10px;
        margin-left: 30px;
        font-size: 12px;
        color: #4d4f56;
      }

      :deep(.bk-radio.bk-radio) {
        margin-top: 20px;
        margin-left: 20px;
        font-size: 12px;
        color: #4d4f56;

      }

      :deep(.bk-radio-label) {
        font-size: 12px;
        color: #4d4f56;
      }
    }
  }

}

.dialog-footer {
  display: flex;
  width: 100%;
  height: 42px;
  padding: 0 20px;
  margin-top: 10px;
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
  background: #fafbfd;
  box-shadow: inset 0 1px 0 0 #0000001f;
  align-items: center;
  justify-content: space-between;

}

.search1 {
  margin-top: 5px;
  font-size: 20px;
  color: #979ba5;
}
</style>
