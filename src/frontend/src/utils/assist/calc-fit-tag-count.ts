/*
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
*/

interface CalcFitTagCountOptions {
  /** 标签总数；只测量了前若干个标签时传入，用于判断是否需要预留 +n */
  total?: number;
  gap?: number;
  /** +n 标签宽度；传函数时按剩余数量计算 */
  overflowWidth?: number | ((rest: number) => number);
}

/**
 * 按标签实际宽度计算单行能完整展示几个，放不下的预留 +n 位置；至少返回 1
 */
export const calcFitTagCount = (
  tagWidths: number[],
  available: number,
  options: CalcFitTagCountOptions = {},
) => {
  const { total = tagWidths.length, gap = 4, overflowWidth = 0 } = options;
  let used = 0;
  let fit = 1;
  for (let i = 0; i < tagWidths.length; i++) {
    used += (i ? gap : 0) + tagWidths[i];
    if (used > available) break;
    const rest = total - (i + 1);
    const extra = rest > 0
      ? gap + (typeof overflowWidth === 'function' ? overflowWidth(rest) : overflowWidth)
      : 0;
    if (used + extra <= available) fit = i + 1;
  }
  return fit;
};
