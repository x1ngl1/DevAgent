import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import RootApp from './App';
import './App.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    { /* 主题配置移至 App.jsx ConfigProvider */ }
    <ConfigProvider locale={zhCN}>
      <App>
        <RootApp />
      </App>
    </ConfigProvider>
  </React.StrictMode>
);
