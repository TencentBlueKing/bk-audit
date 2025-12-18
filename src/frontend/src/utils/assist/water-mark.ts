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
const setWatermark = (imgUrl: string) => {
  const id = '1.23452384164.123412416';

  if (document.getElementById(id) !== null) {
    document.body.removeChild(document.getElementById(id) as Node);
  }
  const div = document.createElement('div');
  div.id = id;
  div.style.pointerEvents = 'none';
  div.style.top = '50px';
  div.style.left = '50px';
  div.style.position = 'fixed';
  div.style.zIndex = '10000';
  div.style.width = `${document.documentElement.clientWidth}px`;
  div.style.height = `${document.documentElement.clientHeight}px`;
  div.style.background = `url(data:image/png;base64,${imgUrl}) left top repeat`;
  document.body.appendChild(div);
  return id;
};

// 该方法只允许调用一次
const watermark = (imgUrl:string) => {
  if (!imgUrl) return;
  let id = setWatermark(imgUrl);
  setInterval(() => {
    if (document.getElementById(id) === null) {
      id = setWatermark(imgUrl);
    }
  }, 500);
  window.onresize = () => {
    setWatermark(imgUrl);
  };
};

export default watermark;
