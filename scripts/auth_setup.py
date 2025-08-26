#!/usr/bin/env python3
"""
Interactive OAuth setup script for Schwab API authentication.

This script guides users through the OAuth flow to obtain initial tokens.
"""

import asyncio
import sys
import webbrowser
import ssl
import json
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import queue
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth.oauth_manager import OAuthManager
from src.auth.exceptions import AuthenticationError
from src.config.settings import get_settings
from src.utils.logger import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Schwab."""
    
    def __init__(self, *args, auth_queue: queue.Queue, callback_path: str = '/', **kwargs):
        self.auth_queue = auth_queue
        self.callback_path = callback_path
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to suppress server logs."""
        pass
    
    def do_GET(self):
        """Handle GET request with authorization code."""
        # Parse the URL
        parsed_url = urlparse(self.path)
        
        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Check if this is the callback
        if parsed_url.path == self.callback_path:
            params = parse_qs(parsed_url.query)
            
            if 'code' in params:
                # Success
                self.wfile.write(b"""
                <html>
                <head><title>Authentication Successful</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Authentication Successful!</h1>
                    <p>You can now close this window and return to the terminal.</p>
                </body>
                </html>
                """)
                
                # Put the full URL in the queue
                # Get the port from server address
                port = self.server.server_address[1]
                self.auth_queue.put(f"https://127.0.0.1:{port}{self.path}")
                
            elif 'error' in params:
                # Error
                error = params.get('error', ['Unknown'])[0]
                error_desc = params.get('error_description', [''])[0]
                
                self.wfile.write(f"""
                <html>
                <head><title>Authentication Failed</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: red;">Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>{error_desc}</p>
                </body>
                </html>
                """.encode())
                
                self.auth_queue.put(f"error:{error}:{error_desc}")
            else:
                # Unknown response
                self.wfile.write(b"""
                <html>
                <head><title>Invalid Response</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1>Invalid Response</h1>
                    <p>The response from Schwab was not recognized.</p>
                </body>
                </html>
                """)


class AuthSetup:
    """Interactive authentication setup."""
    
    def __init__(self):
        self.settings = get_settings()
        self.oauth_manager = OAuthManager()
        self.auth_queue = queue.Queue()
    
    def print_banner(self):
        """Print welcome banner."""
        print("\n" + "="*60)
        print("Schwab API Authentication Setup")
        print("="*60)
        print("\nThis script will help you authenticate with the Schwab API.")
        print("Make sure you have:")
        print("  1. Created an app at https://developer.schwab.com")
        print("  2. Set the callback URL to: https://127.0.0.1:8182")
        print("  3. Your app is in 'Ready for Use' status")
        print("  4. Your API key and app secret in the .env file")
        print("\n" + "="*60 + "\n")
    
    def verify_settings(self) -> bool:
        """Verify required settings are present."""
        print("Checking configuration...")
        
        errors = []
        
        if not self.settings.schwab.api_key:
            errors.append("- SCHWAB_API_KEY is not set")
        
        if not self.settings.schwab.app_secret:
            errors.append("- SCHWAB_APP_SECRET is not set")
        
        # Accept any callback URL that starts with https://127.0.0.1
        if not self.settings.schwab.callback_url.startswith("https://127.0.0.1"):
            errors.append(f"- Callback URL should start with https://127.0.0.1, got {self.settings.schwab.callback_url}")
        
        if errors:
            print("\n❌ Configuration errors found:")
            for error in errors:
                print(error)
            print("\nPlease fix these issues in your .env file and try again.")
            return False
        
        print("✅ Configuration looks good!")
        print(f"   API Key: {self.settings.schwab.api_key[:10]}...")
        print(f"   Callback: {self.settings.schwab.callback_url}")
        return True
    
    def start_callback_server(self) -> HTTPServer:
        """Start HTTPS server for OAuth callback."""
        # Create self-signed certificate context
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create server - Extract port from callback URL
        callback_url = self.settings.schwab.callback_url
        port = 8182  # default
        if callback_url:
            from urllib.parse import urlparse
            parsed = urlparse(callback_url)
            if parsed.port:
                port = parsed.port
        
        server_address = ('127.0.0.1', port)
        
        # Custom handler factory to pass auth_queue and callback path
        parsed_callback = urlparse(self.settings.schwab.callback_url)
        callback_path = parsed_callback.path or '/'
        
        def handler_factory(*args, **kwargs):
            return CallbackHandler(*args, auth_queue=self.auth_queue, callback_path=callback_path, **kwargs)
        
        httpd = HTTPServer(server_address, handler_factory)
        
        # Wrap with SSL - use self-signed certificate
        # For Python 3.10+, we need to create a self-signed certificate
        import tempfile
        import subprocess
        
        # Create temporary certificate
        with tempfile.NamedTemporaryFile(suffix='.pem', delete=False) as cert_file:
            cert_path = cert_file.name
            
        # Generate self-signed certificate
        subprocess.run([
            'openssl', 'req', '-new', '-x509', '-keyout', cert_path,
            '-out', cert_path, '-days', '365', '-nodes',
            '-subj', '/CN=localhost'
        ], capture_output=True)
        
        ssl_context.load_cert_chain(cert_path)
        
        # Wrap socket with SSL
        httpd.socket = ssl_context.wrap_socket(
            httpd.socket,
            server_side=True
        )
        
        # Start server in thread
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        return httpd
    
    async def run_oauth_flow(self) -> bool:
        """Run the OAuth flow."""
        print("\nStarting OAuth flow...")
        
        # Generate authorization URL
        auth_url = self.oauth_manager.get_authorization_url()
        
        print("\n" + "="*60)
        print("IMPORTANT: SSL Certificate Warning")
        print("="*60)
        print("Your browser will show a security warning because we're using")
        print("a self-signed certificate for the local callback server.")
        print("\nThis is NORMAL and SAFE. When you see the warning:")
        print("  1. Click 'Advanced' or 'Show Details'")
        print("  2. Click 'Proceed to 127.0.0.1' or 'Accept the Risk'")
        print("="*60 + "\n")
        
        # Start callback server
        server = self.start_callback_server()
        print(f"✅ Callback server started on {self.settings.schwab.callback_url}")
        
        # Open browser
        print(f"\nOpening browser for authentication...")
        print(f"\nIf the browser doesn't open, manually visit:")
        print(f"{auth_url}\n")
        
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("Waiting for authentication callback...")
        print("(Complete the login in your browser)")
        
        try:
            # Wait for callback (timeout after 5 minutes)
            callback_url = self.auth_queue.get(timeout=300)
            
            if callback_url.startswith("error:"):
                parts = callback_url.split(":", 2)
                error = parts[1] if len(parts) > 1 else "Unknown"
                desc = parts[2] if len(parts) > 2 else ""
                print(f"\n❌ Authentication failed: {error}")
                if desc:
                    print(f"   {desc}")
                return False
            
            print("\n✅ Authorization code received!")
            
            # Exchange code for token
            print("Exchanging authorization code for access token...")
            token_data = await self.oauth_manager.exchange_code_for_token(callback_url)
            
            print("✅ Access token obtained successfully!")
            
            # Test the token
            print("\nTesting authentication...")
            client = await self.oauth_manager.authenticate()
            
            # Get account info
            response = await client.get_account_numbers()
            response.raise_for_status()
            accounts = response.json()
            
            print(f"✅ Authentication successful! Found {len(accounts)} account(s)")
            
            # Show token info
            token_info = self.oauth_manager.get_token_info()
            if token_info:
                print(f"\nToken Information:")
                print(f"  - Valid: {token_info['is_valid']}")
                print(f"  - Expires: {token_info.get('expires_at', 'Unknown')}")
                print(f"  - Time until expiry: {token_info.get('time_until_expiry', 'Unknown')}")
            
            return True
            
        except queue.Empty:
            print("\n❌ Timeout waiting for authentication callback")
            return False
        except Exception as e:
            print(f"\n❌ Authentication error: {e}")
            logger.exception("Authentication error")
            return False
        finally:
            # Stop server
            server.shutdown()
    
    async def check_existing_token(self) -> bool:
        """Check if valid token already exists."""
        print("\nChecking for existing token...")
        
        token_info = self.oauth_manager.get_token_info()
        if not token_info:
            print("No existing token found.")
            return False
        
        print("\nExisting token found:")
        print(f"  - Valid: {token_info['is_valid']}")
        print(f"  - Expires: {token_info.get('expires_at', 'Unknown')}")
        print(f"  - Time until expiry: {token_info.get('time_until_expiry', 'Unknown')}")
        print(f"  - Expiring soon: {token_info['is_expiring_soon']}")
        
        if token_info['is_valid'] and not token_info['is_expiring_soon']:
            # Test the token
            try:
                print("\nTesting existing token...")
                client = await self.oauth_manager.authenticate()
                response = await client.get_account_numbers()
                response.raise_for_status()
                print("✅ Existing token is valid and working!")
                return True
            except Exception as e:
                print(f"❌ Existing token test failed: {e}")
        
        return False
    
    async def run(self, force_new: bool = False) -> bool:
        """Run the authentication setup."""
        self.print_banner()
        
        # Verify settings
        if not self.verify_settings():
            return False
        
        # Check existing token
        if not force_new:
            if await self.check_existing_token():
                response = input("\nDo you want to generate a new token anyway? (y/N): ")
                if response.lower() != 'y':
                    print("\n✅ Using existing token.")
                    return True
        
        # Run OAuth flow
        success = await self.run_oauth_flow()
        
        if success:
            print("\n" + "="*60)
            print("✅ Authentication Setup Complete!")
            print("="*60)
            print("\nYour authentication token has been saved securely.")
            print("The token will expire in 7 days and will need to be refreshed.")
            print("\nYou can now run your trading application!")
        else:
            print("\n" + "="*60)
            print("❌ Authentication Setup Failed")
            print("="*60)
            print("\nPlease check the error messages above and try again.")
            print("\nCommon issues:")
            print("  - App not in 'Ready for Use' status")
            print("  - Incorrect API key or secret")
            print("  - Callback URL mismatch")
        
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Schwab API Authentication Setup"
    )
    parser.add_argument(
        '--force-new',
        action='store_true',
        help='Force generation of a new token even if one exists'
    )
    
    args = parser.parse_args()
    
    setup = AuthSetup()
    
    try:
        success = asyncio.run(setup.run(force_new=args.force_new))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nAuthentication cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()