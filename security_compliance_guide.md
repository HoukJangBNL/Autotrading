# Security & Compliance Guide for Automated Trading System

## Overview

This document outlines security measures and compliance requirements for the Charles Schwab automated trading system. Given the sensitive nature of financial data and trading operations, security must be embedded at every layer.

## Security Architecture

### 1. Authentication & Authorization

#### OAuth2 Security
```python
# Secure token storage using encryption
from cryptography.fernet import Fernet
import keyring
import json

class SecureTokenStorage:
    def __init__(self):
        # Generate or load encryption key
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self):
        """Store encryption key in system keyring"""
        key = keyring.get_password("schwab_trader", "encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            keyring.set_password("schwab_trader", "encryption_key", key)
        return key.encode()
    
    def save_token(self, token_data: dict):
        """Encrypt and save token"""
        encrypted = self.cipher.encrypt(json.dumps(token_data).encode())
        with open('config/token.enc', 'wb') as f:
            f.write(encrypted)
```

#### Access Control
- **Role-Based Access Control (RBAC)**:
  - Admin: Full system access
  - Trader: Trading operations only
  - Viewer: Read-only access
  - Auditor: Logs and reports only

- **Multi-Factor Authentication**:
  - Require 2FA for all administrative actions
  - Time-based OTP for critical operations
  - IP whitelisting for production access

### 2. API Security

#### Rate Limiting Implementation
```python
from datetime import datetime, timedelta
import asyncio
from collections import deque

class RateLimiter:
    def __init__(self, calls_per_second: int = 2):
        self.calls_per_second = calls_per_second
        self.calls = deque()
        self.lock = asyncio.Lock()
    
    async def __aenter__(self):
        async with self.lock:
            now = datetime.now()
            # Remove calls older than 1 second
            while self.calls and self.calls[0] < now - timedelta(seconds=1):
                self.calls.popleft()
            
            # Wait if we've hit the limit
            if len(self.calls) >= self.calls_per_second:
                sleep_time = (self.calls[0] + timedelta(seconds=1) - now).total_seconds()
                await asyncio.sleep(sleep_time)
            
            self.calls.append(now)
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
```

#### API Key Management
- Store API keys in environment variables or secure vault
- Never commit credentials to version control
- Rotate API keys quarterly
- Monitor API key usage for anomalies

### 3. Data Security

#### Encryption at Rest
```python
# Database encryption
SQLALCHEMY_DATABASE_URI = (
    "postgresql://user:pass@localhost/trading"
    "?sslmode=require&sslcert=client-cert.pem&sslkey=client-key.pem"
)

# Enable transparent data encryption
ALTER DATABASE trading SET encryption = 'on';
```

#### Encryption in Transit
- Use TLS 1.3 for all API communications
- Implement certificate pinning for critical endpoints
- Use VPN for database connections
- Enable SSL/TLS for Redis connections

### 4. Network Security

#### Firewall Rules
```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH from specific IPs only
sudo ufw allow from 192.168.1.100 to any port 22

# Allow HTTPS for API
sudo ufw allow 443/tcp

# Allow monitoring
sudo ufw allow from 10.0.0.0/24 to any port 3000  # Grafana
sudo ufw allow from 10.0.0.0/24 to any port 9090  # Prometheus

sudo ufw enable
```

#### Network Isolation
- Separate VLANs for:
  - Trading systems
  - Database servers
  - Monitoring infrastructure
  - Administrative access

### 5. Audit Logging

#### Comprehensive Audit Trail
```python
import json
import hashlib
from datetime import datetime

class AuditLogger:
    def __init__(self, db_service):
        self.db_service = db_service
    
    def log_event(self, event_type: str, user: str, details: dict):
        """Log security event with integrity check"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user': user,
            'details': details,
            'ip_address': self._get_client_ip(),
            'session_id': self._get_session_id()
        }
        
        # Add integrity hash
        event['hash'] = self._calculate_hash(event)
        
        # Store in tamper-evident log
        self.db_service.store_audit_log(event)
    
    def _calculate_hash(self, event: dict) -> str:
        """Create tamper-evident hash"""
        event_str = json.dumps(event, sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()
```

#### Events to Log
- All authentication attempts (success/failure)
- API key usage
- Trading operations (orders placed/cancelled)
- Configuration changes
- Data exports
- System errors and exceptions
- Administrative actions

## Compliance Requirements

### 1. Financial Regulations

#### Record Keeping (SEC Rule 17a-4)
- **Retention Period**: 7 years for all trading records
- **Format**: Write-Once-Read-Many (WORM) storage
- **Accessibility**: Records must be readily accessible

```python
class ComplianceStorage:
    def store_trade_record(self, trade: dict):
        """Store trade record in compliance format"""
        record = {
            'trade_id': trade['order_id'],
            'timestamp': trade['executed_at'],
            'symbol': trade['symbol'],
            'quantity': trade['quantity'],
            'price': trade['price'],
            'side': trade['action'],
            'account': self._hash_account_number(trade['account']),
            'strategy': trade['strategy_id'],
            'regulatory_flags': self._check_regulatory_flags(trade)
        }
        
        # Store in WORM-compliant storage
        self._store_worm(record)
```

#### Best Execution (Reg NMS)
- Monitor execution quality
- Document order routing decisions
- Maintain execution quality statistics

### 2. Data Privacy

#### PII Protection
```python
class PIIProtection:
    def __init__(self):
        self.pii_fields = ['ssn', 'account_number', 'email', 'phone']
    
    def sanitize_data(self, data: dict) -> dict:
        """Remove or hash PII from data"""
        sanitized = data.copy()
        for field in self.pii_fields:
            if field in sanitized:
                sanitized[field] = self._hash_pii(sanitized[field])
        return sanitized
    
    def _hash_pii(self, value: str) -> str:
        """One-way hash for PII"""
        salt = "your-static-salt"  # Use proper salt management
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()
```

#### GDPR Compliance (if applicable)
- Right to erasure implementation
- Data portability features
- Consent management
- Privacy by design

### 3. Risk Controls

#### Position Limits
```python
class ComplianceRiskControls:
    def __init__(self, config):
        self.max_position_value = config['max_position_value']
        self.max_daily_trades = config['max_daily_trades']
        self.restricted_symbols = config['restricted_symbols']
    
    def check_compliance(self, order: Order) -> Tuple[bool, str]:
        """Check order against compliance rules"""
        # Pattern Day Trader Rule
        if self._is_pattern_day_trader_violation(order):
            return False, "PDT rule violation"
        
        # Position concentration
        if self._exceeds_concentration_limit(order):
            return False, "Position concentration limit exceeded"
        
        # Restricted list
        if order.symbol in self.restricted_symbols:
            return False, "Symbol on restricted list"
        
        return True, "Compliant"
```

## Security Checklist

### Pre-Production
- [ ] Security code review completed
- [ ] Penetration testing performed
- [ ] Vulnerability scan passed
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Access controls implemented
- [ ] Audit logging enabled
- [ ] Encryption at rest configured
- [ ] Backup encryption verified
- [ ] Incident response plan created

### API Security
- [ ] API keys stored securely
- [ ] Rate limiting implemented
- [ ] Request signing enabled
- [ ] IP whitelisting configured
- [ ] API access logging enabled
- [ ] Token refresh automation tested
- [ ] Error messages sanitized
- [ ] CORS properly configured

### Data Protection
- [ ] Database encryption enabled
- [ ] Backup encryption configured
- [ ] PII identification completed
- [ ] Data retention policies set
- [ ] Secure deletion procedures
- [ ] Access logs monitored
- [ ] Data classification done

### Operational Security
- [ ] 2FA enabled for all users
- [ ] VPN access configured
- [ ] Security monitoring active
- [ ] Incident response tested
- [ ] Disaster recovery plan
- [ ] Security training completed
- [ ] Change management process
- [ ] Vulnerability management

## Incident Response Plan

### Severity Levels
1. **Critical**: System compromise, data breach, unauthorized trading
2. **High**: Authentication bypass, significant data exposure
3. **Medium**: Failed security controls, suspicious activity
4. **Low**: Policy violations, minor security events

### Response Procedures

#### 1. Detection & Analysis
```python
class IncidentDetector:
    def __init__(self):
        self.thresholds = {
            'failed_logins': 5,
            'api_errors': 100,
            'unusual_trading_volume': 10000
        }
    
    async def monitor_security_events(self):
        """Monitor for security incidents"""
        while True:
            if await self._detect_brute_force():
                await self._trigger_incident('CRITICAL', 'Brute force detected')
            
            if await self._detect_api_abuse():
                await self._trigger_incident('HIGH', 'API abuse detected')
            
            if await self._detect_unusual_trading():
                await self._trigger_incident('HIGH', 'Unusual trading pattern')
            
            await asyncio.sleep(60)  # Check every minute
```

#### 2. Containment
- Immediate actions by severity:
  - **Critical**: Halt all trading, revoke API keys
  - **High**: Disable affected accounts, increase monitoring
  - **Medium**: Enhanced logging, investigation
  - **Low**: Log and review

#### 3. Eradication & Recovery
- Identify root cause
- Remove threat
- Patch vulnerabilities
- Restore from clean backups
- Verify system integrity

#### 4. Post-Incident
- Document timeline
- Identify lessons learned
- Update security controls
- Revise procedures
- Report to regulators if required

## Security Monitoring

### Real-time Monitoring
```python
# Prometheus alerts
groups:
  - name: security
    rules:
      - alert: HighFailedLoginRate
        expr: rate(auth_failures_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High rate of failed logins detected
      
      - alert: UnusualAPIActivity
        expr: rate(api_requests_total[5m]) > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Unusual API activity detected
      
      - alert: SuspiciousTradingPattern
        expr: trading_volume > 10000
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Suspicious trading volume detected
```

### Security Metrics Dashboard
- Failed authentication attempts
- API usage by endpoint
- Active sessions by user
- Data access patterns
- System privilege usage
- Compliance violations
- Security event trends

## Compliance Calendar

### Daily
- Review audit logs
- Check compliance alerts
- Verify data backups
- Monitor access logs

### Weekly
- Security metrics review
- Vulnerability scan
- Access control audit
- Compliance report

### Monthly
- Security awareness training
- Penetration testing
- Policy review
- Incident response drill

### Quarterly
- Full security audit
- Compliance assessment
- API key rotation
- Certificate renewal check

### Annually
- Complete security review
- Regulatory filing
- Policy updates
- Training refresh

## Contact Information

### Security Team
- Security Lead: [Name]
- Email: security@tradingfirm.com
- Phone: [Emergency number]

### Compliance Officer
- Name: [Compliance Officer]
- Email: compliance@tradingfirm.com
- Phone: [Office number]

### Incident Response
- 24/7 Hotline: [Number]
- Email: incident@tradingfirm.com
- Escalation: [Manager contact]

### External Contacts
- Legal Counsel: [Contact]
- Regulatory Liaison: [Contact]
- Security Vendor: [Contact]

## Appendix: Security Tools

### Recommended Tools
1. **SIEM**: Splunk or ELK Stack
2. **Vulnerability Scanner**: Nessus or OpenVAS
3. **Web Application Firewall**: ModSecurity
4. **Intrusion Detection**: Snort or Suricata
5. **Secret Management**: HashiCorp Vault
6. **Certificate Management**: Let's Encrypt with Certbot
7. **Backup**: Borgmatic with encryption

### Security Libraries
```python
# requirements-security.txt
cryptography==41.0.0
PyJWT==2.8.0
python-jose==3.3.0
passlib==1.7.4
argon2-cffi==21.3.0
python-dotenv==1.0.0
keyring==24.2.0
```

This security and compliance guide should be reviewed and updated regularly to ensure it remains current with evolving threats and regulatory requirements.