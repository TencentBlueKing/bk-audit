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
  <div class="system-diagnosis-container">
    <div class="main-title">
      系统诊断，向救火式风险修复说拜拜！
      <span class="main-sub-title">
        完成审计数据接入，一键体验系统诊断功能
      </span>
    </div>
    <ul class="diagnostic-list">
      <li style="margin-bottom: 24px;">
        <div class="qa">
          <div class="q">
            一、问：接入审计后不确定接入效果？
          </div>
          <div class="a">
            答：<span class="blue">系统诊断提供审计接入数据质量诊断，多维度诊断系统接入效果。</span>
          </div>
        </div>
        <ol class="item-list">
          <li class="item">
            <div class="item-index">
              <span>1</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">权限中心未纳管操作操作：</span>
              权限中心未纳管操作数 >0 表示该类 action_id 未在权限中心注册，请前往
              <a
                href="https://iam.woa.com/"
                target="_blank">
                https://iam.woa.com/
              </a>
              调整相关系统接入配置；如符合系统设计，无需处理。
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>2</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">权限中心未纳管资源类型操作：</span>
              权限中心未纳管资源类型操作：权限中心未纳管操作数 >0 表示该类 action_id 未在权限中心注册，请前往
              <a
                href="https://iam.woa.com/"
                target="_blank">
                https://iam.woa.com/
              </a>
              调整相关系统接入配置；如符合系统设计，无需处理。
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>3</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">操作上报次数清单操作：</span>
              无上报操作代表本周期内没有该类操作的操作日志上报，请检查相关操作的日志落地上报功能，如为低频次操作，无需处理。
            </div>
          </li>
          <li style="text-indent: 4em;">
            <img
              src="@images/index-1.png"
              style="width: calc(100% - 4em)">
          </li>
        </ol>
      </li>

      <li>
        <div class="qa">
          <div class="qa-q">
            二、问：系统日志分散，缺乏依赖平台数据对账，审计风险响应滞后怎么办？
          </div>
          <div class="qa-a">
            答：<span class="blue">系统诊断自动关联权限中心和用户管理等基础平台，专业安全人员提供安全审计策略，提前诊断自检，拒绝救火式安全风险修复。</span>
          </div>
        </div>
        <ol class="item-list">
          <li class="item">
            <div class="item-index">
              <span>1</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">资源类型上报次数清单操作：</span>
              无上报资源类型代表本周期内没有该类型资源的操作日志上报。请检查相关资源类型的日志落地上报功能，入围低频次操作，无需处理。
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>2</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">越权操作（含系统账号）操作：</span>
              通过操作日志与 IAM 权限数据对账，用户操作成功但权限不在 IAM 的权限记录中会统计为越权操作。可能原因如下：
              <ul>
                <li class="item-info-list-item">
                  实际存在越权操作，请排查操作链路进行安全加固。
                </li>
                <li class="item-info-list-item">
                  操作日志上报错误，用户实际未成功操作，请排查相关问题进行修复。
                </li>
                <li class="item-info-list-item">
                  该用户为系统管理员角色，导致权限未在 IAM 记录，请忽略。
                </li>
                <li class="item-info-list-item">
                  系统账号未在 IAM 记录权限，暂时无需处理。
                </li>
              </ul>
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>3</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">未识别用户操作次数操作：</span>
              未识别用户包括：
              <ul>
                <li class="item-info-list-item">
                  已离职用户，请重点关注该类型操作，检查权限未过期原因。
                </li>
                <li class="item-info-list-item">
                  HR 数据中未记录的太湖账号、游梯账号等，<strong> 请注意避免跨环境透传引发安全风险。</strong>
                </li>
                <li class="item-info-list-item">
                  系统账号，如符合业务场景，请忽略。
                </li>
              </ul>
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>4</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">外包用户操作次数操作：</span>
              外包用户操作次数仅统计，请结合业务使用场景和敏感等级关注该信息。
              <div style="margin-top: 8px;">
                规范参考：互娱应用系统和敏感操作安全管理规范（文本）
                <a
                  href="https://iwiki.woa.com/p/4007716615"
                  target="_blank">
                  https://iwiki.woa.com/p/4007716615
                </a>
              </div>
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>5</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">子公司操作次数操作：</span>
              子公司操作次数仅统计，请结合业务使用场景和敏感等级关注该信息。
              <div style="margin-top: 8px;">
                规范参考：互娱应用系统和敏感操作安全管理规范（文本）
                <a
                  href="https://iwiki.woa.com/p/4007716615"
                  target="_blank">
                  https://iwiki.woa.com/p/4007716615
                </a>
              </div>
            </div>
          </li>
          <li class="item">
            <div class="item-index">
              <span>6</span>
            </div>
            <div class="item-info">
              <span class="item-info-title">正式员工（非外包子公司）操作次数 TOP20 操作：</span>
              正式员工操作次数仅统计，请结合业务使用场景和敏感等级关注该信息。
              <div style="margin-top: 8px;">
                规范参考：互娱应用系统和敏感操作安全管理规范（文本）
                <a
                  href="https://iwiki.woa.com/p/4007716615"
                  target="_blank">
                  https://iwiki.woa.com/p/4007716615
                </a>
              </div>
            </div>
          </li>
          <li style="text-indent: 4em;">
            <img
              src="@images/index-2.png"
              style="width: calc(100% - 4em)">
          </li>
          <li style="text-indent: 4em;">
            <img
              src="@images/index-3.png"
              style="width: calc(100% - 4em)">
          </li>
        </ol>
      </li>
    </ul>
  </div>
</template>
<script setup lang="ts">

</script>
<style scoped lang="postcss">
  .system-diagnosis-container {
    padding: 24px;
    margin-top: 24px;
    background: #fff;

    .main-title {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
      color: #313238;

      .main-sub-title {
        margin-left: 20px;
        font-size: 18px;
        font-weight: normal;
        letter-spacing: 0;
        color: #313238;
      }
    }

    .diagnostic-list {
      margin-top: 40px;

      .qa {
        font-size: 18px;
        font-weight: 700;
        line-height: 26px;

        .qa-a {
          text-indent: 2em;

          .blue {
            color: #3a84ff;
          }
        }
      }

      .item-list {
        margin-top: 12px;
        font-size: 16px;

        .item {
          display: flex;
          margin: 16px 0;
          line-height: 24px;

          .item-index {
            text-indent: 4em;

            span {
              padding: 0 5.2px;
              margin-right: 8px;
              font-size: 14px;
              color: #fff;
              background: #3a84ff;
              border-radius: 50%;
            }
          }

          .item-info-title {
            font-weight: 700;
          }

          .item-info-list-item {
            margin: 8px 0;

            &::before {
              display: inline-block;
              width: 8px;
              height: 8px;
              background-color: #d8d8d8; /* 设置项目符号的颜色 */
              border-radius: 50%;
              content: ''; /* 使用项目符号 */
            }
          }
        }
      }
    }
  }
</style>
