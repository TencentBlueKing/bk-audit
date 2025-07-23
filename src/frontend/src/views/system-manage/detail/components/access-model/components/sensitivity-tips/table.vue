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
  <div class="sensitivity-tips-table-container">
    <table>
      <thead>
        <tr>
          <th style="width: 15%">
            {{ t('敏感等级') }}
          </th>
          <th style="width: 55%">
            {{ t('实现效果说明') }}
          </th>
          <th style="width: 30%">
            {{ t('举例') }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>
            <span class="sensitivity-level level-1">{{ t('一级(不敏感)') }}</span>
          </td>
          <td>{{ t('可完全开放查看') }}</td>
          <td class="examples">
            {{ t('-') }}
          </td>
        </tr>
        <tr>
          <td>
            <span class="sensitivity-level level-2">{{ t('二级(低)') }}</span>
          </td>
          <td>
            {{
              t('一般指其安全性遭到破坏后不影响国家安全，但可能会对个人权益、公司、业务伙伴或客户、或其他组织的合法权益造成一般危害，或对公共利益造成轻微危害，但不会造成明显影响。')
            }}
          </td>
          <td class="examples">
            {{ t('如硬件信息、系统信息、产品相关的一般运营数据等') }}
          </td>
        </tr>
        <tr>
          <td>
            <span class="sensitivity-level level-3">{{ t('三级(中)') }}</span>
          </td>
          <td>
            {{
              t('一般指其安全性遭到破坏后可能会产生以下影响之一，但不影响国家安全：')
            }}
            <ul class="impact-list">
              <li>（1）{{ t('可能对社会公共利益造成一般危害；') }}</li>
              <li>
                （2）
                {{
                  t('可能对公司、业务伙伴或客户的合法权益造成严重危害，如可能导致本公司遭到监管部门处罚，或者导致部分业务无法正常开展的情况等；')
                }}
              </li>
              <li>（3）{{ t('可能对个人权益造成严重危害。') }}</li>
            </ul>
          </td>
          <td class="examples">
            {{
              t('如用户关联数据（如生日、性别、游戏行为数据）、研发数据、商业市场信息、业务运营流水数据等')
            }}
          </td>
        </tr>
        <tr>
          <td>
            <span class="sensitivity-level level-4">{{ t('四级(高)') }}</span>
          </td>
          <td>
            {{
              t('一般指其安全性遭到破坏后可能会产生以下影响之一，但不影响国家安全：')
            }}
            <ul class="impact-list">
              <li>（1）{{ t('可能对社会公共利益造成严重危害；') }}</li>
              <li>
                （2）
                {{
                  t('可能对公司、业务伙伴或客户的合法权益造成特别严重危害，如可能导致公司遭到监管部门严重处罚，或者导致重要/关键业务无法正常开展等；')
                }}
              </li>
              <li>
                （3）
                {{
                  t('可能导致重大个人信息安全风险，特别严重危害个人权益。')
                }}
              </li>
            </ul>
          </td>
          <td class="examples">
            {{
              t('如用户实名相关数据、产品核心管理数据、财务数据、核心业务源代码等')
            }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();
</script>
<style lang="postcss">
.sensitivity-tips-table-container {
  width: 620px;
  overflow: hidden;
  background: white;
  border: 1px solid #e0e0e0;

  table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }

  th {
    padding: 10px;
    font-weight: 700;
    text-align: left;
    background: #f0f1f5;
    border-right: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
  }

  td {
    padding: 10px;
    line-height: 20px;
    vertical-align: top;
    border-right: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
  }

  tr td:last-child {
    border-right: none;
  }

  tr th:last-child {
    border-right: none;
  }

  tr:last-child td {
    border-bottom: none;
  }

  tr:hover {
    background-color: #f0f8ff;
    transition: background-color .3s ease;
  }
}
</style>
