# Autonomous Vehicle Convoy System - LCM Implementation

This project implements a motion detection system for autonomous vehicle convoys using LCM (Lightweight Communications and Marshalling) for inter-vehicle communication.

## Components

1. **LCM Schema** (`convoy_messages.lcm`) - Defines message types for convoy communication
2. **Python Motion Detector** (`motion_detector.py`) - Main vehicle system with camera-based motion detection
3. **C Message Monitor** (`lcm_monitor.c`) - Terminal-based message monitor for debugging
4. **Build System** (`Makefile`) - Automated build configuration

## Message Types

- **Heartbeat** (`convoy.heartbeat_t`) - Periodic alive signals from convoy vehicles
- **Warning** (`convoy.warning_t`) - Danger/obstacle detection alerts
- **Mode** (`convoy.mode_t`) - Driving mode change notifications
- **Status** (`convoy.status_t`) - Comprehensive vehicle status information

## Installation

### Prerequisites

#### macOS (using Homebrew)

```bash
brew install lcm glib pkg-config opencv python
```

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config liblcm-dev libglib2.0-dev
sudo apt-get install -y python3-opencv python3-numpy python3-lcm
```

### Build Steps

1. **Generate LCM bindings and build the C monitor:**

```bash
make all
```

2. **Generate Python bindings (optional, for completeness):**

```bash
make python-bindings
```

3. **Install Python dependencies:**

```bash
pip install opencv-python numpy python-lcm
```

## Usage

### Running the System

1. **Start the LCM message monitor** (in one terminal):

```bash
./lcm_monitor
```

2. **Start the motion detection system** (in another terminal):

```bash
python motion_detector.py --vehicle-id 1 --mode 0
```

3. **Start additional vehicles** (in separate terminals):

```bash
python motion_detector.py --vehicle-id 2 --mode 2  # Convoy follower
python motion_detector.py --vehicle-id 3 --mode 1  # Convoy head
```

### Command Line Options

#### Motion Detector (`motion_detector.py`)

```bash
python motion_detector.py [options]

Options:
  --camera CAMERA       Camera device ID (default: 0)
  --threshold THRESHOLD Motion detection threshold (default: 25)
  --min-area MIN_AREA   Minimum contour area (default: 500)
  --mode {0,1,2}        Initial driving mode (default: 0)
  --vehicle-id ID       Unique vehicle identifier (default: 1)
```

#### LCM Monitor (`lcm_monitor`)

```bash
./lcm_monitor [options]

Options:
  -h, --help           Show help message
  -c CHANNEL          Subscribe to specific channel only
```

### Interactive Commands

When running the motion detector, you can use these commands:

- `0`, `1`, `2` - Set driving mode (Single/Head/Convoy)
- `s` - Show current system status
- `l` - Show recent log messages
- `st` - Send status message to network
- `w` - Send test warning message
- `q` - Quit the system

### Driving Modes

- **Mode 0 (Single Vehicle)**: Operates independently, no convoy communication
- **Mode 1 (Head in Convoy)**: Leads convoy, sends warnings to followers
- **Mode 2 (In Convoy)**: Follows convoy, relays warnings to other vehicles

## Development

### Building Components Separately

```bash
# Generate only LCM bindings
lcm-gen -c --c-cpath lcm_generated --c-hpath lcm_generated convoy_messages.lcm
lcm-gen -p --ppath lcm_generated convoy_messages.lcm

# Compile only the C monitor
gcc -Wall -Wextra -std=c99 -Ilcm_generated lcm_generated/*.c lcm_monitor.c -llcm -lglib-2.0 -o lcm_monitor
```

### Testing

1. **Test LCM installation:**

```bash
make test
```

2. **Monitor specific message types:**

```bash
./lcm_monitor -c HEARTBEAT    # Only heartbeat messages
./lcm_monitor -c WARNING      # Only warning messages
./lcm_monitor -c MODE         # Only mode change messages
./lcm_monitor -c STATUS       # Only status messages
```

3. **Test convoy behavior:**
   - Start monitor: `./lcm_monitor`
   - Start head vehicle: `python motion_detector.py --vehicle-id 1 --mode 1`
   - Start follower: `python motion_detector.py --vehicle-id 2 --mode 2`
   - Trigger warning in head vehicle: Press `w` in head vehicle terminal
   - Observe message propagation in monitor

### Cleaning Build Artifacts

```bash
make clean
```

## Network Configuration

LCM uses UDP multicast by default. For distributed testing:

1. **Same machine**: Default configuration works
2. **Multiple machines**: Ensure UDP multicast is enabled on your network
3. **Custom LCM URL**: Set environment variable:

```bash
export LCM_DEFAULT_URL="udpm://239.255.76.67:7667?ttl=1"
```

## Troubleshooting

### Common Issues

1. **"Cannot open camera"**: Check camera device ID, try different values (0, 1, 2...)
2. **LCM import errors**: Ensure `lcm_generated` directory exists and has generated Python files
3. **Build failures**: Install missing dependencies using the appropriate package manager
4. **No messages received**: Check network configuration and firewall settings

### Debug Tips

- Use `lcm-spy` (if available) for graphical message monitoring
- Check LCM traffic with: `lcm-logger -f logfile.lcm`
- Enable verbose logging in the Python code by adding debug prints

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Vehicle 1     │    │   Vehicle 2     │    │   Vehicle 3     │
│  (Head Convoy)  │    │  (In Convoy)    │    │ (Single/Convoy) │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │   Camera    │ │    │ │   Camera    │ │    │ │   Camera    │ │
│ │ Detection   │ │    │ │ Detection   │ │    │ │ Detection   │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│        │        │    │        │        │    │        │        │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ LCM Client  │ │    │ │ LCM Client  │ │    │ │ LCM Client  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                   ┌─────────────────────────┐
                   │    LCM Network          │
                   │  (UDP Multicast)        │
                   │                         │
                   │ Channels:               │
                   │ - HEARTBEAT             │
                   │ - WARNING               │
                   │ - MODE                  │
                   │ - STATUS                │
                   └─────────────────────────┘
                                 │
                   ┌─────────────────────────┐
                   │   LCM Monitor           │
                   │  (Debug Terminal)       │
                   └─────────────────────────┘
```

## License

This project is part of the DEIS Lab 3 assignment.
