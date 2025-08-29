#!/bin/bash

echo "🔐 Generating SSL certificates..."

# Create certs directory if it doesn't exist
mkdir -p certs
cd certs

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=Unit/CN=localhost"

echo "✅ SSL certificates generated in certs/ directory"
echo "   - cert.pem: Certificate file"
echo "   - key.pem: Private key file"