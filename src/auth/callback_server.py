"""HTTPS callback server for Schwab OAuth flow."""

import ssl
import asyncio
import logging
from urllib.parse import urlparse, parse_qs
from aiohttp import web
import tempfile
import os

logger = logging.getLogger(__name__)


class CallbackServer:
    """HTTPS server to handle OAuth callbacks."""
    
    def __init__(self, callback_url: str, state: str):
        """
        Initialize callback server.
        
        Args:
            callback_url: The expected callback URL
            state: The OAuth state parameter for CSRF protection
        """
        self.callback_url = callback_url
        self.expected_state = state
        self.authorization_code = None
        self.error = None
        self._app = None
        self._runner = None
        
    async def start(self):
        """Start the HTTPS callback server."""
        # Parse callback URL
        parsed = urlparse(self.callback_url)
        host = parsed.hostname
        port = parsed.port or 8000
        
        # Create web application
        self._app = web.Application()
        self._app.router.add_get('/callback', self.handle_callback)
        
        # Create self-signed certificate for HTTPS
        ssl_context = self._create_ssl_context()
        
        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port, ssl_context=ssl_context)
        await site.start()
        
        logger.info(f"Callback server listening on {self.callback_url}")
        
    async def stop(self):
        """Stop the callback server."""
        if self._runner:
            await self._runner.cleanup()
            
    async def handle_callback(self, request):
        """
        Handle OAuth callback request.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Get query parameters
            params = request.rel_url.query
            
            # Verify state
            state = params.get('state')
            if state != self.expected_state:
                self.error = "State mismatch - possible CSRF attack"
                return web.Response(
                    text="Authorization failed: Invalid state",
                    status=400
                )
            
            # Check for error
            if 'error' in params:
                self.error = f"{params.get('error')}: {params.get('error_description', 'Unknown error')}"
                return web.Response(
                    text=f"Authorization failed: {self.error}",
                    status=400
                )
            
            # Get authorization code
            self.authorization_code = params.get('code')
            if not self.authorization_code:
                self.error = "No authorization code received"
                return web.Response(
                    text="Authorization failed: No code received",
                    status=400
                )
            
            # Return success page that redirects to frontend
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authorization Successful</title>
                <meta http-equiv="refresh" content="2;url=http://localhost:3000/auth/success">
            </head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>Redirecting to application...</p>
                <script>
                    // Store auth success flag
                    localStorage.setItem('auth_callback_success', 'true');
                    // Redirect to frontend
                    setTimeout(() => {
                        window.location.href = 'http://localhost:3000/auth/success';
                    }, 1000);
                </script>
            </body>
            </html>
            """
            
            return web.Response(text=html, content_type='text/html')
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.error = str(e)
            return web.Response(
                text=f"Authorization failed: {e}",
                status=500
            )
    
    def _create_ssl_context(self):
        """Create SSL context with self-signed certificate."""
        # Create temporary self-signed certificate
        import subprocess
        
        cert_file = tempfile.NamedTemporaryFile(suffix='.pem', delete=False)
        key_file = tempfile.NamedTemporaryFile(suffix='.key', delete=False)
        
        try:
            # Generate self-signed certificate
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
                '-keyout', key_file.name,
                '-out', cert_file.name,
                '-days', '1',
                '-nodes',
                '-subj', '/CN=127.0.0.1'
            ], check=True, capture_output=True)
            
            # Create SSL context
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(cert_file.name, key_file.name)
            
            # Clean up temp files after loading
            cert_file.close()
            key_file.close()
            os.unlink(cert_file.name)
            os.unlink(key_file.name)
            
            return ssl_context
            
        except Exception as e:
            logger.error(f"Failed to create SSL certificate: {e}")
            # Fall back to HTTP if SSL fails
            return None
    
    async def wait_for_code(self, timeout: int = 300):
        """
        Wait for authorization code.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            Authorization code or None if error/timeout
        """
        for _ in range(timeout):
            if self.authorization_code or self.error:
                break
            await asyncio.sleep(1)
            
        return self.authorization_code