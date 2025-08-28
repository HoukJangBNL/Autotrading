"""Secure token storage using keyring and database backup."""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import os

try:
    import keyring
    KEYRING_AVAILABLE = True
except Exception:
    KEYRING_AVAILABLE = False

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..config.settings import get_settings
# Avoid circular import - import get_db only when needed
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TokenStore:
    """
    Manages secure storage and retrieval of OAuth tokens.
    
    Uses keyring as primary storage with encrypted database backup.
    Handles token validation and expiration checking.
    """
    
    def __init__(self):
        """Initialize token store with encryption setup."""
        self.settings = get_settings()
        self.service_name = "schwab_autotrader"
        self.username = "oauth_token"
        self._init_encryption()
        
    def _init_encryption(self) -> None:
        """Initialize encryption for database storage."""
        # Generate or load encryption key
        if KEYRING_AVAILABLE:
            try:
                key = keyring.get_password(self.service_name, "encryption_key")
                if not key:
                    key = Fernet.generate_key().decode()
                    keyring.set_password(self.service_name, "encryption_key", key)
                    logger.info("Generated new encryption key in keyring")
            except Exception as e:
                logger.warning(f"Keyring failed, using environment variable: {e}")
                key = os.environ.get("ENCRYPTION_KEY")
                if not key:
                    key = Fernet.generate_key().decode()
                    logger.warning("Generated temporary encryption key (not persisted)")
        else:
            # Use environment variable or generate temporary key
            key = os.environ.get("ENCRYPTION_KEY")
            if not key:
                key = Fernet.generate_key().decode()
                logger.warning("Generated temporary encryption key (not persisted)")
        self.cipher = Fernet(key.encode())
        
    def save_token(self, token_data: Dict[str, Any]) -> None:
        """
        Save token to both keyring and database.
        
        Args:
            token_data: Token data including access_token, refresh_token, expires_at
            
        Raises:
            RuntimeError: If token save fails
        """
        try:
            # Add metadata
            token_data['saved_at'] = datetime.now().isoformat()
            if 'expires_at' not in token_data and 'expires_in' in token_data:
                # Calculate expiration from expires_in
                expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
                token_data['expires_at'] = expires_at.isoformat()
            
            # Save to keyring (primary) if available
            token_json = json.dumps(token_data)
            if KEYRING_AVAILABLE:
                try:
                    keyring.set_password(
                        self.service_name,
                        self.username,
                        token_json
                    )
                    logger.info("Token saved to keyring")
                except Exception as e:
                    logger.warning(f"Failed to save to keyring: {e}")
            
            # Save encrypted to database (backup)
            try:
                encrypted = self.cipher.encrypt(token_json.encode()).decode()
                self._save_to_database(encrypted)
                logger.info("Token backup saved to database")
            except Exception as e:
                logger.warning(f"Failed to save token backup to database: {e}")
                # Don't fail if backup fails
                
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise RuntimeError(f"Token save failed: {e}")
            
    def _save_to_database(self, encrypted_token: str) -> None:
        """Save encrypted token to database."""
        # Import here to avoid circular import
        from ..data.database import get_db
        db = next(get_db())
        try:
            # Create table if not exists
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY,
                    encrypted_token TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Upsert token
            existing = db.execute(text("SELECT id FROM auth_tokens LIMIT 1")).first()
            if existing:
                db.execute(
                    text("UPDATE auth_tokens SET encrypted_token = :token, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                    {"token": encrypted_token, "id": existing[0]}
                )
            else:
                db.execute(
                    text("INSERT INTO auth_tokens (encrypted_token) VALUES (:token)"),
                    {"token": encrypted_token}
                )
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
    def load_token(self) -> Optional[Dict[str, Any]]:
        """
        Load token from storage.
        
        Returns:
            Token data dict or None if not found
        """
        try:
            # Try keyring first if available
            if KEYRING_AVAILABLE:
                try:
                    token_json = keyring.get_password(self.service_name, self.username)
                    if token_json:
                        logger.debug("Token loaded from keyring")
                        return json.loads(token_json)
                except Exception as e:
                    logger.warning(f"Failed to load from keyring: {e}")
                    
            # Fallback to database
            token_data = self._load_from_database()
            if token_data:
                # Restore to keyring for next time if available
                if KEYRING_AVAILABLE:
                    try:
                        keyring.set_password(self.service_name, self.username, json.dumps(token_data))
                        logger.info("Token restored from database backup to keyring")
                    except Exception:
                        pass
                return token_data
                
            logger.debug("No token found in storage")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
            return None
            
    def _load_from_database(self) -> Optional[Dict[str, Any]]:
        """Load and decrypt token from database."""
        # Import here to avoid circular import
        from ..data.database import get_db
        db = next(get_db())
        try:
            result = db.execute(
                text("SELECT encrypted_token FROM auth_tokens ORDER BY updated_at DESC LIMIT 1")
            ).first()
            
            if result:
                decrypted = self.cipher.decrypt(result[0].encode()).decode()
                return json.loads(decrypted)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load token from database: {e}")
            return None
        finally:
            db.close()
            
    def is_token_valid(self, token_data: Optional[Dict[str, Any]]) -> bool:
        """
        Check if token is still valid.
        
        Schwab tokens expire in 7 days. We refresh if less than 1 day remaining.
        
        Args:
            token_data: Token data to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        if not token_data:
            return False
            
        if 'expires_at' not in token_data:
            logger.warning("Token missing expiration date")
            return False
            
        try:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            now = datetime.now()
            
            # Check if expired
            if now >= expires_at:
                logger.info("Token has expired")
                return False
                
            # Check if expiring soon (less than 1 day)
            time_remaining = expires_at - now
            if time_remaining < timedelta(days=1):
                logger.warning(f"Token expiring soon: {time_remaining}")
                # Still valid but needs refresh soon
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking token validity: {e}")
            return False
            
    def delete_token(self) -> None:
        """Delete stored token from all locations."""
        # Delete from keyring if available
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.service_name, self.username)
                logger.info("Token deleted from keyring")
            except Exception as e:
                logger.warning(f"Failed to delete token from keyring: {e}")
            
        # Delete from database
        try:
            # Import here to avoid circular import
            from ..data.database import get_db
            db = next(get_db())
            db.execute(text("DELETE FROM auth_tokens"))
            db.commit()
            db.close()
            logger.info("Token deleted from database")
        except Exception as e:
            logger.warning(f"Failed to delete token from database: {e}")
            
    def get_token_age(self, token_data: Optional[Dict[str, Any]]) -> Optional[timedelta]:
        """
        Get the age of the token.
        
        Args:
            token_data: Token data
            
        Returns:
            Age of token as timedelta or None
        """
        if not token_data or 'saved_at' not in token_data:
            return None
            
        try:
            saved_at = datetime.fromisoformat(token_data['saved_at'])
            return datetime.now() - saved_at
        except Exception:
            return None
            
    def get_token_file_path(self) -> Path:
        """
        Get the token file path for schwab-py compatibility.
        
        Returns:
            Path to token file
        """
        return Path(self.settings.config_dir) / "schwab_token.json"
        
    def save_to_file(self, token_data: Dict[str, Any]) -> None:
        """
        Save token to file for schwab-py compatibility.
        
        Args:
            token_data: Token data to save
        """
        token_path = self.get_token_file_path()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure token format is compatible with schwab-py
        # schwab-py expects specific fields in the token
        formatted_token = {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'token_type': token_data.get('token_type', 'Bearer'),
            'expires_in': token_data.get('expires_in', 1800),
            'scope': token_data.get('scope', ''),
            'expires_at': token_data.get('expires_at'),
            'refresh_token_expires_in': token_data.get('refresh_token_expires_in', 604800),  # 7 days
            'refresh_token_expires_at': token_data.get('refresh_token_expires_at'),
        }
        
        # Remove None values
        formatted_token = {k: v for k, v in formatted_token.items() if v is not None}
        
        with open(token_path, 'w') as f:
            json.dump(formatted_token, f, indent=2)
        logger.debug(f"Token saved to file: {token_path}")
        
    def load_from_file(self) -> Optional[Dict[str, Any]]:
        """
        Load token from file if it exists.
        
        Returns:
            Token data or None
        """
        token_path = self.get_token_file_path()
        if token_path.exists():
            try:
                with open(token_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load token from file: {e}")
        return None