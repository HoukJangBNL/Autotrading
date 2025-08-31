const { createProxyMiddleware } = require('http-proxy-middleware');
const fs = require('fs');
const path = require('path');

module.exports = function(app) {
  // Read SSL certificates
  const certPath = path.join(__dirname, '../../config/cert.pem');
  const keyPath = path.join(__dirname, '../../config/key.pem');
  
  let httpsAgent = undefined;
  
  // Check if certificates exist
  if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    const https = require('https');
    httpsAgent = new https.Agent({
      rejectUnauthorized: false, // Accept self-signed certificates
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath)
    });
  }

  // Proxy API requests to backend
  const apiTarget = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8182';
  app.use(
    '/api',
    createProxyMiddleware({
      target: apiTarget,
      changeOrigin: true,
      secure: false, // Accept self-signed certificates
      agent: httpsAgent,
      onProxyReq: (proxyReq, req, res) => {
        console.log(`[Proxy] ${req.method} ${req.path} -> ${apiTarget}${req.path}`);
      },
      onError: (err, req, res) => {
        console.error('[Proxy Error]:', err);
      }
    })
  );

  // Proxy WebSocket connections
  const wsTarget = (process.env.REACT_APP_WS_URL || 'wss://127.0.0.1:8182/ws');
  app.use(
    '/ws',
    createProxyMiddleware({
      target: wsTarget,
      ws: true,
      changeOrigin: true,
      secure: false, // Accept self-signed certificates
      agent: httpsAgent,
      onError: (err, req, res) => {
        console.error('[WebSocket Proxy Error]:', err);
      }
    })
  );
};