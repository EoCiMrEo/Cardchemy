import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { Provider } from 'react-redux'
import { MotionConfig } from 'framer-motion'
import { store } from './store'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </Provider>
  </React.StrictMode>,
)
