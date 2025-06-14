# SFO Enhanced Scraper Installation

## Prerequisites

Make sure you have Python 3 and virtual environment support on your Ubuntu system:

```bash
sudo apt update
sudo apt install python3 python3-full python3-venv -y
```

## Installation Methods

### Method 1: Automatic Installation (Recommended)

Run the installation script:

```bash
cd /path/to/ha_sfoweb
chmod +x install_deps.sh
./install_deps.sh
```

### Method 2: Manual Installation

Install dependencies manually using a virtual environment:

```bash
cd /path/to/ha_sfoweb

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Testing the Scraper

After installation, test the scraper with your credentials:

### Option 1: Use the convenience script
```bash
./run_test.sh
```

### Option 2: Manual activation
```bash
source venv/bin/activate
python test_scraper.py
```

The script will prompt you for your SFO username and password, then test:
- Credential validation
- Appointment fetching
- Data parsing

## Installing in Home Assistant

1. Copy the `custom_components/sfoweb` folder to your Home Assistant configuration directory:
   ```bash
   cp -r custom_components/sfoweb /path/to/homeassistant/config/custom_components/
   ```

2. Restart Home Assistant

3. Go to **Settings** → **Devices & Services** → **Add Integration**

4. Search for "SFOWeb" and configure with your credentials

## Troubleshooting

### Import Errors
If you get import errors, make sure the dependencies are installed:
```bash
python3 -c "import aiohttp, bs4; print('✅ All dependencies installed')"
```

### Permission Issues
If pip fails with permission errors, use the `--user` flag:
```bash
pip3 install --user -r requirements.txt
```

### Virtual Environment (Optional)
For a cleaner installation, use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 test_scraper.py
```

## Dependencies

- `aiohttp>=3.8.0` - Async HTTP client for web requests
- `beautifulsoup4>=4.11.0` - HTML parsing and manipulation