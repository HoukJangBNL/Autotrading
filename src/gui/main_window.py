"""
Main GUI window for Schwab Automated Trading System.
Frontend persona focus: Modern, intuitive, accessible design.
"""

import sys
import asyncio
from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QStatusBar, QMenuBar, QLabel, QPushButton, QSplitter,
    QTextEdit, QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import QTimer, Signal, QThread, Qt
from PySide6.QtGui import QFont, QIcon, QAction, QColor
import logging
from datetime import datetime

# Import GUI services
from .services.gui_service import GUIService
from .services.websocket_client import GUIWebSocketClient

logger = logging.getLogger(__name__)


class TradingDashboard(QMainWindow):
    """
    Main trading dashboard with tabbed interface.
    Focus: User experience, accessibility, real-time updates.
    """
    
    # Signals for real-time updates
    market_data_received = Signal(dict)
    system_status_changed = Signal(str, str)  # status, message
    
    def __init__(self):
        super().__init__()
        self.current_mode = "Discovery"  # Discovery, Selection, Trading
        self.is_connected = False
        
        # Initialize GUI services - start in Mock mode for testing
        self.gui_service = GUIService(mock_mode=True)
        self.websocket_client = GUIWebSocketClient()
        
        # Check if we're in mock mode
        self.mock_mode = self.gui_service.mock_mode
        
        # Discovery state
        self.discovery_running = False
        self.watchlist_symbols = set()
        
        # Data storage
        self.market_data_cache = {}
        self.discovery_alerts = []
        
        self.init_ui()
        self.setup_menu_bar()
        self.setup_status_bar()
        self.setup_connections()
        self.setup_services()
        
        logger.info("Trading Dashboard initialized with GUI services")
    
    def init_ui(self):
        """Initialize the main user interface."""
        self.setWindowTitle("Schwab Auto Trading System - v1.0")
        self.setGeometry(100, 100, 1400, 900)
        
        # Force window to front on macOS
        self.raise_()
        self.activateWindow()
        self.show()
        
        # Set modern styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
                padding: 8px 16px;
                margin-right: 2px;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Create central widget with tab layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Add control bar at top
        self.create_control_bar(layout)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_discovery_tab()
        self.create_selection_tab()
        self.create_trading_tab()
        
        # Set Discovery as default active tab
        self.tab_widget.setCurrentIndex(0)
    
    def create_control_bar(self, parent_layout):
        """Create top control bar with system controls."""
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        
        # Mode selection
        self.mode_checkbox = QCheckBox("Real Trading Mode")
        self.mode_checkbox.setToolTip("Enable real Schwab API connection (requires authentication)")
        self.mode_checkbox.stateChanged.connect(self.toggle_trading_mode)
        control_layout.addWidget(self.mode_checkbox)
        
        control_layout.addStretch()
        
        # System status indicator
        self.status_indicator = QLabel("⚫ Disconnected")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-weight: bold;
                padding: 5px 10px;
                border: 1px solid #d32f2f;
                border-radius: 15px;
                background-color: #ffebee;
            }
        """)
        control_layout.addWidget(self.status_indicator)
        
        control_layout.addStretch()
        
        # Mode indicator
        mode_label = QLabel(f"Current Mode: {self.current_mode}")
        mode_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        control_layout.addWidget(mode_label)
        
        control_layout.addStretch()
        
        # System controls
        self.connect_btn = QPushButton("Connect to Market")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.connect_btn.clicked.connect(self.toggle_connection)
        control_layout.addWidget(self.connect_btn)
        
        self.emergency_stop_btn = QPushButton("🛑 EMERGENCY STOP")
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        control_layout.addWidget(self.emergency_stop_btn)
        
        parent_layout.addWidget(control_widget)
    
    def create_discovery_tab(self):
        """Create the Discovery mode tab with market scanning capabilities."""
        discovery_widget = QWidget()
        
        # Main layout: left panel (controls) + right panel (results)
        main_layout = QHBoxLayout(discovery_widget)
        
        # Left panel: Discovery criteria and controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)
        
        # Discovery criteria group
        criteria_group = QGroupBox("Discovery Criteria")
        criteria_layout = QGridLayout(criteria_group)
        
        # Volume criteria
        volume_group = QGroupBox("Volume Analysis")
        volume_layout = QGridLayout(volume_group)
        volume_layout.addWidget(QLabel("Volume Spike:"), 0, 0)
        volume_layout.addWidget(QPushButton("2x Average"), 0, 1)
        volume_layout.addWidget(QPushButton("5x Average"), 1, 1)
        volume_layout.addWidget(QPushButton("10x Average"), 2, 1)
        criteria_layout.addWidget(volume_group, 0, 0, 1, 2)
        
        # Price movement criteria
        price_group = QGroupBox("Price Movement")
        price_layout = QGridLayout(price_group)
        price_layout.addWidget(QLabel("Change >"), 0, 0)
        price_layout.addWidget(QPushButton("5%"), 0, 1)
        price_layout.addWidget(QPushButton("10%"), 1, 1)
        price_layout.addWidget(QPushButton("15%"), 2, 1)
        criteria_layout.addWidget(price_group, 1, 0, 1, 2)
        
        # Market cap filter
        mcap_group = QGroupBox("Market Cap")
        mcap_layout = QGridLayout(mcap_group)
        mcap_layout.addWidget(QPushButton("Small (<2B)"), 0, 0)
        mcap_layout.addWidget(QPushButton("Mid (2B-10B)"), 1, 0)
        mcap_layout.addWidget(QPushButton("Large (>10B)"), 2, 0)
        criteria_layout.addWidget(mcap_group, 2, 0, 1, 2)
        
        left_layout.addWidget(criteria_group)
        
        # Discovery controls
        controls_group = QGroupBox("Discovery Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        self.start_discovery_btn = QPushButton("🔍 Start Discovery")
        self.start_discovery_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        self.start_discovery_btn.clicked.connect(self.start_discovery)
        controls_layout.addWidget(self.start_discovery_btn)
        
        self.stop_discovery_btn = QPushButton("⏹️ Stop Discovery")
        self.stop_discovery_btn.setEnabled(False)
        self.stop_discovery_btn.clicked.connect(self.stop_discovery)
        controls_layout.addWidget(self.stop_discovery_btn)
        
        left_layout.addWidget(controls_group)
        
        # Watch list group
        watchlist_group = QGroupBox("Watch List")
        watchlist_layout = QVBoxLayout(watchlist_group)
        self.watchlist_text = QTextEdit()
        self.watchlist_text.setMaximumHeight(150)
        self.watchlist_text.setPlaceholderText("Your discovered symbols will appear here...")
        watchlist_layout.addWidget(self.watchlist_text)
        left_layout.addWidget(watchlist_group)
        
        left_layout.addStretch()
        
        # Right panel: Real-time results
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Real-time market data table
        market_data_group = QGroupBox("📊 Real-time Market Data")
        market_data_layout = QVBoxLayout(market_data_group)
        
        self.market_data_table = QTableWidget()
        self.market_data_table.setColumnCount(7)
        self.market_data_table.setHorizontalHeaderLabels([
            'Symbol', 'Price', 'Change', 'Change %', 'Volume', 'High', 'Low'
        ])
        
        # Set column widths
        header = self.market_data_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Price
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Change
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Change %
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)           # Volume
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # High
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Low
        
        self.market_data_table.setAlternatingRowColors(True)
        self.market_data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        market_data_layout.addWidget(self.market_data_table)
        
        right_layout.addWidget(market_data_group)
        
        # Discovery alerts
        alerts_group = QGroupBox("🚨 Discovery Alerts")
        alerts_layout = QVBoxLayout(alerts_group)
        
        self.alerts_text = QTextEdit()
        self.alerts_text.setMaximumHeight(200)
        self.alerts_text.setPlaceholderText("""
        🔍 Discovery Mode Ready
        
        Click "Start Discovery" to begin scanning for opportunities.
        Alerts will appear here when criteria are met.
        """)
        alerts_layout.addWidget(self.alerts_text)
        
        right_layout.addWidget(alerts_group)
        
        # Add panels to main layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 1050])  # Give more space to results
        
        main_layout.addWidget(splitter)
        
        self.tab_widget.addTab(discovery_widget, "🔍 Discovery")
    
    def create_selection_tab(self):
        """Create placeholder Selection mode tab."""
        selection_widget = QWidget()
        layout = QVBoxLayout(selection_widget)
        
        placeholder_group = QGroupBox("🎯 Selection Mode")
        placeholder_layout = QVBoxLayout(placeholder_group)
        
        placeholder_text = QTextEdit()
        placeholder_text.setPlaceholderText("""
        🚧 COMING SOON - Selection Mode
        
        This mode will provide:
        • Strategy optimization for discovered symbols
        • Backtesting capabilities
        • Risk assessment tools
        • Portfolio allocation suggestions
        
        Currently in development...
        """)
        placeholder_text.setEnabled(False)
        placeholder_layout.addWidget(placeholder_text)
        
        layout.addWidget(placeholder_group)
        
        self.tab_widget.addTab(selection_widget, "🎯 Selection")
    
    def create_trading_tab(self):
        """Create placeholder Trading mode tab."""
        trading_widget = QWidget()
        layout = QVBoxLayout(trading_widget)
        
        placeholder_group = QGroupBox("⚡ Trading Mode")
        placeholder_layout = QVBoxLayout(placeholder_group)
        
        placeholder_text = QTextEdit()
        placeholder_text.setPlaceholderText("""
        🚧 COMING SOON - Live Trading Mode
        
        This mode will provide:
        • Automated order execution
        • Real-time position management
        • Risk monitoring and controls
        • Performance tracking
        
        Currently in development...
        """)
        placeholder_text.setEnabled(False)
        placeholder_layout.addWidget(placeholder_text)
        
        layout.addWidget(placeholder_group)
        
        self.tab_widget.addTab(trading_widget, "⚡ Trading")
    
    def setup_menu_bar(self):
        """Setup application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        refresh_action = QAction('Refresh', self)
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup application status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Connection status
        self.conn_status_label = QLabel("Disconnected from market data")
        self.status_bar.addWidget(self.conn_status_label)
        
        # Discovery status
        self.discovery_status_label = QLabel("Discovery: Stopped")
        self.status_bar.addPermanentWidget(self.discovery_status_label)
        
        # Update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
    
    def setup_connections(self):
        """Setup signal connections."""
        self.market_data_received.connect(self.handle_market_data)
        self.system_status_changed.connect(self.handle_status_change)
    
    def setup_services(self):
        """Setup GUI services and their connections."""
        # Connect GUI service signals
        self.gui_service.market_data_updated.connect(self.handle_market_data_update)
        self.gui_service.discovery_alert.connect(self.handle_discovery_alert)
        self.gui_service.connection_status_changed.connect(self.handle_connection_status_change)
        self.gui_service.system_error.connect(self.handle_system_error)
        
        # Connect WebSocket client signals
        self.websocket_client.market_data_received.connect(self.handle_websocket_data)
        self.websocket_client.connection_status_changed.connect(self.handle_websocket_status)
        self.websocket_client.error_occurred.connect(self.handle_websocket_error)
        
        logger.info("GUI services connected")
    
    # Event handlers
    def toggle_connection(self):
        """Toggle market data connection."""
        if self.is_connected:
            self.disconnect_from_market()
        else:
            self.connect_to_market()
    
    def connect_to_market(self):
        """Connect to market data feed using GUI service."""
        self.gui_service.connect_to_backend_sync()
        
        # Only start WebSocket connection if not in mock mode
        if not self.mock_mode:
            # Start WebSocket connection with default symbols
            default_symbols = {'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN'}
            self.websocket_client.connect_websocket(default_symbols)
        else:
            logger.info("Skipping WebSocket connection - running in Mock mode")
        
        self.is_connected = True
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        
        if self.mock_mode:
            self.status_indicator.setText("🟡 Mock Mode")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #f57c00;
                    font-weight: bold;
                    padding: 5px 10px;
                    border: 1px solid #f57c00;
                    border-radius: 15px;
                    background-color: #fff3e0;
                }
            """)
            self.conn_status_label.setText("Connected to Mock backend (Testing Mode)")
        else:
            self.status_indicator.setText("🟢 Connected")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #388e3c;
                    font-weight: bold;
                    padding: 5px 10px;
                    border: 1px solid #388e3c;
                    border-radius: 15px;
                    background-color: #e8f5e8;
                }
            """)
            self.conn_status_label.setText("Connected to Schwab market data")
        logger.info("Connected to market data with GUI services")
    
    def disconnect_from_market(self):
        """Disconnect from market data feed."""
        # Stop discovery if running
        if self.discovery_running:
            self.stop_discovery()
        
        # Disconnect services
        self.gui_service.disconnect_from_backend_sync()
        
        # Only disconnect WebSocket if not in mock mode
        if not self.mock_mode:
            self.websocket_client.disconnect()
        else:
            logger.info("Skipping WebSocket disconnect - running in Mock mode")
        
        self.is_connected = False
        self.connect_btn.setText("Connect to Market")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.status_indicator.setText("⚫ Disconnected")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-weight: bold;
                padding: 5px 10px;
                border: 1px solid #d32f2f;
                border-radius: 15px;
                background-color: #ffebee;
            }
        """)
        
        self.conn_status_label.setText("Disconnected from market data")
        logger.info("Disconnected from market data with GUI services")
    
    def start_discovery(self):
        """Start the discovery process."""
        if not self.is_connected:
            self.alerts_text.append("❌ Please connect to market data first!")
            return
            
        # Get discovery criteria from UI
        criteria = self.get_discovery_criteria_from_ui()
        
        # Start discovery with GUI service
        self.gui_service.start_discovery(criteria)
        
        self.discovery_running = True
        self.start_discovery_btn.setEnabled(False)
        self.stop_discovery_btn.setEnabled(True)
        self.discovery_status_label.setText("Discovery: Running")
        
        self.alerts_text.append(f"🔍 Discovery started - scanning for opportunities...")
        logger.info("Discovery mode started with GUI service")
    
    def stop_discovery(self):
        """Stop the discovery process."""
        # Stop discovery with GUI service
        self.gui_service.stop_discovery()
        
        self.discovery_running = False
        self.start_discovery_btn.setEnabled(True)
        self.stop_discovery_btn.setEnabled(False)
        self.discovery_status_label.setText("Discovery: Stopped")
        
        self.alerts_text.append("⏹️ Discovery stopped")
        logger.info("Discovery mode stopped")
    
    def get_discovery_criteria_from_ui(self) -> Dict:
        """Extract discovery criteria from UI controls."""
        # For now, return default criteria
        # TODO: Get actual values from UI controls
        return {
            'volume_spike_threshold': 2.0,
            'price_change_threshold': 5.0,
            'min_volume': 100000,
            'market_cap_filter': None
        }
    
    def toggle_trading_mode(self):
        """Toggle between Mock and Real trading mode."""
        if self.is_connected:
            self.alerts_text.append("❌ Please disconnect before changing trading mode")
            # Revert checkbox state
            self.mode_checkbox.setChecked(not self.mode_checkbox.isChecked())
            return
        
        real_mode = self.mode_checkbox.isChecked()
        
        # Recreate GUI service with new mode
        old_service = self.gui_service
        self.gui_service = GUIService(mock_mode=not real_mode)
        
        # Reconnect signals
        self.setup_services()
        
        # Update mode indicator
        mode_text = "Real Mode" if real_mode else "Mock Mode"
        self.alerts_text.append(f"🔄 Switched to {mode_text}")
        
        logger.info(f"Trading mode changed to: {mode_text}")
    
    def emergency_stop(self):
        """Emergency stop all operations."""
        self.stop_discovery()
        self.disconnect_from_market()
        
        self.alerts_text.append("🛑 EMERGENCY STOP - All operations halted")
        logger.warning("Emergency stop activated")
    
    # GUI Service Event Handlers
    def handle_market_data_update(self, data):
        """Handle market data update from GUI service."""
        if isinstance(data, dict):
            self.update_market_data_table(data)
    
    def handle_discovery_alert(self, alert_data):
        """Handle discovery alert from GUI service."""
        if isinstance(alert_data, dict):
            symbol = alert_data.get('symbol', 'Unknown')
            alert_type = alert_data.get('type', 'unknown')
            message = alert_data.get('message', 'Alert')
            severity = alert_data.get('severity', 'low')
            timestamp = alert_data.get('timestamp', datetime.now().strftime('%H:%M:%S'))
            
            # Color code by severity
            color_map = {
                'low': '#2196f3',     # Blue
                'medium': '#ff9800',  # Orange  
                'high': '#f44336'     # Red
            }
            color = color_map.get(severity, '#2196f3')
            
            # Add to alerts display
            alert_html = f"""
            <div style="color: {color}; font-weight: bold;">
                [{timestamp}] {symbol}: {message}
            </div>
            """
            
            self.alerts_text.append(alert_html)
            
            # Add to watchlist if not already there
            if symbol not in self.watchlist_symbols:
                self.add_to_watchlist(symbol)
    
    def handle_connection_status_change(self, connected, message):
        """Handle connection status change from GUI service."""
        if connected:
            self.conn_status_label.setText(f"Backend: {message}")
        else:
            self.conn_status_label.setText(f"Backend: {message}")
    
    def handle_system_error(self, error_message):
        """Handle system error from GUI service."""
        self.alerts_text.append(f"❌ System Error: {error_message}")
        logger.error(f"GUI Service Error: {error_message}")
    
    # WebSocket Event Handlers
    def handle_websocket_data(self, data):
        """Handle incoming WebSocket market data."""
        if isinstance(data, dict):
            self.update_market_data_table(data)
            self.market_data_cache[data.get('symbol', '')] = data
    
    def handle_websocket_status(self, connected, message):
        """Handle WebSocket connection status."""
        status_text = "Connected" if connected else "Disconnected"
        self.conn_status_label.setText(f"WebSocket: {status_text} - {message}")
    
    def handle_websocket_error(self, error_message):
        """Handle WebSocket error."""
        self.alerts_text.append(f"🌐 WebSocket Error: {error_message}")
        logger.error(f"WebSocket Error: {error_message}")
    
    # Data Display Methods
    def update_market_data_table(self, data):
        """Update the market data table with new data."""
        if not isinstance(data, dict):
            return
            
        symbol = data.get('symbol', '')
        if not symbol:
            return
        
        # Find existing row or create new one
        row = self.find_symbol_row(symbol)
        if row == -1:
            row = self.market_data_table.rowCount()
            self.market_data_table.insertRow(row)
        
        # Update table cells
        self.market_data_table.setItem(row, 0, QTableWidgetItem(symbol))
        self.market_data_table.setItem(row, 1, QTableWidgetItem(f"${data.get('price', 0.0):.2f}"))
        
        # Color code change values
        change = data.get('change', 0.0)
        change_percent = data.get('change_percent', 0.0)
        
        change_item = QTableWidgetItem(f"${change:+.2f}")
        change_percent_item = QTableWidgetItem(f"{change_percent:+.2f}%")
        
        # Set colors based on change
        if change > 0:
            change_item.setForeground(QColor(76, 175, 80))      # Green
            change_percent_item.setForeground(QColor(76, 175, 80))
        elif change < 0:
            change_item.setForeground(QColor(244, 67, 54))      # Red
            change_percent_item.setForeground(QColor(244, 67, 54))
        
        self.market_data_table.setItem(row, 2, change_item)
        self.market_data_table.setItem(row, 3, change_percent_item)
        self.market_data_table.setItem(row, 4, QTableWidgetItem(f"{data.get('volume', 0):,}"))
        self.market_data_table.setItem(row, 5, QTableWidgetItem(f"${data.get('high', 0.0):.2f}"))
        self.market_data_table.setItem(row, 6, QTableWidgetItem(f"${data.get('low', 0.0):.2f}"))
    
    def find_symbol_row(self, symbol):
        """Find the row index for a given symbol."""
        for row in range(self.market_data_table.rowCount()):
            item = self.market_data_table.item(row, 0)
            if item and item.text() == symbol:
                return row
        return -1
    
    def add_to_watchlist(self, symbol):
        """Add symbol to watchlist."""
        symbol = symbol.upper()
        if symbol not in self.watchlist_symbols:
            self.watchlist_symbols.add(symbol)
            self.update_watchlist_display()
            
            # Subscribe to WebSocket data for this symbol (only if not in mock mode)
            if not self.mock_mode and self.websocket_client.is_connected():
                self.websocket_client.subscribe_symbol(symbol)
    
    def update_watchlist_display(self):
        """Update the watchlist text display."""
        watchlist_text = "\n".join(sorted(self.watchlist_symbols))
        self.watchlist_text.setPlainText(watchlist_text)
    
    # Legacy handlers
    def handle_market_data(self, data):
        """Handle incoming market data (legacy)."""
        self.handle_websocket_data(data)
    
    def handle_status_change(self, status, message):
        """Handle system status changes (legacy)."""
        self.status_bar.showMessage(f"{status}: {message}", 5000)
    
    def update_status(self):
        """Update status information."""
        # Update connection status
        if self.is_connected:
            # Show current time or data timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S")
            self.conn_status_label.setText(f"Connected - Last update: {current_time}")
    
    def open_settings(self):
        """Open settings dialog."""
        # TODO: Implement settings dialog
        logger.info("Settings requested")
    
    def refresh_data(self):
        """Refresh all data displays."""
        logger.info("Data refresh requested")
    
    def show_about(self):
        """Show about dialog."""
        # TODO: Implement about dialog
        logger.info("About dialog requested")
    
    def closeEvent(self, event):
        """Handle application close."""
        self.disconnect_from_market()
        event.accept()


def main():
    """Run the trading dashboard application."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Schwab Auto Trading System")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("AutoTrading Solutions")
    
    # macOS specific settings
    app.setQuitOnLastWindowClosed(True)
    
    # Create and show main window
    dashboard = TradingDashboard()
    dashboard.show()
    dashboard.raise_()
    dashboard.activateWindow()
    
    # Force focus to application
    app.setActiveWindow(dashboard)
    
    print(f"GUI Window created and should be visible at position ({dashboard.x()}, {dashboard.y()})")
    print("If you don't see the window, check your dock or try Alt+Tab")
    
    return app.exec()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())