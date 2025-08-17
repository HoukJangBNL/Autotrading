#!/bin/bash
# Test GUI in venv

echo "🐍 Testing GUI in virtual environment..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ venv not found. Please create it first:"
    echo "python -m venv venv"
    exit 1
fi

# Activate venv
echo "📦 Activating venv..."
source venv/bin/activate

# Check Python version
echo "Python version: $(python --version)"
echo "Python location: $(which python)"

# Check if PySide6 is installed
echo ""
echo "🔍 Checking PySide6..."
python -c "import PySide6; print('✅ PySide6 available')" 2>/dev/null || {
    echo "❌ PySide6 not installed"
    echo "Installing PySide6..."
    pip install PySide6
}

# Test GUI import
echo ""
echo "🧪 Testing GUI imports..."
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.') / 'src'))
try:
    from gui.services.gui_service import GUIService
    print('✅ GUIService import successful')
    service = GUIService(mock_mode=True)
    print('✅ GUIService creation successful')
    print(f'   Backend available: {not service.mock_mode}')
    print(f'   Mock mode: {service.mock_mode}')
except Exception as e:
    print(f'❌ Error: {e}')
    exit 1
"

echo ""
echo "🚀 Ready to launch GUI!"
echo "Run: python run_gui.py"