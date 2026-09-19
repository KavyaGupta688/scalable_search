import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { MotionProvider } from './components/Motion';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MotionProvider><App /></MotionProvider>
  </React.StrictMode>
);

import './redesign.css';
import './motion.css';
