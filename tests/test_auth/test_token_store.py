"""Tests for token store."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import keyring
from cryptography.fernet import Fernet

from src.auth.token_store import TokenStore


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.config_dir = "/tmp/test_config"
    return settings


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.execute = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.close = Mock()
    return db


@pytest.fixture
def valid_token_data():
    """Valid token data for testing."""
    return {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': (datetime.now() + timedelta(days=6)).isoformat(),
        'token_type': 'Bearer',
        'expires_in': 518400
    }


@pytest.fixture
def token_store(mock_settings, mock_db):
    """Token store instance for testing."""
    with patch('src.auth.token_store.get_settings', return_value=mock_settings):
        with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
            with patch('src.auth.token_store.keyring.get_password', return_value=None):
                with patch('src.auth.token_store.keyring.set_password'):
                    store = TokenStore()
                    return store


class TestTokenStore:
    """Test cases for TokenStore."""
    
    def test_init_encryption_new_key(self, mock_settings):
        """Test encryption initialization with new key."""
        # Generate a valid Fernet key for testing
        test_key = Fernet.generate_key()
        
        with patch('src.auth.token_store.get_settings', return_value=mock_settings):
            with patch('src.auth.token_store.keyring.get_password', return_value=None) as mock_get:
                with patch('src.auth.token_store.keyring.set_password') as mock_set:
                    with patch('src.auth.token_store.Fernet.generate_key') as mock_gen:
                        mock_gen.return_value = test_key
                        
                        store = TokenStore()
                        
                        mock_get.assert_called_with('schwab_autotrader', 'encryption_key')
                        mock_set.assert_called_with('schwab_autotrader', 'encryption_key', test_key.decode())
                        assert store.cipher is not None
                        
    def test_init_encryption_existing_key(self, mock_settings):
        """Test encryption initialization with existing key."""
        existing_key = Fernet.generate_key().decode()
        
        with patch('src.auth.token_store.get_settings', return_value=mock_settings):
            with patch('src.auth.token_store.keyring.get_password', return_value=existing_key) as mock_get:
                with patch('src.auth.token_store.keyring.set_password') as mock_set:
                    store = TokenStore()
                    
                    mock_get.assert_called_with('schwab_autotrader', 'encryption_key')
                    mock_set.assert_not_called()
                    assert store.cipher is not None
                    
    def test_save_token_success(self, token_store, valid_token_data, mock_db):
        """Test successful token save."""
        # Mock the database query result for checking existing token
        mock_result = Mock()
        mock_result.first.return_value = None  # No existing token
        mock_db.execute.return_value = mock_result
        
        with patch('src.auth.token_store.keyring.set_password') as mock_keyring:
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Execute
                token_store.save_token(valid_token_data)
                
                # Verify keyring save
                mock_keyring.assert_called_once()
                args = mock_keyring.call_args[0]
                assert args[0] == 'schwab_autotrader'
                assert args[1] == 'oauth_token'
                saved_data = json.loads(args[2])
                assert saved_data['access_token'] == 'test_access_token'
                assert 'saved_at' in saved_data
                
                # Verify database save attempt
                assert mock_db.execute.call_count >= 1
                mock_db.commit.assert_called_once()
                
    def test_save_token_with_expires_in(self, token_store, mock_db):
        """Test token save with expires_in calculation."""
        token_data = {
            'access_token': 'test_token',
            'expires_in': 3600  # 1 hour
        }
        
        with patch('src.auth.token_store.keyring.set_password') as mock_keyring:
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Execute
                token_store.save_token(token_data)
                
                # Verify expires_at was calculated
                saved_json = mock_keyring.call_args[0][2]
                saved_data = json.loads(saved_json)
                assert 'expires_at' in saved_data
                
    def test_save_token_keyring_failure(self, token_store):
        """Test token save with keyring failure."""
        with patch('src.auth.token_store.keyring.set_password', side_effect=Exception("Keyring error")):
            with pytest.raises(RuntimeError, match="Token save failed"):
                token_store.save_token({'access_token': 'test'})
                
    def test_load_token_from_keyring(self, token_store, valid_token_data):
        """Test loading token from keyring."""
        token_json = json.dumps(valid_token_data)
        
        with patch('src.auth.token_store.keyring.get_password', return_value=token_json):
            # Execute
            loaded = token_store.load_token()
            
            # Verify
            assert loaded == valid_token_data
            
    def test_load_token_from_database(self, token_store, valid_token_data, mock_db):
        """Test loading token from database when keyring fails."""
        encrypted_token = token_store.cipher.encrypt(json.dumps(valid_token_data).encode()).decode()
        mock_db.execute.return_value.first.return_value = (encrypted_token,)
        
        with patch('src.auth.token_store.keyring.get_password', return_value=None):
            with patch('src.auth.token_store.keyring.set_password') as mock_set:
                with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                    # Execute
                    loaded = token_store.load_token()
                    
                    # Verify
                    assert loaded == valid_token_data
                    # Should restore to keyring
                    mock_set.assert_called_once()
                    
    def test_load_token_not_found(self, token_store, mock_db):
        """Test loading when no token exists."""
        mock_db.execute.return_value.first.return_value = None
        
        with patch('src.auth.token_store.keyring.get_password', return_value=None):
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Execute
                loaded = token_store.load_token()
                
                # Verify
                assert loaded is None
                
    def test_is_token_valid_with_valid_token(self, token_store, valid_token_data):
        """Test token validation with valid token."""
        assert token_store.is_token_valid(valid_token_data) is True
        
    def test_is_token_valid_with_expired_token(self, token_store):
        """Test token validation with expired token."""
        expired_token = {
            'expires_at': (datetime.now() - timedelta(days=1)).isoformat()
        }
        assert token_store.is_token_valid(expired_token) is False
        
    def test_is_token_valid_expiring_soon(self, token_store):
        """Test token validation with token expiring soon."""
        expiring_token = {
            'expires_at': (datetime.now() + timedelta(hours=12)).isoformat()
        }
        # Should still be valid but log warning
        assert token_store.is_token_valid(expiring_token) is True
        
    def test_is_token_valid_no_token(self, token_store):
        """Test token validation with None."""
        assert token_store.is_token_valid(None) is False
        
    def test_is_token_valid_missing_expires_at(self, token_store):
        """Test token validation without expiration date."""
        token = {'access_token': 'test'}
        assert token_store.is_token_valid(token) is False
        
    def test_delete_token(self, token_store, mock_db):
        """Test token deletion."""
        with patch('src.auth.token_store.keyring.delete_password') as mock_delete:
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Execute
                token_store.delete_token()
                
                # Verify
                mock_delete.assert_called_once_with('schwab_autotrader', 'oauth_token')
                mock_db.execute.assert_called()
                mock_db.commit.assert_called_once()
                
    def test_get_token_age(self, token_store):
        """Test getting token age."""
        token_data = {
            'saved_at': (datetime.now() - timedelta(days=2, hours=3)).isoformat()
        }
        
        age = token_store.get_token_age(token_data)
        
        assert age is not None
        assert age.days == 2
        
    def test_get_token_age_no_saved_at(self, token_store):
        """Test getting token age without saved_at."""
        assert token_store.get_token_age({'access_token': 'test'}) is None
        
    def test_get_token_file_path(self, token_store, mock_settings):
        """Test getting token file path."""
        path = token_store.get_token_file_path()
        assert str(path) == "/tmp/test_config/schwab_token.json"
        
    def test_save_to_file(self, token_store, valid_token_data):
        """Test saving token to file."""
        with patch('builtins.open', create=True) as mock_open:
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                # Execute
                token_store.save_to_file(valid_token_data)
                
                # Verify
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                mock_open.assert_called_once()
                mock_file.write.assert_called()
                
    def test_load_from_file_exists(self, token_store, valid_token_data):
        """Test loading token from existing file."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = json.dumps(valid_token_data)
                mock_open.return_value.__enter__.return_value = mock_file
                
                # Execute
                loaded = token_store.load_from_file()
                
                # Verify
                assert loaded == valid_token_data
                
    def test_load_from_file_not_exists(self, token_store):
        """Test loading token from non-existent file."""
        with patch('pathlib.Path.exists', return_value=False):
            loaded = token_store.load_from_file()
            assert loaded is None
            
    def test_load_from_file_error(self, token_store):
        """Test loading token with file error."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', side_effect=Exception("File error")):
                loaded = token_store.load_from_file()
                assert loaded is None
    
    def test_load_token_general_exception(self, token_store):
        """Test load_token with general exception."""
        with patch('src.auth.token_store.keyring.get_password', side_effect=Exception("General error")):
            loaded = token_store.load_token()
            assert loaded is None
    
    def test_load_from_database_exception(self, token_store, mock_db):
        """Test database load with exception."""
        mock_db.execute.side_effect = Exception("DB error")
        
        with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
            result = token_store._load_from_database()
            assert result is None
            mock_db.close.assert_called_once()
    
    def test_is_token_valid_exception(self, token_store):
        """Test token validation with parsing exception."""
        invalid_token = {
            'expires_at': 'invalid-date-format'
        }
        assert token_store.is_token_valid(invalid_token) is False
    
    def test_delete_token_keyring_exception(self, token_store, mock_db):
        """Test token deletion with keyring exception."""
        with patch('src.auth.token_store.keyring.delete_password', side_effect=Exception("Keyring error")):
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Should not raise, just log warning
                token_store.delete_token()
                # Should still try to delete from database
                mock_db.execute.assert_called()
                mock_db.commit.assert_called_once()
    
    def test_delete_token_database_exception(self, token_store, mock_db):
        """Test token deletion with database exception."""
        mock_db.execute.side_effect = Exception("DB error")
        
        with patch('src.auth.token_store.keyring.delete_password') as mock_delete:
            with patch('src.auth.token_store.get_db', return_value=iter([mock_db])):
                # Should not raise, just log warnings
                token_store.delete_token()
                # Should have tried keyring delete first
                mock_delete.assert_called_once()
    
    def test_get_token_age_invalid_date(self, token_store):
        """Test get_token_age with invalid date format."""
        token_data = {
            'saved_at': 'not-a-valid-date'
        }
        age = token_store.get_token_age(token_data)
        assert age is None