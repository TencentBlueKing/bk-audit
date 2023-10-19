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
  <div class="strategy-upgrade-card">
    <p class="title">
      {{ title }}
    </p>
    <div class="table-content">
      <div
        v-for="item in column"
        :key="item.label"
        class="table-tr"
        :class="{
          'disabled': item.disabled,
          'highlight': item.highlight,
        }">
        <div class="tr-title ">
          <img
            v-if="item.type"
            class="field-type-icon"
            :src="item.highlight
              ? `/images/field-type/y-${item.type}.png`
              : `/images/field-type/${item.type}.png`">
          <tool-tip
            class="content"
            :data="item.label" />
        </div>
        <p class="tr-content">
          {{ item.value || '--' }}
        </p>
      </div>
    </div>
    <div
      v-if="inputFieldsMap && inputFieldsMap.length"
      class="fields-map">
      <p class="mb8">
        {{ t('输入字段映射') }}
      </p>
      <template
        v-for="(mapItem,index) in inputFieldsMap"
        :key="index">
        <p
          v-if="mapItem.title"
          class="title">
          {{ mapItem.title }}
        </p>
        <div class="table-content">
          <div
            v-for="item in mapItem.column"
            :key="item.label"
            class="table-tr "
            :class="{
              'disabled':item.disabled,
              'new': item.new,
            }">
            <div class="tr-title">
              <img
                v-if="item.type"
                class="field-type-icon"
                :src="item.disabled || item.new
                  ? `/images/field-type/y-${item.type}.png`
                  : `/images/field-type/${item.type}.png`">
              <tool-tip
                class="content"
                :data="item.label" />
            </div>
            <p class="tr-content">
              <span v-if="item.new">
                {{ t('待补充') }}
              </span>
              <span v-else>
                {{ item.value || '--' }}
              </span>
              <audit-icon
                v-if="item.new"
                class="new-tip"
                type="new" />
            </p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  import ToolTip from '@components/show-tooltips-text/index.vue';

  import type { ColumnType } from '../index.vue';

  interface Props {
    title: string,
    column: ColumnType[],
    inputFieldsMap?: Array<{
      title?: string,
      column:  ColumnType[]
    }>
  }
  defineProps<Props>();
  const { t } = useI18n();
</script>
<style scoped lang="postcss">
.strategy-upgrade-card {
  width: 491px;
  padding: 12px 16px;
  background: #FFF;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 #1919290d;

  .field-type-icon {
    width: 46px;
    margin-right: 6px;
  }

  .fields-map{
    margin-top: 15px;
    font-size: 12px;
    color: #313238;

    .title{
      /* width: 459px; */
      height: 32px;
      padding-left: 8px;
      margin-top: 12px;
      font-size: 12px;
      line-height: 32px;
      color: #313238;
      background: #F0F1F5;
    }
  }

  >.title {
    margin-bottom: 14px;
    font-size: 14px;
    color: #313238;
  }

  .table-content{
    .table-tr:last-child{
      border-bottom: 1px solid #F0F1F5;
    }

    .table-tr.disabled{
      color: #FF9C01;

      .tr-title{
        color: #FF9C01;

        .field-type-icon {
          width: 46px;
          margin-right: 6px;
        }

        .content{
          text-decoration: line-through;
        }
      }

      .tr-content{
        color: #FF9C01;
        text-decoration: line-through;
      }
    }

    .table-tr.new{
      color: #FF9C01;

      .tr-title{
        color: #FF9C01;

        .field-type-icon {
          width: 46px;
          margin-right: 6px;
        }
      }

      .tr-content{
        position: relative;
        width: 100%;
        color: #FF9C01;
      }

      .new-tip{
        position: absolute;
        top: 32%;
        right: 10px;
      }
    }

    .table-tr.highlight{
      .tr-title{
        color: #FF9C01;
      }

      .tr-content{
        color: #FF9C01;
      }
    }

    .table-tr{
      display: flex;
      align-items: center;
      height: 32px;
      border-top: 1px solid #F0F1F5;

      >.tr-title{
        display: flex;
        height: 31px;
        max-width: 200px;
        min-width: 200px;
        padding: 0 8px;
        color:#979BA5;
        background: #FAFBFD;
        border-right: 1px solid #F0F1F5;
        align-items: center;

        .tr-type{
          display: inline-block;
          width: 46px;
          height: 23px;
          margin-right: 8px;
          font-size: 10px;
          font-weight: 400;
          line-height: 23px;
          color: #3A84FF;
          text-align: center;
          background: #E1ECFF;
          border-radius: 10px;
        }
      }

      >.tr-content{
        padding: 5px 8px;
        color: #63656e;
      }
    }
  }
}
</style>
