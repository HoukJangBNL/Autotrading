#!/usr/bin/env python3
"""
Create HTTPS server for Schwab OAuth callback.
This runs outside Docker to handle the callback on https://127.0.0.1:8000/callback
"""

import asyncio
import ssl
import logging
from aiohttp import web
import subprocess
import tempfile
import os
import requests
import webbrowser
from urllib.parse import parse_qs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchwabOAuthServer:
    def __init__(self):
        self.authorization_code = None
        self.state = None
        
    async def handle_callback(self, request):
        """Handle OAuth callback from Schwab."""
        try:
            # Extract parameters
            params = request.rel_url.query
            self.authorization_code = params.get('code')
            self.state = params.get('state')
            
            if 'error' in params:
                error = params.get('error')
                error_desc = params.get('error_description', 'Unknown error')
                html = f"""
                <html>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>{error}: {error_desc}</p>
                </body>
                </html>
                """
                return web.Response(text=html, content_type='text/html')
            
            if self.authorization_code:
                # Forward the code to our backend
                try:
                    backend_response = requests.get(
                        f'http://localhost:8000/api/auth/callback',
                        params={'code': self.authorization_code, 'state': self.state}
                    )
                    
                    if backend_response.status_code == 200:
                        html = """
                        <html>
                        <head>
                            <meta http-equiv="refresh" content="2;url=http://localhost:3000/auth/success">
                        </head>
                        <body>
                            <h1>Authorization Successful!</h1>
                            <p>Redirecting to application...</p>
                            <script>
                                window.location.href = 'http://localhost:3000/auth/success';
                            </script>
                        </body>
                        </html>
                        """
                    else:
                        html = """
                        <html>
                        <body>
                            <h1>Authorization Failed</h1>
                            <p>Failed to process authorization code</p>
                        </body>
                        </html>
                        """
                except Exception as e:
                    logger.error(f"Failed to forward code to backend: {e}")
                    html = f"""
                    <html>
                    <body>
                        <h1>Authorization Failed</h1>
                        <p>Error: {e}</p>
                    </body>
                    </html>
                    """
                    
                return web.Response(text=html, content_type='text/html')
            
            html = """
            <html>
            <body>
                <h1>Authorization Failed</h1>
                <p>No authorization code received</p>
            </body>
            </html>
            """
            return web.Response(text=html, content_type='text/html')
            
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            return web.Response(text=f"Error: {e}", status=500)
    
    def create_ssl_context(self):
        """Create self-signed SSL certificate."""
        cert_file = '/tmp/schwab_cert.pem'
        key_file = '/tmp/schwab_key.pem'
        
        # Generate self-signed certificate if it doesn't exist
        if not os.path.exists(cert_file):
            logger.info("Generating self-signed certificate...")
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
                '-keyout', key_file,
                '-out', cert_file,
                '-days', '365',
                '-nodes',
                '-subj', '/CN=127.0.0.1'
            ], check=True)
            logger.info("Certificate generated")
        
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        return ssl_context
    
    async def run_server(self):
        """Run the HTTPS server."""
        app = web.Application()
        app.router.add_get('/callback', self.handle_callback)
        
        ssl_context = self.create_ssl_context()
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 8000, ssl_context=ssl_context)
        await site.start()
        
        logger.info("HTTPS server running on https://127.0.0.1:8000/callback")
        logger.info("Press Ctrl+C to stop")
        
        # Get auth URL from backend and open browser
        try:
            response = requests.get('http://localhost:8000/api/auth/login')
            if response.status_code == 200:
                auth_url = response.json().get('auth_url')
                if auth_url:
                    logger.info(f"Opening browser with auth URL: {auth_url[:100]}...")
                    webbrowser.open(auth_url)
        except Exception as e:
            logger.error(f"Failed to get auth URL: {e}")
        
        # Keep server running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await runner.cleanup()


async def main():
    server = SchwabOAuthServer()
    await server.run_server()


if __name__ == '__main__':
    asyncio.run(main())