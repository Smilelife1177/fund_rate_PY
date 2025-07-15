#!/bin/bash

# Check if .env file already exists
if [ -f .env ]; then
    echo "Error: .env file already exists"
    exit 1
fi

# Create .env file with Bybit API key and secret placeholders
cat << EOF > .env
BYBIT_API_KEY =
BYBIT_API_SECRET =
BYBIT_API_KEY_TEST =
BYBIT_API_SECRET_TEST =
BINANCE_API_KEY =
BINANCE_API_SECRET =
BINANCE_API_KEY_TEST =
BINANCE_API_SECRET_TEST =
EOF

echo ".env file created successfully"