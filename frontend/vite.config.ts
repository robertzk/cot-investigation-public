// import { defineConfig } from 'vite';
// import react from '@vitejs/plugin-react'

// // https://vite.dev/config/
// export default defineConfig({
//   plugins: [react()],
// })

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: [
      'ag-grid-react',
      'ag-grid-community',
      'ag-grid-community/styles/ag-grid.css',
      'ag-grid-community/styles/ag-theme-alpine.css'
    ]
  }
})