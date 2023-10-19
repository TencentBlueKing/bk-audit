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
const axios = require('axios');
const history = require('connect-history-api-fallback');
const cookieParser = require('cookie-parser');
const Express = require('express');
const artTemplate = require('express-art-template');
const path = require('path');

const app = new Express();
const PORT = process.env.PORT || 5000;
const http = axios.create({
  withCredentials: true,
});

http.interceptors.response.use(response => response, error => Promise.reject(error));

// 注入全局变量
const GLOBAL_VAR = {
  // 后台API 地址从环境变量中获取
  AUDIT_AJAX_URL_PREFIX: process.env.AUDIT_AJAX_URL_PREFIX || 'AUDIT_AJAX_URL_PREFIX',
  AJAX_URL_PREFIX: process.env.AJAX_URL_PREFIX || 'AJAX_URL_PREFIX',
  TEST_AA: 'TEST_AA',
};

// APA 重定向回首页，由首页Route响应处理
// https://github.com/bripkens/connect-history-api-fallback#index
app.use(history({
  index: '/',
  rewrites: [
    {
      // from: /\d+\.\d+\.\d+\.\d+$/,
      from: /\/(\d+\.)*\d+$/,
      to: '/',
    },
    {
      // 兼容 /bcs/projectId/app/214/taskgroups/0.-1-13.test123.10013.1510806131114508229/containers/containerId
      from: /\/\/+.*\..*\//,
      to: '/',
    },
  ],
}));

app.use(cookieParser());

// 首页
app.get('/', (req, res) => {
  const index = path.join(__dirname, '../dist/index.html');
  res.render(index, GLOBAL_VAR);
});
app.get('/login-success.html', (req, res) => {
  const loginSuccess = path.join(__dirname, '../dist/login-success.html');
  res.render(loginSuccess);
});

// 配置静态资源
app.use('/assets', Express.static(path.join(__dirname, '../dist/assets')));
app.use('/images', Express.static(path.join(__dirname, '../dist/images')));
app.use('/monacoeditorwork', Express.static(path.join(__dirname, '../dist/monacoeditorwork')));

// 配置视图
app.set('views', path.join(__dirname, '../dist'));

// 配置模板引擎
// http://aui.github.io/art-template/zh-cn/docs/
app.engine('html', artTemplate);
app.set('view engine', 'html');

// 配置端口
app.listen(PORT, () => {
  console.log(`App is running in port ${PORT}`);
});
