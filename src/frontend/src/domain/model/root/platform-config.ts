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

export default class PlatformConfig {
  version: string;
  bkAppCode: string;
  name: string;
  nameEn: string;
  appLogo: string;
  helperText: string;
  helperTextEn: string;
  helperLink: string;
  brandImg: string;
  brandImgEn: string;
  brandName: string;
  favIcon: string;
  brandNameEn: string;
  footerInfo: string;
  footerInfoEn: string;
  footerCopyright: string;
  footerInfoHTML: string;
  footerInfoHTMLEn: string;
  footerCopyrightContent: string;
  i18n: {
    name: string;
    helperText: string;
    brandImg: string;
    brandName: string;
    footerInfoHTML: string;
    productName: string;
  };

  constructor(payload = {} as PlatformConfig) {
    this.version = payload.version;
    this.bkAppCode = payload.bkAppCode;
    this.helperText = payload.helperText;
    this.helperTextEn = payload.helperTextEn;
    this.helperLink = payload.helperLink;
    this.brandImg = payload.brandImg;
    this.brandImgEn = payload.brandImgEn;
    this.footerInfo = payload.footerInfo;
    this.footerInfoEn = payload.footerInfoEn;
    this.footerCopyright = payload.footerCopyright;
    this.footerInfoHTML = payload.footerInfoHTML;
    this.footerInfoHTMLEn = payload.footerInfoHTMLEn;
    this.appLogo = payload.appLogo;
    this.name = payload.name;
    this.nameEn = payload.name;
    this.brandName = payload.name;
    this.brandNameEn = payload.name;
    this.footerCopyrightContent = payload.footerCopyrightContent;
    this.favIcon = payload.favIcon;
    this.i18n = payload.i18n;
  }
}
