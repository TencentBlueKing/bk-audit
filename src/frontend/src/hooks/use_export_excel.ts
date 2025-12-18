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
import * as XLSX from 'xlsx';

function shortenSheetName(name: string, maxLength = 31) {
  if (name.length <= maxLength) {
    return name;
  }
  return `${name.slice(0, maxLength - 3)}...`;
}

// 导出excel表格数据的sheet页
const exportExcelSheet = (wb: any, json: any, name: string, titleAr: Array<string>, titleKey: Array<string>) =>   {
  const data: any =  [];
  // 处理表头去重
  const uniqueHeaders = Array.from(new Set(titleAr));
  const uniqueTitleKey = Array.from(new Set(titleKey));

  json.forEach((item: any) => {
    const rowData: any = new Array(uniqueTitleKey.length).fill(null);
    uniqueTitleKey.forEach((tIiem, tIndex) => {
      rowData[tIndex] = item[tIiem] === '' ? '--' : item[tIiem];
    });
    data.push(rowData);
  });
  data.splice(0, 0, uniqueHeaders);

  const ws = XLSX.utils.aoa_to_sheet(data);

  XLSX.utils.book_append_sheet(wb, ws, shortenSheetName(name));
};

export default {
  exportExcelSheet,
};
