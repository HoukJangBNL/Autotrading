#!/usr/bin/env python3
"""Troubleshoot Schwab API authentication issues."""

import sys
import os
from pathlib import Path
import urllib.parse
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

def check_configuration():
    """Check API configuration and common issues."""
    print("Schwab API Authentication Troubleshooting")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check environment variables
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL')
    
    print("1. Environment Variables Check:")
    print("-" * 40)
    
    issues = []
    
    if not api_key:
        print("❌ SCHWAB_API_KEY is not set")
        issues.append("Missing API key")
    else:
        print(f"✅ API Key: {api_key[:10]}...{api_key[-5:]}")
        print(f"   Length: {len(api_key)} characters")
        
        # Check for common issues
        if api_key.startswith(' ') or api_key.endswith(' '):
            print("⚠️  WARNING: API key has leading/trailing spaces")
            issues.append("API key has whitespace")
            
    if not app_secret:
        print("❌ SCHWAB_APP_SECRET is not set")
        issues.append("Missing app secret")
    else:
        print(f"✅ App Secret: {app_secret[:5]}...{app_secret[-3:]}")
        print(f"   Length: {len(app_secret)} characters")
        
        if app_secret.startswith(' ') or app_secret.endswith(' '):
            print("⚠️  WARNING: App secret has leading/trailing spaces")
            issues.append("App secret has whitespace")
            
    if not callback_url:
        print("❌ SCHWAB_CALLBACK_URL is not set")
        issues.append("Missing callback URL")
    else:
        print(f"✅ Callback URL: {callback_url}")
        
        # Parse and validate callback URL
        parsed = urllib.parse.urlparse(callback_url)
        print(f"   Protocol: {parsed.scheme}")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        
        # Check for common issues
        if parsed.scheme != 'https':
            print("⚠️  WARNING: Callback URL must use HTTPS")
            issues.append("Callback URL not HTTPS")
            
        if parsed.hostname != '127.0.0.1':
            print("⚠️  WARNING: Recommended hostname is 127.0.0.1")
            
        if parsed.port != 8182:
            print("⚠️  WARNING: Recommended port is 8182")
            
        if callback_url.endswith('/'):
            print("❌ ERROR: Callback URL has trailing slash - this will cause auth to fail!")
            issues.append("Callback URL has trailing slash")
            
    print("\n2. Auth URL Construction:")
    print("-" * 40)
    
    if api_key and callback_url:
        # Construct the auth URL as schwab-py does
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?response_type=code&client_id={api_key}&redirect_uri={urllib.parse.quote(callback_url, safe='')}"
        
        print("The authorization URL will be:")
        print(auth_url)
        print()
        print("URL Components:")
        print(f"- Base: https://api.schwabapi.com/v1/oauth/authorize")
        print(f"- Client ID: {api_key}")
        print(f"- Redirect URI (encoded): {urllib.parse.quote(callback_url, safe='')}")
        
    print("\n3. Common Issues and Solutions:")
    print("-" * 40)
    
    print("CRITICAL: Your app status must be 'Ready for use'")
    print("         NOT 'Approved - Pending' or any other status")
    print()
    
    print("Most common causes of 'We are unable to complete your request' error:")
    print()
    print("1. ❗ App Status Issue (Most Common)")
    print("   - Log into https://developer.schwab.com/")
    print("   - Check your app status")
    print("   - Must say EXACTLY 'Ready for use'")
    print("   - 'Approved - Pending' means NOT ready yet")
    print("   - Can take several days after initial approval")
    print()
    
    print("2. ❗ Callback URL Mismatch")
    print("   - Must EXACTLY match what's in Schwab Developer Portal")
    print("   - Case sensitive")
    print("   - No trailing slash")
    print("   - Include https:// and port")
    print(f"   - Your current URL: {callback_url}")
    print()
    
    print("3. ❗ Multiple Callback URLs")
    print("   - If you have multiple URLs, each must be on separate line")
    print("   - Click 'Add Another' button for each URL")
    print("   - Don't enter multiple URLs in one field")
    print()
    
    print("4. ⚠️  Recent Schwab Issues (2024)")
    print("   - Reports of issues with 127.0.0.1 URLs being rejected")
    print("   - Some users needed to recreate their app")
    print("   - Try using 'localhost' instead of '127.0.0.1' if issues persist")
    print()
    
    if issues:
        print("\n4. Issues Found:")
        print("-" * 40)
        for issue in issues:
            print(f"❌ {issue}")
    else:
        print("\n4. Configuration Check:")
        print("-" * 40)
        print("✅ No obvious configuration issues found")
        print("   If you still get errors, check:")
        print("   1. App status in Schwab Developer Portal")
        print("   2. Exact callback URL match")
        print("   3. Try recreating the app if nothing else works")
        
    print("\n5. Next Steps:")
    print("-" * 40)
    print("1. Log into https://developer.schwab.com/")
    print("2. Verify your app shows 'Ready for use'")
    print("3. Copy your callback URL EXACTLY as shown")
    print("4. Update .env file if needed")
    print("5. Contact traderapi@schwab.com if issues persist")
    print()
    print("Include this troubleshooting output in your support request.")
    

def test_api_endpoint():
    """Test if we can reach Schwab API endpoints."""
    print("\n6. API Connectivity Test:")
    print("-" * 40)
    
    try:
        # Test if we can reach the OAuth endpoint
        response = requests.get('https://api.schwabapi.com', timeout=5)
        print(f"✅ Can reach api.schwabapi.com (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Cannot reach api.schwabapi.com: {e}")
        
    try:
        # Test if we can reach developer portal
        response = requests.get('https://developer.schwab.com', timeout=5)
        print(f"✅ Can reach developer.schwab.com (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Cannot reach developer.schwab.com: {e}")


def check_token_file():
    """Check for existing token files."""
    print("\n7. Token File Check:")
    print("-" * 40)
    
    common_paths = [
        Path.home() / '.schwab_token.json',
        Path.cwd() / 'schwab_token.json',
        Path.cwd() / 'config' / 'schwab_token.json',
    ]
    
    found = False
    for path in common_paths:
        if path.exists():
            print(f"✅ Found token file: {path}")
            print(f"   Size: {path.stat().st_size} bytes")
            print(f"   Modified: {datetime.fromtimestamp(path.stat().st_mtime)}")
            found = True
            
    if not found:
        print("ℹ️  No existing token files found (this is normal for first-time setup)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SCHWAB API AUTHENTICATION TROUBLESHOOTER")
    print("=" * 60)
    print()
    print("This tool helps diagnose common Schwab API authentication issues.")
    print("The error 'We are unable to complete your request' usually means")
    print("a configuration mismatch or app status issue.")
    print()
    
    check_configuration()
    test_api_endpoint()
    check_token_file()
    
    print("\n" + "=" * 60)
    print("Troubleshooting complete!")
    print("=" * 60)